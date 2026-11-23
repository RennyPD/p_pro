import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BookOpen, GraduationCap, Users } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { EmptyState, Spinner } from "../../components/ui";
import { Metric, Tabs } from "../../components/visual";
import { api, apiMessage } from "../../lib/api";
import { useAccess } from "../../lib/permissions";
import { GroupMembersTab } from "./GroupMembersTab";
import { GroupPromotionTab } from "./GroupPromotionTab";
import { GroupSubjectsTab } from "./GroupSubjectsTab";
import { groupKey, type ClassGroupDetail } from "./groupsData";
import "./class-groups.css";

type Tab = "members" | "subjects" | "promotion";

export function ClassGroupPage() {
  const { groupId = "" } = useParams();
  const access = useAccess();
  const [tab, setTab] = useState<Tab>("members");
  const group = useQuery({
    queryKey: groupKey(groupId),
    queryFn: () => api.get<ClassGroupDetail>(`/class-groups/${groupId}`).then(r => r.data),
  });
  if (group.isPending) return <Spinner />;
  if (group.isError)
    return (
      <div className="page">
        <EmptyState
          icon={<Users />}
          title="No pudimos abrir el grupo"
          description={apiMessage(group.error)}
        />
      </div>
    );
  const data = group.data;
  const enrolled = data.members.filter(member => member.status === "enrolled");
  const tabs = [
    {
      key: "members" as const,
      label: "Estudiantes",
      icon: <Users size={16} />,
      count: enrolled.length,
    },
    {
      key: "subjects" as const,
      label: "Materias",
      icon: <BookOpen size={16} />,
      count: data.subjects.length,
    },
    ...(access.can("enrollments.manage")
      ? [{ key: "promotion" as const, label: "Promoción", icon: <GraduationCap size={16} /> }]
      : []),
  ];

  return (
    <div className="page groups-page">
      <Link to="/class-groups" className="groups-back">
        <ArrowLeft size={16} /> Grupos
      </Link>
      <header className="page-header">
        <div>
          <span className="kicker">
            {data.career_name} · {data.school_year_name}
          </span>
          <h1>
            {data.grade_number}.º {data.name}
          </h1>
          <p className="muted">
            Titular: {data.homeroom_teacher_name ?? "sin asignar"} · {data.room}
          </p>
        </div>
      </header>
      <div className="groups-metrics">
        <Metric label="Estudiantes" value={`${enrolled.length} / ${data.capacity}`} />
        <Metric label="Materias del grado" value={data.subjects.length} />
        <Metric
          label="Períodos abiertos"
          value={data.open_periods.length}
          note={data.open_periods.map(name => name.split(" · ")[0]).join(", ") || "Ninguno"}
        />
      </div>
      <Tabs
        items={tabs}
        value={tab}
        onChange={setTab}
        label="Secciones del grupo"
        panelId="group-panel"
      />
      <div id="group-panel" role="tabpanel">
        {tab === "members" && <GroupMembersTab group={data} />}
        {tab === "subjects" && <GroupSubjectsTab group={data} />}
        {tab === "promotion" && <GroupPromotionTab group={data} />}
      </div>
    </div>
  );
}
