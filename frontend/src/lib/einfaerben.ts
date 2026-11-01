// Quellcode einfärben (WIKI-33): eine Stelle für alle Codeblöcke im Lesetext, die der Baustein nicht schon gefärbt hat
// (die Handbücher färben PHP im Backend). Die Sprache kommt aus einem Hinweis (etwa den Schlagwörtern einer Frage),
// sonst erkennt sie sich am Inhalt unter den bekannten Sprachen; bleibt sie unsicher, bleibt der Block schlicht.
// Die Farben sind die Editorfarben (--ed-*, hell und dunkel), in nachschlag.css den Klassen von highlight.js zugeordnet.
import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import c from "highlight.js/lib/languages/c";
import cpp from "highlight.js/lib/languages/cpp";
import csharp from "highlight.js/lib/languages/csharp";
import css from "highlight.js/lib/languages/css";
import diff from "highlight.js/lib/languages/diff";
import dockerfile from "highlight.js/lib/languages/dockerfile";
import go from "highlight.js/lib/languages/go";
import ini from "highlight.js/lib/languages/ini";
import java from "highlight.js/lib/languages/java";
import javascript from "highlight.js/lib/languages/javascript";
import json from "highlight.js/lib/languages/json";
import lua from "highlight.js/lib/languages/lua";
import makefile from "highlight.js/lib/languages/makefile";
import markdown from "highlight.js/lib/languages/markdown";
import php from "highlight.js/lib/languages/php";
import powershell from "highlight.js/lib/languages/powershell";
import python from "highlight.js/lib/languages/python";
import ruby from "highlight.js/lib/languages/ruby";
import rust from "highlight.js/lib/languages/rust";
import shell from "highlight.js/lib/languages/shell";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import vim from "highlight.js/lib/languages/vim";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";

const SPRACHEN = { bash, c, cpp, csharp, css, diff, dockerfile, go, ini, java, javascript, json, lua, makefile, markdown, php,
                   powershell, python, ruby, rust, shell, sql, typescript, vim, xml, yaml };
for (const [name, sprache] of Object.entries(SPRACHEN)) hljs.registerLanguage(name, sprache);

/** Schlagwörter und Kürzel, die auf eine Sprache zeigen (Frage und Antwort: vimscript, neovim, python-3.x ...). */
const HINWEISE: Record<string, string> = {
  vim: "vim", vimscript: "vim", "vim-script": "vim", neovim: "vim", vimrc: "vim",
  javascript: "javascript", js: "javascript", "node.js": "javascript", nodejs: "javascript", typescript: "typescript",
  python: "python", "python-3.x": "python", python3: "python", php: "php", bash: "bash", shell: "bash", sh: "bash", zsh: "bash",
  json: "json", html: "xml", xml: "xml", css: "css", sql: "sql", mysql: "sql", postgresql: "sql", java: "java", c: "c",
  "c++": "cpp", cpp: "cpp", "c#": "csharp", go: "go", golang: "go", rust: "rust", ruby: "ruby", lua: "lua", yaml: "yaml",
  ini: "ini", diff: "diff", markdown: "markdown", powershell: "powershell", makefile: "makefile", dockerfile: "dockerfile",
};

/** Ohne Hinweis erkennt sich die Sprache nur unter diesen gängigen (seltene wie Ruby oder Lua verwechselt die Erkennung
 *  leicht mit Vim-Befehlen) und erst ab dieser Sicherheit; darunter bleibt der Block schlicht: lieber schlicht als falsch. */
const OHNE_HINWEIS = ["bash", "javascript", "typescript", "python", "json", "xml", "css", "sql", "vim", "php", "c", "cpp", "java", "yaml", "diff"];
const SICHER_AB = 10;

/** Die erste bekannte Sprache unter Hinweisen (Schlagwörter einer Frage); leer, wenn keins auf eine zeigt. */
export function spracheAus(woerter: string[]): string {
  for (const w of woerter) {
    const sprache = HINWEISE[w.trim().toLowerCase()];
    if (sprache) return sprache;
  }
  return "";
}

/** Färbt die Codeblöcke unter `wurzel`, die noch nicht gefärbt sind; Ausgaben und vom Backend Gefärbtes bleiben. */
export function codeEinfaerben(wurzel: HTMLElement, hinweis = ""): void {
  for (const pre of wurzel.querySelectorAll<HTMLElement>("pre")) {
    if (pre.dataset.gefaerbt || pre.classList.contains("ausgabe") || pre.querySelector("[class^='c-'], .hljs-keyword")) continue;
    const ziel = pre.querySelector<HTMLElement>("code") ?? pre;
    const text = ziel.textContent ?? "";
    if (!text.trim()) continue;
    const ergebnis = hinweis ? hljs.highlight(text, { language: hinweis, ignoreIllegals: true }) : hljs.highlightAuto(text, OHNE_HINWEIS);
    if (!hinweis && (ergebnis.relevance ?? 0) < SICHER_AB) {
      pre.dataset.gefaerbt = "schlicht";
      continue;
    }
    ziel.innerHTML = ergebnis.value;          // highlight.js maskiert den Text selbst; hinzu kommen nur seine span-Klassen
    pre.dataset.gefaerbt = ergebnis.language ?? hinweis;
  }
}
