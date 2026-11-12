<script lang="ts">
  // Suchergebnisse (Entwurf mockups/suche.html, WIKI-17 docs/SUCHE.md): jedes Buch wird für sich gefragt und zeigt
  // seinen Stand (sucht, fertig mit n Treffern, keine Antwort); die Treffer stehen nach Buch gruppiert, das Buch, aus
  // dem gesucht wurde, zuerst. Links die Bücher als Filter, rechts die Vorschau. Weg: /suche?frage=&buch=&nur=1
  // Englische Quellen fragt die Seite zusätzlich mit der Übersetzung der Frage (WIKI-40, Punkt 5): deren Treffer kommen
  // dazu, sobald die Übersetzung da ist; sie steht sichtbar über den Treffern und lässt sich ändern.
  // Suchkorrektur (WIKI-41, Punkt 9): sonst "Meintest du ...?" (aus dem Wortschatz), ohne Treffer sucht die Seite gleich mit der
  // Korrektur (?statt=) und sagt das; "Doch nach ... suchen" (?genau=1) sucht ohne Korrektur.
  import { gehe, navigation, seitenFehler } from "appkern-oberflaeche";
  import { onDestroy, untrack } from "svelte";
  import Suchfeld from "../teile/Suchfeld.svelte";
  import Buchmarke from "../teile/Buchmarke.svelte";
  import Wahlzeichen from "../teile/Wahlzeichen.svelte";
  import { bibliothek, bibliothekLaden, zahl, nutzbar } from "../lib/bibliothek.svelte";
  import { abschnittFuer, suchregelnLaden } from "../lib/suchregeln.svelte";
  import { artikelHolen, korrekturHolen, sucheHolen, uebersetzungHolen, uebersetzungKorrigieren, type Uebersetzung } from "../lib/schnittstelle";
  import type { Artikel, Buch, Suchergebnis, Treffer } from "../lib/typen";
  import { lesen, suchen } from "../lib/ziele";
  import { gesuchtMelden } from "../lib/meins.svelte";
  import { istCode } from "../lib/code";

  const JE_BUCH = 5;                          // Treffer je Buch in der Übersicht über alle Bücher
  const IM_KONTEXT = 10;                      // im Buch, aus dem gesucht wurde
  const NUR_EIN_BUCH = 40;                    // "nur in diesem Buch"

  interface Stand {
    stand: "sucht" | "fertig" | "fehler";
    ergebnis: Suchergebnis | null;       // was die Seite zeigt: die Treffer der Übersetzung zuerst, dann die übrigen
    ms: number;
    original?: Suchergebnis;
    uebersetzt?: Suchergebnis;
  }

  /** Beide Antworten eines Buchs zusammen: die Treffer der Übersetzung zuerst, jede Seite einmal. */
  function gemischt(st: Stand): Stand {
    const teile = [st.uebersetzt, st.original].filter((e): e is Suchergebnis => !!e);
    if (!teile.length) return st;
    const gesehen = new Set<string>();
    const treffer = teile.flatMap((e) => e.treffer).filter((t) => !gesehen.has(t.pfad) && !!gesehen.add(t.pfad));
    const basis = st.original ?? teile[0];
    return { ...st, ergebnis: { ...basis, treffer, index_gesamt: Math.max(...teile.map((e) => e.index_gesamt)) } };
  }

  const gleich = (a: string, b: string) => a.trim().toLowerCase() === b.trim().toLowerCase();

  let staende = $state.raw<Record<string, Stand>>({});
  let aus = $state<string[]>([]);             // abgewählte Bücher
  let gewaehlt = $state.raw<Treffer | null>(null);
  let vorschau = $state.raw<Artikel | null>(null);
  let fehler = $state("");
  let uebersetzung = $state.raw<Uebersetzung | null>(null);
  let uebersetzungGrund = $state("");
  let aendern = $state(false);
  let neuText = $state("");
  let nochmal = $state(0);                    // nach einer Korrektur der Übersetzung neu fragen
  let meintest = $state("");

  const zusatz = $derived(new URLSearchParams(navigation.suche));
  const frage = $derived(zusatz.get("frage") ?? "");
  const kontext = $derived(zusatz.get("buch") ?? "");
  const nur = $derived(zusatz.get("nur") === "1" && !!kontext);
  const statt = $derived(zusatz.get("statt") ?? "");          // korrigiert aus dieser Frage (sie fand nichts)
  const genau = $derived(zusatz.get("genau") === "1");        // ohne Korrektur, so wie getippt
  // was die Suche durchsuchen kann, sagt das Backend (Volltextindex der Datei oder eigener Index), ohne Archiv (WIKI-46)
  const durchsucht = $derived(bibliothek.buecher.filter((b) => b.durchsuchbar && nutzbar(b)));
  // Reihenfolge: das Buch, aus dem gesucht wurde, dann die übrigen wie in der Bibliothek
  // ohne Frage wird nichts gesucht: keine Quelle steht dann als "sucht" da (WIKI-92, Rückmeldung 12.11.)
  const reihenfolge = $derived.by((): Buch[] => {
    if (!frage) return [];
    const gewaehlte = durchsucht.filter((b) => !aus.includes(b.kennung) && (!nur || b.kennung === kontext));
    return [...gewaehlte.filter((b) => b.kennung === kontext), ...gewaehlte.filter((b) => b.kennung !== kontext)];
  });
  const mitTreffern = $derived(reihenfolge.filter((b) => staende[b.kennung]?.stand !== "fertig" || staende[b.kennung]?.ergebnis?.treffer.length));
  const ohneTreffer = $derived(reihenfolge.filter((b) => staende[b.kennung]?.stand === "fertig" && !staende[b.kennung]?.ergebnis?.treffer.length));
  const erledigt = $derived(reihenfolge.filter((b) => staende[b.kennung] && staende[b.kennung].stand !== "sucht").length);
  const fertig = $derived(reihenfolge.length > 0 && reihenfolge.every((b) => staende[b.kennung] && staende[b.kennung].stand !== "sucht"));
  const gesamt = $derived(reihenfolge.reduce((n, b) => n + (staende[b.kennung]?.ergebnis?.index_gesamt ?? 0), 0));
  const besteStelle = $derived(reihenfolge.map((b) => staende[b.kennung]?.ergebnis?.beste_stelle).find(Boolean) ?? null);
  const hinweisBedeutung = $derived(reihenfolge.map((b) => staende[b.kennung]?.ergebnis)
    .find((e) => e?.bedeutung_angebunden && e.nur_index && !e.bedeutung_ausstehend && e.hinweis)?.hinweis ?? "");
  // Bedeutungssuche läuft noch (WIKI-98): ihre Treffer kommen nach; danach die gemessene Dauer
  const bedeutungAusstehend = $derived(reihenfolge.some((b) => staende[b.kennung]?.original?.bedeutung_ausstehend));
  let nachgeliefert = $state<number | null>(null);

  // Eine neue Frage sucht in allen Quellen neu; eine geänderte Auswahl der Quellen holt nur die dazugekommenen (abgewählte
  // bleiben gemerkt und stehen beim Wiederanwählen gleich da). So bleibt die Seite beim An- und Abwählen ruhig (WIKI-103).
  let lauf: { schluessel: string; abruf: AbortController } | null = null;
  $effect(() => {
    const f = frage, buecher = reihenfolge.map((b) => b.kennung), k = kontext, n = nur;
    const schluessel = `${f}\n${k}\n${n}\n${nochmal}`;
    if (!f || !buecher.length) return;
    untrack(() => {
      if (lauf?.schluessel !== schluessel) {
        lauf?.abruf.abort();
        lauf = { schluessel, abruf: new AbortController() };
        void alleFragen(f, buecher, k, n, lauf.abruf.signal);
      } else {
        const neu = buecher.filter((b) => !staende[b]);
        if (neu.length) void dazuFragen(f, neu, buecher, k, n, lauf.abruf.signal);
      }
    });
  });
  onDestroy(() => lauf?.abruf.abort());

  const anzahlFuer = (k: string, n: boolean) => (b: string) => n ? NUR_EIN_BUCH : b === k ? IM_KONTEXT : JE_BUCH;
  const englischVon = (buecher: string[]) => buecher.filter((b) => bibliothek.buecher.find((x) => x.kennung === b)?.sprache === "eng");

  /** Eine Quelle fragen; ihr Stand steht danach in `staende`. `erste`: die Quelle, deren Treffer zuerst gewählt wird. */
  async function buchFragen(f: string, b: string, anzahl: (b: string) => number, erste: string, einzige: boolean, signal: AbortSignal) {
    const anfang = performance.now();
    try {
      const original = await sucheHolen(f, { buecher: [b], anzahl: anzahl(b) }, signal);
      if (signal.aborted) return;
      staende = { ...staende, [b]: gemischt({ ...staende[b], stand: "fertig", original, ms: Math.round(performance.now() - anfang) }) };
      if (original.bedeutung_ausstehend) void bedeutungNachliefern(f, b, anzahl(b), signal);
      const ergebnis = staende[b].ergebnis!;
      if (!gewaehlt && ergebnis.treffer[0] && (b === erste || !staende[erste]?.ergebnis?.treffer.length)) void waehlen(ergebnis.treffer[0]);
    } catch (e) {
      if (signal.aborted) return;
      staende = { ...staende, [b]: { stand: "fehler", ergebnis: null, ms: Math.round(performance.now() - anfang) } };
      if (einzige) fehler = seitenFehler(e);
    }
  }

  /** Quellen, die zur Auswahl dazukamen: nur sie fragen, englische auch mit der schon geholten Übersetzung. */
  async function dazuFragen(f: string, neu: string[], buecher: string[], k: string, n: boolean, signal: AbortSignal) {
    staende = { ...staende, ...Object.fromEntries(neu.map((b) => [b, { stand: "sucht", ergebnis: null, ms: 0 } as Stand])) };
    const anzahl = anzahlFuer(k, n);
    const u = uebersetzung;
    await Promise.all([...neu.map((b) => buchFragen(f, b, anzahl, buecher[0], false, signal)),
      ...(u && !gleich(u.text, f) ? englischVon(neu).map((b) => uebersetztIn(u.text, b, anzahl, signal)) : [])]);
  }

  /** Jedes Buch für sich: so steht ein schnelles Buch nicht hinter einem langsamen, und jedes zeigt seinen Stand. */
  async function alleFragen(f: string, buecher: string[], k: string, n: boolean, signal: AbortSignal) {
    fehler = "";
    gewaehlt = null;
    vorschau = null;
    navigation.titel = `Suche: ${f}`;
    staende = Object.fromEntries(buecher.map((b) => [b, { stand: "sucht", ergebnis: null, ms: 0 } as Stand]));
    uebersetzung = null;
    uebersetzungGrund = "";
    aendern = false;
    meintest = "";
    nachgeliefert = null;
    const englisch = englischVon(buecher);
    const anzahl = anzahlFuer(k, n);
    const uebersetzt = englisch.length ? uebersetztFragen(f, englisch, anzahl, signal) : Promise.resolve();
    await Promise.all([uebersetzt, ...buecher.map((b) => buchFragen(f, b, anzahl, buecher[0], buecher.length === 1, signal))]);
    if (signal.aborted) return;
    const summe = Object.values(staende).reduce((x, s) => x + (s.ergebnis?.index_gesamt ?? 0), 0);
    void gesuchtMelden(f, summe);
    if (!genau && !statt) void korrekturAnbieten(f, buecher, summe === 0, signal);
  }

  /** Die Bedeutungssuche antwortete nicht in der kurzen Wartezeit, läuft aber weiter: dieselbe Suche mit `nachliefern`
   *  wartet auf sie und bringt Index und Bedeutung gemischt; die Treffer des Buchs werden ersetzt (WIKI-98). */
  async function bedeutungNachliefern(f: string, b: string, n: number, signal: AbortSignal) {
    let original: Suchergebnis;
    try {
      original = await sucheHolen(f, { buecher: [b], anzahl: n, nachliefern: true }, signal);
    } catch {
      if (signal.aborted || !staende[b]?.original) return;
      original = { ...staende[b].original!, bedeutung_ausstehend: false, hinweis: "Bedeutungssuche antwortete nicht" };
    }
    if (signal.aborted) return;
    staende = { ...staende, [b]: gemischt({ ...staende[b], original }) };
    if (!original.nur_index) nachgeliefert = original.zeiten.bedeutung_ms;
  }

  /** Ein Vorschlag zum Antippen; ohne Treffer gleich mit der Korrektur suchen (die Seite sagt das), dann auch übers Modell. */
  async function korrekturAnbieten(f: string, buecher: string[], keine: boolean, signal: AbortSignal) {
    try {
      const k = await korrekturHolen(f, buecher, keine, signal);
      if (signal.aborted || !k.vorschlag) return;
      if (keine) weiterSuchen(k.vorschlag, { statt: f }, true);
      else meintest = k.vorschlag;
    } catch {
      // ohne Korrektur bleibt die Suche, wie sie ist
    }
  }

  function weiterSuchen(f: string, mehr: Record<string, string> = {}, ersetzen = false) {
    const p = new URLSearchParams({ frage: f, ...mehr });
    if (kontext) p.set("buch", kontext);
    if (nur) p.set("nur", "1");
    gehe(`suche?${p}`, ersetzen);
  }

  /** Die englischen Quellen noch einmal mit der Übersetzung; ohne Leitstelle steht der Grund über den Treffern. */
  async function uebersetztFragen(f: string, buecher: string[], anzahl: (b: string) => number, signal: AbortSignal) {
    let u: Uebersetzung;
    try {
      u = await uebersetzungHolen(f, signal);
    } catch (e) {
      if (!signal.aborted) uebersetzungGrund = seitenFehler(e);
      return;
    }
    if (signal.aborted) return;
    if (u.von === "keine") {
      uebersetzungGrund = u.grund;
      return;
    }
    uebersetzung = u;
    if (gleich(u.text, f)) return;
    await Promise.all(buecher.map((b) => uebersetztIn(u.text, b, anzahl, signal)));
  }

  /** Eine englische Quelle zusätzlich mit der übersetzten Frage. */
  async function uebersetztIn(text: string, b: string, anzahl: (b: string) => number, signal: AbortSignal) {
    try {
      const ergebnis = await sucheHolen(text, { buecher: [b], anzahl: anzahl(b) }, signal);
      if (!signal.aborted) staende = { ...staende, [b]: gemischt({ ...staende[b], uebersetzt: ergebnis }) };
    } catch {
      // die Treffer der Frage selbst bleiben
    }
  }

  async function korrigieren(e: SubmitEvent) {
    e.preventDefault();
    if (!neuText.trim()) return;
    try {
      await uebersetzungKorrigieren(frage, neuText.trim());
      nochmal += 1;
    } catch (x) {
      uebersetzungGrund = seitenFehler(x);
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
    lesen(t.buch, t.pfad, { frage, abschnitt: abschnittFuer(t.abschnitt), weg: t.wege.includes("bedeutung") ? "bedeutung" : "index" });
  }

  function umschalten(kennung: string) {
    aus = aus.includes(kennung) ? aus.filter((k) => k !== kennung) : [...aus, kennung];
  }

  const istHandbuch = (kennung: string) => bibliothek.buecher.find((b) => b.kennung === kennung)?.art === "dokumentation";

  $effect(() => void bibliothekLaden());

  void suchregelnLaden();      // ob Treffer an ihrer Stelle öffnen (Einstellung, WIKI-79)
</script>

<div class="inhalt-stufe" data-schrift="klein">
<div class="suchkopf">
  {#key frage}<Suchfeld gross wert={frage} />{/key}
  {#if frage && !bibliothek.geladen}
    <div class="suchstand"><span><i class="fa-solid fa-circle-notch fa-spin"></i> Quellen werden geladen ...</span></div>
  {/if}
  {#if frage && reihenfolge.length}
    <div class="suchstand">
      {#if nur}
        <span>Nur in <Buchmarke kennung={kontext} symbol={false} /></span>
        <button class="knopf still" onclick={() => suchen(frage, kontext)}><i class="fa-solid fa-swatchbook"></i>In allen Quellen suchen</button>
      {:else}
        <span>{#if fertig}{reihenfolge.length} {reihenfolge.length === 1 ? "Quelle" : "Quellen"} durchsucht, rund {zahl(gesamt)} Treffer{:else}Sucht in {reihenfolge.length} {reihenfolge.length === 1 ? "Quelle" : "Quellen"} ...{/if}</span>
      {/if}
    </div>
    <!-- Fortschritt über alle Quellen (WIKI-92): wächst mit jeder fertigen Quelle, schimmert, solange gesucht wird -->
    <!-- immer an seinem Platz, fertig unsichtbar: so springt nichts, wenn eine Suche beginnt oder endet -->
    <div class="suchfortschritt" class:ruht={fertig} role="progressbar" aria-label="Suche läuft" aria-hidden={fertig}
         aria-valuemin={0} aria-valuemax={reihenfolge.length} aria-valuenow={erledigt}>
      <b style:width="{Math.max(6, (erledigt / reihenfolge.length) * 100)}%"></b></div>
  {/if}
</div>
{#if bedeutungAusstehend}
  <div class="fundband"><i class="fa-solid fa-circle-notch fa-spin"></i>
    <span><b>Bedeutungssuche läuft noch.</b> Bis dahin Treffer aus dem Index; die passenden Stellen kommen nach.</span></div>
{:else if nachgeliefert !== null}
  <div class="fundband"><i class="fa-solid fa-wand-magic-sparkles"></i>
    <span>Treffer nach Bedeutung nachgeliefert, die Bedeutungssuche brauchte {(nachgeliefert / 1000).toLocaleString("de-DE", { maximumFractionDigits: 1 })} s.</span></div>
{/if}
{#if hinweisBedeutung}
  <div class="fundband warn"><i class="fa-solid fa-triangle-exclamation"></i>
    <span><b>Nur Index:</b> {hinweisBedeutung}. Treffer passen deshalb nur dem Wortlaut nach.</span></div>
{/if}
<!-- Suchkorrektur (WIKI-41) -->
{#if statt}
  <div class="fundband"><i class="fa-solid fa-spell-check"></i>
    <span>Keine Treffer für <b>{statt}</b>, gezeigt werden die für <b>{frage}</b>.</span>
    <button class="knopf still" onclick={() => weiterSuchen(statt, { genau: "1" })}>Doch nach {statt} suchen</button></div>
{:else if meintest}
  <div class="fundband"><i class="fa-solid fa-spell-check"></i>
    <span>Meintest du <button class="meintest" onclick={() => weiterSuchen(meintest)}>{meintest}</button>?</span></div>
{/if}
<!-- Übersetzte Suche (WIKI-40): womit die englischen Quellen zusätzlich gefragt werden, änderbar -->
{#if uebersetzung && !gleich(uebersetzung.text, frage)}
  <div class="fundband uebersetzt"><i class="fa-solid fa-language"></i>
    {#if aendern}
      <form class="uebersetzung-aendern" onsubmit={korrigieren}>
        <input name="neu-text" bind:value={neuText} aria-label="Übersetzung für die englischen Quellen" />
        <button class="knopf primaer" type="submit">Übernehmen</button>
        <button class="knopf still" type="button" onclick={() => (aendern = false)}>Abbrechen</button>
      </form>
    {:else}
      <span>Englische Quellen auch mit <b>{uebersetzung.text}</b>{uebersetzung.von === "nutzer" ? " (deine Übersetzung)" : ""}</span>
      <button class="knopf still" onclick={() => { neuText = uebersetzung!.text; aendern = true; }}><i class="fa-solid fa-pen"></i>Ändern</button>
    {/if}
  </div>
{:else if uebersetzungGrund}
  <div class="fundband"><i class="fa-solid fa-language"></i><span>Englische Quellen ohne Übersetzung: {uebersetzungGrund}</span></div>
{/if}
<div class="suchseite">
  <aside class="filterspalte">
    <div class="filtergruppe"><h4>Quellen</h4>
      {#each durchsucht as b (b.kennung)}
        {@const an = !aus.includes(b.kennung)}
        {@const st = frage && an ? staende[b.kennung] : undefined}
        <button class:an class:aus={!an} aria-pressed={an} onclick={() => umschalten(b.kennung)} title={an ? "Diese Quelle nicht durchsuchen" : "Diese Quelle durchsuchen"}>
          <Wahlzeichen {an} /><Buchmarke kennung={b.kennung} symbol={false} flaggeVorn />
          <!-- Stand je Quelle hier statt als eigene Reihe über den Treffern (docs/SUCHE.md Punkt 7, WIKI-103): sucht,
               keine Antwort oder die Zahl der Treffer, die Zeit beim Überfahren -->
          <span class="zahl" class:fehlt={st?.stand === "fehler"}
                title={st?.stand === "fertig" ? `${st.ms} ms` : st?.stand === "fehler" ? "keine Antwort" : st ? "sucht" : undefined}>
            {#if st?.stand === "sucht"}<i class="fa-solid fa-circle-notch fa-spin"></i>{:else if st?.stand === "fehler"}<i class="fa-solid fa-triangle-exclamation"></i>
            {:else if st?.ergebnis}{zahl(st.ergebnis.index_gesamt)}{/if}</span></button>
      {/each}
    </div>
  </aside>

  <div class="rollfeld" style="padding: 0">
    <div class="ergebnisse">
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
      {#if !frage}<p class="leer-hinweis">Oben eine Frage oder einen Begriff eingeben.</p>{/if}
      {#if besteStelle}
        {@const st = besteStelle}
        <div class="beste-stelle">
          <span class="fund-etikett"><i class="fa-solid fa-wand-magic-sparkles"></i>Beste Stelle</span>
          <span class="ort"><b>{st.titel}</b>{st.abschnitt ? ` · ${st.abschnitt}` : ""}</span>
          <blockquote>{@html st.ausschnitt}</blockquote>
          <div class="knopfreihe"><button class="knopf primaer" onclick={() => oeffnen(st)}><i class="fa-solid fa-arrow-down"></i>Zur Stelle</button></div>
        </div>
      {/if}
      {#each mitTreffern as b, i (b.kennung)}
        {@const st = staende[b.kennung]}
        {#if i > 0 && mitTreffern[i - 1].kennung === kontext && !nur}<div class="andere-buecher">In den anderen Quellen</div>{/if}
        <section class="buchtreffer">
          <div class="buchtreffer-kopf">
            <Buchmarke kennung={b.kennung} />
            {#if !st || st.stand === "sucht"}<span class="buchstand-text"><i class="fa-solid fa-spinner fa-spin"></i>sucht ...</span>
            {:else if st.stand === "fehler"}<span class="buchstand-text fehlt"><i class="fa-solid fa-triangle-exclamation"></i>keine Antwort</span>
            {:else}<span class="buchstand-text">rund {zahl(st.ergebnis?.index_gesamt ?? 0)} Treffer</span>{/if}
            {#if !nur && st?.stand === "fertig" && (st.ergebnis?.index_gesamt ?? 0) > (st.ergebnis?.treffer.length ?? 0)}
              <button class="alle" onclick={() => suchen(frage, b.kennung, true)}>Alle aus dieser Quelle</button>
            {/if}
          </div>
          {#each st?.ergebnis?.treffer ?? [] as t, ti (t.buch + t.pfad + ti)}
            <button class="treffer" class:gewaehlt={gewaehlt === t} onclick={() => oeffnen(t)} onmouseenter={() => gewaehlt !== t && waehlen(t)}>
              {#if t.bild}<img src={t.bild} alt="" loading="lazy" />{:else}<span class="ohne-bild"><i class="fa-solid fa-file-lines"></i></span>{/if}
              <span>
                <span class="zeile1"><span class="t" class:code={istHandbuch(t.buch) && istCode(t.titel)}>{t.titel}</span>
                  {#if t.abschnitt}<span class="treffer-abschnitt">› {t.abschnitt}</span>{/if}
                  <span class="marken">
                    {#if t.wege.includes("bedeutung")}<span class="weg-marke bedeutung"><i class="fa-solid fa-wand-magic-sparkles"></i>Bedeutung</span>{/if}
                    {#if t.wege.includes("index")}<span class="weg-marke index"><i class="fa-solid fa-magnifying-glass"></i>Index</span>{/if}
                  </span>
                </span>
                {#if t.frage}
                  <!-- Frage und Antwort: Zahlen der Frage aus dem eigenen Index (Trefferkarte je Buchart) -->
                  <span class="treffer-frage">
                    <span><b>{zahl(t.frage.stimmen)}</b>Stimmen</span>
                    <span class:akzeptiert={t.frage.akzeptiert}>{#if t.frage.akzeptiert}<i class="fa-solid fa-check"></i>{/if}<b>{t.frage.antworten}</b>{t.frage.antworten === 1 ? "Antwort" : "Antworten"}</span>
                    {#each t.frage.schlagwoerter.slice(0, 5) as s (s)}<span class="tf-wort">{s}</span>{/each}
                  </span>
                {/if}
                <!-- Ausschnitt vom Backend maskiert, nur die Fundwörter in <em> -->
                <span class="ausschnitt">{@html t.ausschnitt}</span>
              </span>
            </button>
          {/each}
          {#if !st || st.stand === "sucht"}
            <!-- Platzhalter in der Form der Treffer, bis die Quelle antwortet (WIKI-92) -->
            {#each [0, 1] as n (n)}
              <div class="treffer platzhalter" aria-hidden="true"><span class="ohne-bild"></span>
                <span class="zeilen"><span class="z1"></span><span class="z2"></span><span class="z3"></span></span></div>
            {/each}
          {/if}
        </section>
      {/each}
      {#if ohneTreffer.length}
        <p class="leer-hinweis">Keine Treffer in {#each ohneTreffer as b, i (b.kennung)}{i ? ", " : ""}<Buchmarke kennung={b.kennung} symbol={false} />{/each}.</p>
      {/if}
      {#if fertig && !mitTreffern.length}
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
          <div class="fund-etikett"><i class="fa-solid fa-list"></i>Abschnitte</div>
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
