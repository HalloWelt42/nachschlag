<script lang="ts">
  // Suchfeld mit Vorschlägen beim Tippen (Entwurf teile/vorschlaege.html): oben Titel aus dem Index der Bücher,
  // darunter passende Stellen aus der Bedeutungssuche (nur, wenn sie antwortet). Pfeiltasten wählen, Enter öffnet;
  // ohne Wahl führt Enter zur Suche mit allen Treffern. `gross`: Form der Startseite und der Suchseite; `taste`: die
  // Taste / setzt die Schreibmarke hierher (nur das Feld im Kopf).
  import { onMount } from "svelte";
  import { sucheHolen, vorschlaegeHolen } from "../lib/schnittstelle";
  import type { Treffer, Vorschlag } from "../lib/typen";
  import { buchName } from "../lib/bibliothek.svelte";
  import { kontextBuch } from "../lib/suchkontext";
  import { lesen, suchen } from "../lib/ziele";
  import Buchmarke from "./Buchmarke.svelte";

  let { gross = false, taste = false, wert = "", platzhalter = "Begriff, Name oder eine Frage in eigenen Worten" }:
    { gross?: boolean; taste?: boolean; wert?: string; platzhalter?: string } = $props();

  const TITEL_WARTEN_MS = 120;
  const STELLEN_WARTEN_MS = 380;
  const STELLEN_AB_ZEICHEN = 4;

  let frage = $state("");
  let offen = $state(false);
  let gewaehlt = $state(-1);
  let titel = $state.raw<Vorschlag[]>([]);
  let stellen = $state.raw<Treffer[]>([]);
  let feld: HTMLInputElement;
  let titelUhr: ReturnType<typeof setTimeout> | undefined;
  let stellenUhr: ReturnType<typeof setTimeout> | undefined;
  let titelAbruf: AbortController | undefined;
  let stellenAbruf: AbortController | undefined;

  $effect(() => {
    frage = wert;
  });

  // Im Buch: seine Treffer zuerst (ein Tipp auf die Marke sucht für diese Frage in allen gleich)
  let ohneKontext = $state(false);
  const kontext = $derived(ohneKontext ? "" : kontextBuch());
  $effect(() => {
    void kontextBuch();
    ohneKontext = false;                                  // neuer Ort: wieder mit seinem Buch
  });

  const eintraege = $derived([...titel.map((v) => ({ art: "titel" as const, v })), ...stellen.map((t) => ({ art: "stelle" as const, t }))]);

  function teile(text: string, suche: string): { text: string; treffer: boolean }[] {
    const s = suche.trim().toLowerCase();
    const i = s ? text.toLowerCase().indexOf(s) : -1;
    if (i < 0) return [{ text, treffer: false }];
    return [{ text: text.slice(0, i), treffer: false }, { text: text.slice(i, i + s.length), treffer: true },
            { text: text.slice(i + s.length), treffer: false }].filter((t) => t.text);
  }

  function eingabe() {
    gewaehlt = -1;
    offen = true;
    clearTimeout(titelUhr);
    clearTimeout(stellenUhr);
    const jetzt = frage.trim();
    if (!jetzt) {
      titel = [];
      stellen = [];
      return;
    }
    titelUhr = setTimeout(async () => {
      titelAbruf?.abort();
      titelAbruf = new AbortController();
      try {
        const vorschlaege = await vorschlaegeHolen(jetzt, [], 6, titelAbruf.signal);
        // Titel aus dem Buch, in dem man ist, zuerst; sonst bleibt die Folge des Index
        titel = kontext ? [...vorschlaege.filter((v) => v.buch === kontext), ...vorschlaege.filter((v) => v.buch !== kontext)] : vorschlaege;
      } catch {
        /* abgebrochen oder ohne Antwort: die Liste bleibt, wie sie war */
      }
    }, TITEL_WARTEN_MS);
    if (jetzt.length < STELLEN_AB_ZEICHEN) {
      stellen = [];
      return;
    }
    stellenUhr = setTimeout(async () => {
      stellenAbruf?.abort();
      stellenAbruf = new AbortController();
      try {
        const ergebnis = await sucheHolen(jetzt, { wege: "bedeutung", anzahl: 3 }, stellenAbruf.signal);
        stellen = ergebnis.nur_index ? [] : ergebnis.treffer;
      } catch {
        stellen = [];
      }
    }, STELLEN_WARTEN_MS);
  }

  function schliessen() {
    offen = false;
    gewaehlt = -1;
  }

  function oeffnen(i: number) {
    const e = eintraege[i];
    if (!e) return;
    const gesucht = frage.trim();
    schliessen();
    feld.blur();
    frage = wert;                     // das Feld zeigt wieder, was zur Seite gehört (im Kopf: nichts)
    if (e.art === "titel") {
      const [pfad, anker = ""] = (e.v.weiterleitung || e.v.pfad).split("#");
      lesen(e.v.buch, pfad, {}, anker);
    } else {
      lesen(e.t.buch, e.t.pfad, { frage: gesucht, abschnitt: e.t.abschnitt, weg: "bedeutung" });
    }
  }

  function alleTreffer() {
    const gesucht = frage.trim();
    if (!gesucht) return;
    schliessen();
    feld.blur();
    frage = wert;
    suchen(gesucht, kontext);
  }

  function tasten(e: KeyboardEvent) {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      offen = true;
      const n = eintraege.length;
      if (n) gewaehlt = e.key === "ArrowDown" ? (gewaehlt + 1) % n : (gewaehlt - 1 + n) % n;
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (gewaehlt >= 0) oeffnen(gewaehlt);
      else alleTreffer();
    } else if (e.key === "Escape") {
      schliessen();
    }
  }

  onMount(() => {
    if (!taste) return;
    const schreibmarke = (e: KeyboardEvent) => {
      const ziel = e.target as HTMLElement | null;
      if (e.key !== "/" || ziel?.closest("input, textarea, [contenteditable]")) return;
      e.preventDefault();
      feld.focus();
      feld.select();
    };
    addEventListener("keydown", schreibmarke);
    return () => removeEventListener("keydown", schreibmarke);
  });
