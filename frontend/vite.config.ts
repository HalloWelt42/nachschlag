import { readFileSync } from "node:fs";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// Fassung der gebauten Oberfläche (aus version.json): eingebaut ins Skript und als Meta in die Startseite. Der Server
// meldet die der ausgelieferten Startseite; weicht sie ab, lädt ein offener Tab von selbst neu.
const FASSUNG = JSON.parse(readFileSync(new URL("../version.json", import.meta.url), "utf-8")).version as string;
const fassungEinsetzen = {
  name: "fassung-einsetzen",
  transformIndexHtml: (html: string) => html.replace("</head>", `  <meta name="app-fassung" content="${FASSUNG}" />\n  </head>`),
};

// Beim Entwickeln leitet Vite /api ans Backend; im Betrieb liefert das Backend die gebaute Oberfläche selbst aus.
export default defineConfig({
  plugins: [svelte(), fassungEinsetzen],
  define: { __APP_FASSUNG__: JSON.stringify(FASSUNG) },
  // Die Oberfläche des Appkerns kommt als Svelte-Quelltext mit TypeScript; Vite bündelt sie nicht vor, sie wird wie
  // eigener Code übersetzt (sonst scheitert das Vorbündeln an den .svelte.ts-Dateien)
  optimizeDeps: {
    exclude: ["appkern-oberflaeche"],
    // CodeMirror nur einmal: der Editor des Appkerns (appkern-oberflaeche/code, nicht vorgebündelt) braucht von jedem
    // Paket dieselbe Fassung, sonst greifen Erweiterungen und Farben nicht ("multiple instances of @codemirror/state")
    include: [
      "@codemirror/autocomplete", "@codemirror/commands", "@codemirror/lang-css", "@codemirror/lang-html",
      "@codemirror/lang-javascript", "@codemirror/lang-markdown", "@codemirror/lang-php", "@codemirror/lang-python",
      "@codemirror/lang-sql", "@codemirror/language", "@codemirror/lint", "@codemirror/search", "@codemirror/state",
      "@codemirror/view", "@lezer/common", "@lezer/highlight",
    ],
  },
  server: {
    port: 9711,
    strictPort: true,
    proxy: { "/api": { target: "http://127.0.0.1:8711", changeOrigin: false } },
  },
});
