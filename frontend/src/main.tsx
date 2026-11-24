import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { Toaster } from "sonner";
import App from "./App";
import { ConfirmHost } from "./components/ConfirmDialog";
import { DraftGuard } from "./components/DraftGuard";
import { initErrorTracking } from "./lib/observability";
import "./styles.css";
import "./accessibility.css";
import "./workspace-design.css";

void initErrorTracking();

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } },
});
const router = createBrowserRouter([
  {
    path: "*",
    element: (
      <DraftGuard>
        <App />
      </DraftGuard>
    ),
  },
]);
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <ConfirmHost />
      <Toaster richColors position="top-right" />
    </QueryClientProvider>
  </StrictMode>,
);
