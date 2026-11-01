<script lang="ts">
  // Suchergebnisse (Entwurf mockups/suche.html): Bücher als Filter links, Treffer in der Mitte mit dem Weg, der sie
  // fand, rechts die Vorschau des gewählten Treffers. Antwortet die Bedeutungssuche nicht, sagt das ein Band und die
  // Treffer kommen aus dem Index allein. Weg: /suche?frage=...
  import { navigation, seitenFehler } from "appkern-oberflaeche";
  import { untrack } from "svelte";
  import Suchfeld from "../teile/Suchfeld.svelte";
  import { bezeichnung, bibliothek, bibliothekLaden, buchName, zahl } from "../lib/bibliothek.svelte";
  import { artikelHolen, sucheHolen } from "../lib/schnittstelle";
  import type { Artikel, Suchergebnis, Treffer } from "../lib/typen";
  import { lesen } from "../lib/ziele";

  const ANZAHL = 30;

  // Antworten der Schnittstelle nur lesen (roh, ohne Proxy: Vergleiche über Treffer gelten dann)
  let ergebnis = $state.raw<Suchergebnis | null>(null);
  let fehler = $state("");
  let laedt = $state(false);
  let aus = $state<string[]>([]);               // abgewählte Bücher
  let gewaehlt = $state.raw<Treffer | null>(null);
  let vorschau = $state.raw<Artikel | null>(null);

  const frage = $derived(new URLSearchParams(navigation.suche).get("frage") ?? "");
  const durchsucht = $derived(bibliothek.buecher.filter((b) => b.faehigkeiten.volltext));
  const gewaehlteBuecher = $derived(aus.length ? durchsucht.filter((b) => !aus.includes(b.kennung)).map((b) => b.kennung) : []);
  const jeBuch = $derived.by(() => {
    const zahlen: Record<string, number> = {};
    for (const t of ergebnis?.treffer ?? []) zahlen[t.buch] = (zahlen[t.buch] ?? 0) + 1;
    return zahlen;
  });

  $effect(() => {
    const f = frage, buecher = gewaehlteBuecher;
    if (!f) return;
    const abruf = new AbortController();
    untrack(() => laden(f, buecher, abruf.signal));
    return () => abruf.abort();
  });

  async function laden(f: string, buecher: string[], signal: AbortSignal) {
    laedt = true;
    fehler = "";
    void bibliothekLaden();
    try {
      const neu = await sucheHolen(f, { buecher, anzahl: ANZAHL }, signal);
      ergebnis = neu;
      navigation.titel = `Suche: ${f}`;
      if (neu.treffer[0]) waehlen(neu.treffer[0]);
    } catch (e) {
      if (!signal.aborted) fehler = seitenFehler(e);
    } finally {
      if (!signal.aborted) laedt = false;
    }
  }

  async function waehlen(t: Treffer) {
    gewaehlt = t;
    try {
      const a = await artikelHolen(t.buch, t.pfad);
      if (gewaehlt === t) vorschau = a;
    } catch {
      if (gewaehlt === t) vorschau = null;
    }
  }

  function oeffnen(t: Treffer) {
    lesen(t.buch, t.pfad, { frage, abschnitt: t.abschnitt, weg: t.wege.includes("bedeutung") ? "bedeutung" : "index" });
  }

  function umschalten(kennung: string) {
    aus = aus.includes(kennung) ? aus.filter((k) => k !== kennung) : [...aus, kennung];
  }
</script>

