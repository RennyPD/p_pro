import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { resources } from "../../config/resources";
import { api, apiMessage } from "../../lib/api";
import { ResourcePage } from "../resources/ResourcePage";

type Career = { career_id: number; code: string; name: string };

export function SubjectsPage() {
  const [careerId, setCareerId] = useState("");
  const careers = useQuery<Career[]>({
    queryKey: ["subject-career-options"],
    queryFn: async () => {
      const result: Career[] = [];
      for (let skip = 0; ; skip += 100) {
        const response = await api.get<Career[]>("/careers/", { params: { skip, limit: 100 } });
        result.push(...response.data);
        if (response.data.length < 100) return result;
      }
    },
  });
  return <ResourcePage key={careerId || "all"} config={resources.subjects}
    queryParams={careerId ? { career_id: Number(careerId) } : {}}
    toolbarContent={<>
      <select aria-label="Filtrar asignaturas por carrera" value={careerId} onChange={event => setCareerId(event.target.value)} disabled={careers.isLoading || careers.isError}>
        <option value="">Todas las carreras y asignaturas libres</option>
        {careers.data?.map(career => <option key={career.career_id} value={career.career_id}>{career.code} · {career.name}</option>)}
      </select>
      {careers.error && <span role="alert">{apiMessage(careers.error)}</span>}
      <Link className="back-link" to="/careers">Catálogo de carreras</Link>
    </>} />;
}
