import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins:[react()],
  build:{rollupOptions:{output:{manualChunks:{react:["react","react-dom","react-router-dom"],data:["@tanstack/react-query","@tanstack/react-table","axios","zustand"],forms:["react-hook-form","zod","@hookform/resolvers"]}}}},
  test:{environment:"jsdom",setupFiles:"./src/test/setup.ts",css:true,exclude:["e2e/**","node_modules/**"]},
});