</script>

<div class="suchanker" class:grosssuche={gross} class:offen={offen && frage.trim()}>
  <label class="suchfeld">
    <i class="fa-solid fa-magnifying-glass"></i>
    <input bind:this={feld} bind:value={frage} type="search" placeholder={platzhalter} autocomplete="off" spellcheck="false"
           aria-label="Suchen" oninput={eingabe} onkeydown={tasten} onfocus={() => (offen = true)} onblur={schliessen} />
    {#if kontext}
      <button type="button" class="buchwahl mit-buch" title="Treffer aus dieser Quelle zuerst; antippen: alle Quellen gleich"
              onmousedown={(e) => e.preventDefault()} onclick={() => (ohneKontext = true)}>
        <Buchmarke kennung={kontext} symbol={false} /><span class="zuerst">zuerst</span><i class="fa-solid fa-xmark"></i></button>
    {:else}
      <span class="buchwahl" title="Gesucht wird in allen Quellen"><i class="fa-solid fa-book"></i>Alle Quellen</span>
    {/if}
    {#if taste}<kbd title="Taste / setzt die Schreibmarke ins Suchfeld">/</kbd>{/if}
  </label>
  {#if offen && frage.trim()}
    <!-- Auswahl mit der Maus ohne den Fokus zu verlieren (sonst schließt das Feld vor dem Klick) -->
    <div class="vorschlaege" role="listbox" tabindex="-1" onmousedown={(e) => e.preventDefault()}>
      {#if titel.length}
        <div class="gruppe"><i class="fa-solid fa-book"></i>Artikel</div>
        {#each titel as v, i (v.buch + v.pfad)}
          <div class="vorschlag" class:gewaehlt={gewaehlt === i} role="option" aria-selected={gewaehlt === i} tabindex="-1"
               onclick={() => oeffnen(i)} onkeydown={() => {}} onmouseenter={() => (gewaehlt = i)}>
            <span class="ohne-bild"><i class="fa-solid {v.weiterleitung ? 'fa-share' : 'fa-file-lines'}"></i></span>
            <span>
              <span class="t">{#each teile(v.titel, frage) as t}{#if t.treffer}<em>{t.text}</em>{:else}{t.text}{/if}{/each}</span>
              <span class="u">{v.weiterleitung ? `führt zu ${v.weiterleitung.replace("#", ", Abschnitt ").replaceAll("_", " ")}`
                : v.kurztext || buchName(v.buch)}</span>
            </span>
            <span class="art">{v.weiterleitung ? "Weiterleitung" : "Artikel"}</span>
          </div>
        {/each}
      {/if}
      {#if stellen.length}
        <div class="gruppe"><i class="fa-solid fa-wand-magic-sparkles"></i>Passende Stellen<span class="weg">Bedeutung</span></div>
        {#each stellen as t, j (t.buch + t.pfad + t.abschnitt + j)}
          {@const i = titel.length + j}
          <div class="stelle" class:gewaehlt={gewaehlt === i} role="option" aria-selected={gewaehlt === i} tabindex="-1"
               onclick={() => oeffnen(i)} onkeydown={() => {}} onmouseenter={() => (gewaehlt = i)}>
            <span class="sym"><i class="fa-solid fa-paragraph"></i></span>
            <span><span class="ort"><b>{t.titel}</b>{t.abschnitt ? ` · ${t.abschnitt}` : ""}</span>
              <span class="satz">{@html t.ausschnitt}</span></span>
          </div>
        {/each}
      {/if}
      {#if !titel.length && !stellen.length}<div class="leer">Kein Titel beginnt so. Enter sucht im Text aller Quellen.</div>{/if}
      <div class="fuss-zeile">
        <span><kbd>↑</kbd> <kbd>↓</kbd> wählen</span><span><kbd>Enter</kbd> öffnen</span><span><kbd>Esc</kbd> schließen</span>
        <span class="rechts" role="button" tabindex="-1" onclick={alleTreffer} onkeydown={() => {}}>Alle Treffer zeigen</span>
      </div>
    </div>
  {/if}
</div>
