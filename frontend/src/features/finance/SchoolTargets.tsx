import { useQuery } from "@tanstack/react-query";
import { api } from "../../lib/api";
import type { ApiSchema } from "../../lib/apiTypes";

type SchoolYear = ApiSchema<"SchoolYearOut">;
type Grade = ApiSchema<"GradeTarget">;
export type SchoolCareer = {
  career_id: number;
  name: string;
  academic_level?: string;
  duration_terms?: number;
};

const SCHOOL_LEVELS = new Set(["initial", "primary", "secondary"]);

/**
 * School year and grades a plan charges (Fase 3 E): the members of that
 * grade's groups in the year. Without months, the plan bills the whole year.
 */
export function SchoolTargets({
  careers,
  yearId,
  onYearChange,
  grades,
  onGradesChange,
  disabled,
}: {
  careers: SchoolCareer[];
  yearId: number | "";
  onYearChange: (id: number | "") => void;
  grades: Grade[];
  onGradesChange: (grades: Grade[]) => void;
  disabled: boolean;
}) {
  const years = useQuery({
    queryKey: ["school-years", "billing"],
    queryFn: () =>
      api.get<SchoolYear[]>("/school-years/", { params: { limit: 20 } }).then(r => r.data),
  });
  const programs = careers.filter(item => SCHOOL_LEVELS.has(item.academic_level ?? ""));
  if (!years.data?.length && !programs.length) return null;
  const has = (careerId: number, grade: number) =>
    grades.some(item => item.career_id === careerId && item.grade_number === grade);
  const toggle = (careerId: number, grade: number) =>
    onGradesChange(
      has(careerId, grade)
        ? grades.filter(item => !(item.career_id === careerId && item.grade_number === grade))
        : [...grades, { career_id: careerId, grade_number: grade }],
    );

  return (
    <div className="billing-school">
      <label className="form-field">
        <span>Año lectivo</span>
        <select
          value={yearId}
          disabled={disabled}
          onChange={event => onYearChange(Number(event.target.value) || "")}
        >
          <option value="">Sin año lectivo</option>
          {years.data?.map(year => (
            <option key={year.school_year_id} value={year.school_year_id}>
              {year.name}
            </option>
          ))}
        </select>
      </label>
      {yearId !== "" &&
        programs.map(program => (
          <fieldset key={program.career_id} className="billing-grades">
            <legend>{program.name}: grados</legend>
            {Array.from({ length: program.duration_terms ?? 6 }, (_, index) => index + 1).map(
              grade => (
                <label key={grade}>
                  <input
                    type="checkbox"
                    checked={has(program.career_id, grade)}
                    onChange={() => toggle(program.career_id, grade)}
                  />
                  {grade}.º
                </label>
              ),
            )}
          </fieldset>
        ))}
    </div>
  );
}
