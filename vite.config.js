import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [vue()],
  root: resolve(__dirname, "frontend"),
  base: "/static/dist/",
  build: {
    outDir: resolve(__dirname, "app/static/dist"),
    emptyOutDir: true,
    sourcemap: false,
  },
});
