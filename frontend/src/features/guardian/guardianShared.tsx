import type { UseQueryResult } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import type { ReactNode } from "react";
import { EmptyState, Spinner } from "../../components/ui";
import { apiMessage } from "../../lib/api";

/** Loading and error states shared by the guardian tabs. */
export function Loaded<T>({
  query,
  children,
}: {
  query: UseQueryResult<T>;
  children: (data: T) => ReactNode;
}) {
  if (query.isPending) return <Spinner />;
  if (query.isError)
    return (
      <EmptyState
        icon={<AlertTriangle />}
        title="No pudimos cargar esta información"
        description={apiMessage(query.error)}
      />
    );
  return <>{children(query.data)}</>;
}
