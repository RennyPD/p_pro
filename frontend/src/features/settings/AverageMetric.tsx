import "./institutional-control.css";
import "./alert-history.css";
import { describeAverage } from "../../lib/academicResult";
import { type GradeMetric } from "./institutionalControlShared";

export function AverageMetric({ r }: { r: GradeMetric }) {
  const average = describeAverage({
    finalAverage: r.average_grade,
    finalCount: r.grade_count,
    provisionalAverage: r.provisional_average_grade,
    provisionalCount: r.provisional_grade_count,
  });
  return (
    <div>
      <dt>{average.kind === "provisional" ? "Promedio provisional" : "Promedio final"}</dt>
      <dd>{average.value}</dd>
      <small>{average.note}</small>
    </div>
  );
}
