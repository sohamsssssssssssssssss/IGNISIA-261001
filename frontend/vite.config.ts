import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 650,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("cytoscape-fcose")) return "graph-layout-vendor";
          if (id.includes("cytoscape-popper")) return "graph-overlay-vendor";
          if (id.includes("cytoscape")) return "graph-core-vendor";
          if (id.includes("recharts")) return "charts-vendor";
          if (id.includes("/d3")) return "d3-vendor";
          if (id.includes("lucide-react")) return "icons-vendor";
          if (id.includes("react-dom") || id.includes("/react/")) return "react-vendor";
          return undefined;
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test/setup.ts",
  },
});
