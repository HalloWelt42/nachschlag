<script lang="ts">
  // Baustein Kachel (Karte) für alle Kartenarten der App, damit sie gleich gebaut sind: Bild (oben oder links) oder Zeichen,
  // Titel, Untertitel, eigener Inhalt, ein Fuß, der immer am Boden sitzt (Karten einer Reihe fluchten; die
  // Ansichtsprüfung misst das über data-karte und data-fuss), eine Ecke oben rechts (Flagge, Griff).
  //   art "hoch": Bild oben (Weiterlesen, Übersicht); "quer": Bild oder Zeichen links (Bücher, Artikel im Thema);
  //   "text": ohne Bild (Zufallsfund mit Knöpfen).
  // Mit `ziel` ist die ganze Karte ein Knopf (mit `adresse` ein Verweis, Mittelklick öffnet neu); ohne trägt sie ihre
  // Knöpfe selbst (im Fuß). Weitere Angaben (draggable, ondragstart ...) gehen an das Element der Karte.
  import type { Snippet } from "svelte";

  let {
    art = "hoch",
    bild = "",
    symbol = "fa-file-lines",
    zeichen,
    titel,
    untertitel = "",
    ziel,
    adresse = "",
    hinweis = "",
    gesperrt = false,
    class: klasse = "",
    vorsatz,
    ecke,
    children,
    fuss,
    ...rest
  }: {
    art?: "hoch" | "quer" | "text";
    bild?: string;
    symbol?: string;
    zeichen?: Snippet;                       // eigenes Zeichen statt `symbol` (etwa das Buchzeichen, WIKI-88)
    titel: string;
    untertitel?: string;
    ziel?: () => void;
    adresse?: string;
    hinweis?: string;
    gesperrt?: boolean;
    class?: string;
    vorsatz?: Snippet;
    ecke?: Snippet;
    children?: Snippet;
    fuss?: Snippet;
    [weitere: string]: unknown;
  } = $props();

  const element = $derived(adresse && ziel ? "a" : ziel ? "button" : "div");

  function tippen(e: MouseEvent) {
    if (!ziel || gesperrt) return;
    if (element === "a" && (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0)) return;   // neu öffnen bleibt dem Browser
    e.preventDefault();
    ziel();
  }
</script>

<svelte:element this={element} class="kachel {art} {klasse}" class:mit-ecke={!!ecke} data-karte title={hinweis || undefined}
                href={element === "a" ? adresse : undefined} type={element === "button" ? "button" : undefined}
                disabled={element === "button" ? gesperrt : undefined} onclick={tippen} {...rest}>
  {#if art !== "text"}
    <span class="kachel-bild" class:zeichen={!bild} class:echt={!bild && !!zeichen}>{#if bild}<img src={bild} alt="" loading="lazy" />{:else if zeichen}{@render zeichen()}{:else}<i class="fa-solid {symbol}"></i>{/if}</span>
  {/if}
  <span class="kachel-koerper">
    {#if vorsatz}{@render vorsatz()}{/if}
    <span class="kachel-titel">{titel}</span>
    {#if untertitel}<span class="kachel-unter">{untertitel}</span>{/if}
    {#if children}{@render children()}{/if}
    {#if fuss}<span class="kachel-fuss" data-fuss>{@render fuss()}</span>{/if}
  </span>
  {#if ecke}<span class="kachel-ecke">{@render ecke()}</span>{/if}
</svelte:element>
