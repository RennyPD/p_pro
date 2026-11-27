import { useQuery } from "@tanstack/react-query";
import { LifeBuoy } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { useAccess } from "../../lib/permissions";
import { useAuthStore } from "../../store/auth";
import { LegalText } from "../legal/LegalText";
import "./help.css";

type Guide = { slug: string; title: string; summary: string; audience: string[] };

function useRole(): string | null {
  const token = useAuthStore(state => state.token);
  const access = useAccess();
  if (!token || !access.ready) return null;
  if (access.guardian) return "guardian";
  if (access.student) return "student";
  if (access.teaching) return "teacher";
  return access.institution ? "admin" : null;
}

/** Help center (Fase 5 G5): guides of the reader's role first. Public. */
export function HelpPage({ base = "/ayuda" }: { base?: string }) {
  const { slug } = useParams();
  const role = useRole();
  const guides = useQuery({
    queryKey: ["help"],
    queryFn: () => api.get<Guide[]>("/public/help").then(r => r.data),
  });
  const guide = useQuery({
    queryKey: ["help", slug],
    queryFn: () => api.get<Guide & { text: string }>(`/public/help/${slug}`).then(r => r.data),
    enabled: Boolean(slug),
    retry: false,
  });
  const mine = (guides.data ?? []).filter(
    item => role && (item.audience.includes(role) || item.audience.includes("all")),
  );
  const others = (guides.data ?? []).filter(item => !mine.includes(item));
  return (
    <div className="page help-page">
      <header className="page-header">
        <div>
          <span className="kicker">Centro de ayuda</span>
          <h1>¿En qué te ayudamos?</h1>
          <p>
            Guías cortas para cada rol. Si no encuentras lo que buscas, escríbenos desde «Ayuda y
            soporte».
          </p>
        </div>
      </header>
      <div className="help-layout">
        <nav className="panel help-index" aria-label="Guías">
          {guides.isPending ? (
            <Spinner label="Cargando guías" />
          ) : (
            <>
              {mine.length > 0 && (
                <>
                  <h2>Para ti</h2>
                  <GuideList items={mine} current={slug} base={base} />
                </>
              )}
              <h2>{mine.length ? "Otras guías" : "Guías"}</h2>
              <GuideList items={others} current={slug} base={base} />
            </>
          )}
        </nav>
        <article className="panel help-article">
          {!slug ? (
            <div className="help-welcome">
              <LifeBuoy aria-hidden />
              <p>Elige una guía de la lista.</p>
            </div>
          ) : guide.isPending ? (
            <Spinner label="Cargando guía" />
          ) : guide.isError ? (
            <p className="form-error">{apiMessage(guide.error)}</p>
          ) : (
            <LegalText text={guide.data.text} />
          )}
        </article>
      </div>
    </div>
  );
}

function GuideList({ items, current, base }: { items: Guide[]; current?: string; base: string }) {
  return (
    <ul>
      {items.map(item => (
        <li key={item.slug}>
          <Link
            to={`${base}/${item.slug}`}
            aria-current={item.slug === current ? "page" : undefined}
          >
            <strong>{item.title}</strong>
            <small>{item.summary}</small>
          </Link>
        </li>
      ))}
    </ul>
  );
}