<div class="inhalt-stufe" data-schrift="klein">
<div class="suchkopf">
  {#key frage}<Suchfeld gross wert={frage} />{/key}
  {#if ergebnis}
    <div class="suchstand">
      {#if !ergebnis.nur_index}
        <span><span class="weg-marke bedeutung"><i class="fa-solid fa-wand-magic-sparkles"></i>Bedeutung</span>
          <span class="zahl">{ergebnis.zeiten.bedeutung_ms} ms</span></span>
      {/if}
      <span><span class="weg-marke index"><i class="fa-solid fa-magnifying-glass"></i>Index</span> rund
        <span class="zahl">{zahl(ergebnis.index_gesamt)}</span> Artikel · <span class="zahl">{ergebnis.zeiten.index_ms} ms</span></span>
      <span>{ergebnis.nur_index ? "sortiert nach Index" : "gemischt nach Rang beider Wege"}</span>
      {#if laedt}<span>sucht ...</span>{/if}
    </div>
  {/if}
</div>
{#if ergebnis?.nur_index && ergebnis.bedeutung_angebunden && ergebnis.hinweis}
  <div class="fundband warn"><i class="fa-solid fa-triangle-exclamation"></i>
    <span><b>Nur Index:</b> {ergebnis.hinweis}. Treffer passen deshalb nur dem Wortlaut nach.</span></div>
{/if}
<div class="suchseite">
  <aside class="filterspalte">
    <div class="filtergruppe"><h4>Bücher</h4>
      {#each durchsucht as b (b.kennung)}
        {@const an = !aus.includes(b.kennung)}
        <button class:an class:aus={!an} onclick={() => umschalten(b.kennung)} title={an ? "Dieses Buch nicht durchsuchen" : "Dieses Buch durchsuchen"}>
          <i class="fa-{an ? 'solid fa-square-check' : 'regular fa-square'}"></i>{bezeichnung(b)}
          <span class="zahl">{jeBuch[b.kennung] ?? 0}</span></button>
      {/each}
    </div>
  </aside>

  <div class="rollfeld" style="padding: 0">
    <div class="ergebnisse">
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
      {#if !frage}<p class="leer-hinweis">Oben eine Frage oder einen Begriff eingeben.</p>{/if}
      {#if ergebnis?.beste_stelle}
        {@const s = ergebnis.beste_stelle}
        <div class="beste-stelle">
          <span class="etikett"><i class="fa-solid fa-wand-magic-sparkles"></i>Beste Stelle</span>
          <span class="ort"><b>{s.titel}</b>{s.abschnitt ? ` · ${s.abschnitt}` : ""}</span>
          <blockquote>{@html s.ausschnitt}</blockquote>
          <div class="knopfreihe"><button class="knopf primaer" onclick={() => oeffnen(s)}><i class="fa-solid fa-arrow-down"></i>Zur Stelle</button></div>
        </div>
      {/if}
      {#each ergebnis?.treffer ?? [] as t, i (t.buch + t.pfad + i)}
        <button class="treffer" class:gewaehlt={gewaehlt === t} onclick={() => oeffnen(t)} onmouseenter={() => gewaehlt !== t && waehlen(t)}>
          <span class="ohne-bild"><i class="fa-solid fa-file-lines"></i></span>
          <span>
            <span class="zeile1"><span class="t">{t.titel}</span>
              {#if t.abschnitt}<span class="treffer-abschnitt">› {t.abschnitt}</span>{/if}
              <span class="buchname">{buchName(t.buch)}</span>
              <span class="marken">
                {#if t.wege.includes("bedeutung")}<span class="weg-marke bedeutung"><i class="fa-solid fa-wand-magic-sparkles"></i>Bedeutung</span>{/if}
                {#if t.wege.includes("index")}<span class="weg-marke index"><i class="fa-solid fa-magnifying-glass"></i>Index</span>{/if}
              </span>
            </span>
            <!-- Ausschnitt vom Backend maskiert, nur die Fundwörter in <em> -->
            <span class="ausschnitt">{@html t.ausschnitt}</span>
          </span>
        </button>
      {/each}
      {#if ergebnis && !ergebnis.treffer.length && !laedt}
        <p class="leer-hinweis">Keine Treffer zu "{frage}". Andere Wörter oder eine Frage in eigenen Worten helfen oft.</p>
      {/if}
    </div>
  </div>

  <aside class="vorschau-leiste">
    {#if vorschau && gewaehlt}
      {@const t = gewaehlt}
      <div class="rollfeld">
        <h2>{vorschau.titel}</h2>
        <p>{vorschau.einleitung}</p>
        {#if vorschau.abschnitte.length}
          <div class="etikett"><i class="fa-solid fa-list"></i>Abschnitte</div>
          <div class="abschnitte">
            {#each vorschau.abschnitte.filter((a) => a.ebene === 2) as a (a.anker)}
              <button class:treff={a.titel === t.abschnitt} onclick={() => lesen(t.buch, t.pfad, { frage }, a.anker)}>
                <span>{a.titel}</span>{#if a.titel === t.abschnitt}<span class="weg-marke bedeutung">Fundstelle</span>{/if}</button>
            {/each}
          </div>
        {/if}
        <div class="knopfreihe"><button class="knopf primaer" onclick={() => oeffnen(t)}><i class="fa-solid fa-book-open"></i>Öffnen</button></div>
      </div>
    {/if}
  </aside>
</div>
</div>
