import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Spinner } from "../../components/ui";
import { api, apiMessage } from "../../lib/api";
import { LegalText } from "./LegalText";
import { legalLinks } from "./legalLinks";
import "./legal.css";

type LegalDocument = { kind: string; title: string; version: string; slug: string; text: string };

/** Public legal documents (Fase 5 G3): terms, privacy, cookies, data processing. */
export function LegalPage() {
  const { slug = "terminos" } = useParams();
  const document = useQuery({
    queryKey: ["legal", slug],
    queryFn: () => api.get<LegalDocument>(`/public/legal/${slug}`).then(r => r.data),
    retry: false,
  });
  return (
    <main className="legal-page">
      <nav className="legal-nav" aria-label="Documentos legales">
        {[...legalLinks, { slug: "tratamiento-de-datos", label: "Tratamiento de datos" }].map(
          link => (
            <Link
              key={link.slug}
              to={`/legal/${link.slug}`}
              aria-current={link.slug === slug ? "page" : undefined}
            >
              {link.label}
            </Link>
          ),
        )}
      </nav>
      <article className="panel legal-article">
        {document.isPending ? (
          <Spinner label="Cargando documento" />
        ) : document.isError ? (
          <p className="form-error">{apiMessage(document.error)}</p>
        ) : (
          <LegalText text={document.data.text} />
        )}
      </article>
      <p className="legal-back">
        <Link to="/login">Volver a Nexo</Link>
      </p>
    </main>
  );
}
