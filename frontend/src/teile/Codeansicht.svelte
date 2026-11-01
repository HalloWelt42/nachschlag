<script lang="ts">
  // Codeansicht (WIKI-30): ein Codeblock über den ganzen Schirm, ohne Umbruch und seitlich rollbar, mit Zeilennummern,
  // Kopieren und eigener Schriftgröße (je Gerät gemerkt). Im Querformat nutzt sie die volle Breite, Kopf und Leisten
  // der App treten zurück. Im Artikel bleibt der Umbruch (die Seite rollt nie seitlich). Escape oder Schließen gehen
  // zurück.
  import { kopieren } from "appkern-oberflaeche";
  import { RUECKMELDUNG_MS } from "../lib/zitat";

  let { html, text, sprache = "", onzu }: { html: string; text: string; sprache?: string; onzu: () => void } = $props();

  const GROESSEN = [70, 80, 90, 100, 115, 130, 150];      // Prozent der Grundschrift
  const VORGABE = 90;
  const SCHLUESSEL = "nachschlag.codegroesse";

  function gemerkt(): number {
    try {
      const w = Number(localStorage.getItem(SCHLUESSEL));
      return GROESSEN.includes(w) ? w : VORGABE;
    } catch {
      return VORGABE;
    }
  }

  let stufe = $state(gemerkt());
  let kopiert = $state<"" | "ja" | "nein">("");
  const zeilen = $derived(text.replace(/\n$/, "").split("\n").length);
  const nummern = $derived(Array.from({ length: zeilen }, (_, i) => i + 1).join("\n"));

  function groesser(schritt: 1 | -1) {
    stufe = GROESSEN[Math.min(GROESSEN.length - 1, Math.max(0, GROESSEN.indexOf(stufe) + schritt))];
    try {
      localStorage.setItem(SCHLUESSEL, String(stufe));
    } catch {
      // ohne Speicher gilt die Größe nur jetzt
    }
  }

  async function kopierenKlick() {
    kopiert = (await kopieren(text)) ? "ja" : "nein";
    setTimeout(() => (kopiert = ""), RUECKMELDUNG_MS);
  }
</script>

<svelte:window onkeydown={(e) => e.key === "Escape" && onzu()} />
<div class="codeansicht" role="dialog" aria-label="Code groß">
  <div class="codeansicht-kopf">
    <span class="was"><b>{sprache || "Code"}</b><span class="neben">{zeilen} {zeilen === 1 ? "Zeile" : "Zeilen"}</span></span>
    <button class="knopf still" aria-label="Schrift kleiner" disabled={stufe === GROESSEN[0]} onclick={() => groesser(-1)}>
      <i class="fa-solid fa-magnifying-glass-minus"></i></button>
    <button class="knopf still" aria-label="Schrift größer" disabled={stufe === GROESSEN[GROESSEN.length - 1]} onclick={() => groesser(1)}>
      <i class="fa-solid fa-magnifying-glass-plus"></i></button>
    <button class="knopf" class:kopiert-ok={kopiert === "ja"} onclick={kopierenKlick}>
      <i class="fa-solid {kopiert === 'ja' ? 'fa-check' : kopiert === 'nein' ? 'fa-triangle-exclamation' : 'fa-copy'}"></i>{kopiert === "ja" ? "Kopiert" : kopiert === "nein" ? "Geht nicht" : "Kopieren"}</button>
    <button class="knopf primaer" onclick={onzu}><i class="fa-solid fa-xmark"></i>Schließen</button>
  </div>
  <div class="codeansicht-rumpf" style:font-size="{stufe}%">
    <pre class="codeansicht-nummern" aria-hidden="true">{nummern}</pre>
    <!-- derselbe Inhalt wie im Artikel (dort schon gesäubert und eingefärbt) -->
    <pre class="codeansicht-code">{@html html}</pre>
  </div>
</div>
