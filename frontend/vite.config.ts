import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Long-lived vendor chunks: they change rarely, so browsers keep them
        // cached between releases. Pages load on demand (React.lazy in App.tsx).
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (
            /[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(
              id,
            )
          )
            return "react";
          // Tables are only used by listing pages, not at sign-in.
          if (id.includes("@tanstack/react-table") || id.includes("@tanstack/table-core"))
            return "tables";
          if (/[\\/]node_modules[\\/](@tanstack|axios|zustand)[\\/]/.test(id)) return "data";
          if (/[\\/]node_modules[\\/](react-hook-form|zod|@hookform)[\\/]/.test(id)) return "forms";
          return undefined;
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    css: true,
    exclude: ["e2e/**", "acceptance/**", "node_modules/**"],
  },
});
