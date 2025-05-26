import { resolve } from "node:path";
import preact from "@preact/preset-vite";
import { defineConfig } from "vitest/config";

// Two separate builds: a tiny classic-script loader that sites paste in,
// and the chat itself as an ES module the loader imports on first interaction.
export default defineConfig(({ mode }) => {
  const isLoader = mode === "loader";
  return {
    plugins: [preact()],
    build: {
      outDir: resolve(import.meta.dirname, "dist"),
      emptyOutDir: isLoader,
      target: "es2020",
      minify: true,
      lib: isLoader
        ? {
            entry: resolve(import.meta.dirname, "src/loader.ts"),
            name: "RelayLoader",
            formats: ["iife"],
            fileName: () => "widget.js",
          }
        : {
            entry: resolve(import.meta.dirname, "src/app.tsx"),
            formats: ["es"],
            fileName: () => "widget-app.js",
          },
    },
    test: {
      environment: "happy-dom",
      include: ["tests/**/*.test.ts?(x)"],
    },
  };
});
