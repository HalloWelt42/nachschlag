<script lang="ts">
  // Reiter Katalog der Bibliothek (WIKI-57, Entwurf katalog.html): das Verzeichnis der Bücher in den gewählten Sprachen,
  // je Buch seine Ausgaben (mit Bildern, ohne Bilder, klein) mit Stand, Größe, Neuheit und dem Stand zur eigenen
  // Bibliothek; abonnieren je Ausgabe. Neues seit der letzten Durchsicht steht oben; wer den Reiter öffnet, hat es gesehen.
  import { Auswahl, gehe, Nachladen, Seitenkopf, seitenFehler } from "appkern-oberflaeche";
  import { onMount, untrack } from "svelte";
  import { katalogZeichen } from "../lib/arten";
  import { buch, datum, zahl } from "../lib/bibliothek.svelte";
  import { AUSGABE, groesse, lader, laderLaden, monat, ZUSTAND } from "../lib/buecherlader.svelte";
  import { abbestellen, abonnieren, durchsichtStarten, neuesGesehen, verzeichnisHolen } from "../lib/schnittstelle";
  import type { Katalogfilter, Variante, Verzeichnisbuch } from "../lib/typen";
  import Ladebalken from "./Ladebalken.svelte";
  import Sprachmarke from "./Sprachmarke.svelte";
  import Buchzeichen from "./Buchzeichen.svelte";

  const ANZAHL = 60;
  const KUERZEL: Record<string, string> = { de: "deu", en: "eng", mul: "mul" };
  const SPRACHE: Record<string, string> = { de: "Deutsch", en: "Englisch", mul: "Mehrsprachige" };

  const GB = 1024 ** 3;
  const AUSGABEN = [{ wert: "", titel: "Alle Ausgaben" }, { wert: "maxi", titel: "Mit Bildern" }, { wert: "nopic", titel: "Ohne Bilder" },
                    { wert: "mini", titel: "Klein" }, { wert: "einzeln", titel: "Nur eine Ausgabe" }];
  const GROESSEN = [{ wert: "0", titel: "Jede Größe" }, { wert: String(100 * 1024 ** 2), titel: "Bis 100 MB" },
                    { wert: String(GB), titel: "Bis 1 GB" }, { wert: String(10 * GB), titel: "Bis 10 GB" },
                    { wert: String(50 * GB), titel: "Bis 50 GB" }];
  const BIBLIOTHEK = [{ wert: "", titel: "Ob da oder nicht" }, { wert: "da", titel: "In meiner Bibliothek" },
                      { wert: "nicht_da", titel: "Nicht in der Bibliothek" }, { wert: "neuer_da", titel: "Neuere Fassung da" }];
  const SORTIERUNGEN = [{ wert: "titel", titel: "Nach Titel" }, { wert: "neueste", titel: "Neueste zuerst" },
                        { wert: "groesste", titel: "Größte zuerst" }, { wert: "kleinste", titel: "Kleinste zuerst" }];

  let filter = $state<Katalogfilter>({ suche: "", bereich: "", sprache: "", ausgabe: "", groesse_bis: 0, bibliothek: "",
                                       nur_neu: false, nur_abonniert: false, kategorie: "", sortierung: "titel" });
  /** Das Buch in der Bibliothek, wenn eine Ausgabe dort liegt: seine Karte zeigt dann sein eigenes Symbol (WIKI-88). */
  const lokal = (b: Verzeichnisbuch) => {
    const v = b.varianten.find((x) => x.lokal_stand);
    return v ? buch(`${v.stamm}_${v.lokal_stand}`) : undefined;
  };
  let buecher = $state.raw<Verzeichnisbuch[]>([]);
  let bereiche = $state.raw<string[]>([]);
  let sprachen = $state.raw<string[]>([]);
  let kategorien = $state.raw<string[]>([]);
  let gesamt = $state(0);
  let laedt = $state(false);
  let fehler = $state("");
  let nachladefehler = $state("");
  let arbeitet = $state("");

  const stand = $derived(lader.stand);
  const durchgang = $derived(stand?.letzter_durchgang ?? null);
  const neu = $derived(durchgang && !durchgang.erstaufnahme ? durchgang.neue_buecher + durchgang.neue_fassungen : 0);

  onMount(() => {
    filter.nur_neu = (stand?.neu_ungesehen ?? 0) > 0;  // mit Ungesehenem zuerst das Neue
    void laderLaden().then(() => {
      if (lader.stand?.neu_ungesehen) void neuesGesehen().then(() => laderLaden(true));
    });
  });

  let zaehler = 0;
  async function laden(weiter = false) {
    const mein = ++zaehler;
    laedt = true;
    try {
      const s = await verzeichnisHolen($state.snapshot(filter), weiter ? buecher.length : 0, ANZAHL);
      if (mein !== zaehler) return;
      buecher = weiter ? [...buecher, ...s.eintraege] : s.eintraege;
      gesamt = s.gesamt;
      bereiche = s.bereiche;
      sprachen = s.sprachen;
      kategorien = s.kategorien;
      fehler = nachladefehler = "";
    } catch (f) {
      if (mein === zaehler && weiter) nachladefehler = seitenFehler(f);
      else if (mein === zaehler) fehler = seitenFehler(f);
    } finally {
      if (mein === zaehler) laedt = false;
    }
  }

  // Neu laden, wenn Filter wechseln (die Suche wartet kurz aufs Tippen) oder der Stand des Bücherladers neu kam
  let warten: ReturnType<typeof setTimeout> | undefined;
  $effect(() => {
    void [JSON.stringify(filter), lader.version];
    clearTimeout(warten);
    warten = setTimeout(() => untrack(() => void laden()), 200);
    return () => clearTimeout(warten);
  });

  async function tun(schluessel: string, arbeit: () => Promise<unknown>) {
    arbeitet = schluessel;
    try {
      await arbeit();
      fehler = "";
      await laderLaden(true);
    } catch (f) {
      fehler = seitenFehler(f);
    } finally {
      arbeitet = "";
    }
  }

  const kategoriewahl = $derived([{ wert: "", titel: "Alle Kategorien" }, ...kategorien.map((k) => ({ wert: k, titel: k.replace(/_/g, " ") }))]);
  const bereichwahl = $derived([{ wert: "", titel: "Alle Bereiche" }, ...bereiche.map((b) => ({ wert: b, titel: b.replace(/_/g, " ") }))]);
  const karteKlasse = (b: Verzeichnisbuch) => b.varianten.some((v) => v.zustand === "laedt") ? "laedt" : b.varianten.some((v) => v.abonniert) ? "abo" : "";
  const zustandText = (v: Variante) => v.zustand === "neuer_da" || v.zustand === "aktuell" ? `${ZUSTAND[v.zustand].text}, bei dir ${monat(v.lokal_stand)}` : ZUSTAND[v.zustand].text;
</script>

<Seitenkopf rand="var(--bib-rand)">
  {#snippet kopf()}
  <div class="katalog-filter">
    <label class="suchfeld katalog-suche"><i class="fa-solid fa-magnifying-glass"></i>
      <input name="suche" type="search" bind:value={filter.suche} placeholder="Im Katalog suchen" aria-label="Im Katalog suchen" /></label>
    {#if sprachen.length > 1}
      <div class="segment" role="radiogroup" aria-label="Sprache">
        <button class:aktiv={!filter.sprache} onclick={() => (filter.sprache = "")}>Alle Sprachen</button>
        {#each sprachen as s (s)}<button class:aktiv={filter.sprache === s} onclick={() => (filter.sprache = s)}>{SPRACHE[s] ?? s}</button>{/each}
      </div>
    {/if}
    <Auswahl wert={filter.bereich} symbol="fa-folder" titel="Bereich" optionen={bereichwahl} onwahl={(w: string) => (filter.bereich = w)} />
    {#if kategorien.length}
      <Auswahl wert={filter.kategorie} symbol="fa-tag" titel="Kategorie" optionen={kategoriewahl} onwahl={(w: string) => (filter.kategorie = w)} />
    {/if}
    <Auswahl wert={filter.ausgabe} symbol="fa-images" titel="Ausgabe" optionen={AUSGABEN}
             onwahl={(w: string) => (filter.ausgabe = w as Katalogfilter["ausgabe"])} />
    <Auswahl wert={String(filter.groesse_bis)} symbol="fa-weight-hanging" titel="Größe" optionen={GROESSEN}
             onwahl={(w: string) => (filter.groesse_bis = Number(w))} />
    <Auswahl wert={filter.bibliothek} symbol="fa-swatchbook" titel="Bibliothek" optionen={BIBLIOTHEK}
             onwahl={(w: string) => (filter.bibliothek = w as Katalogfilter["bibliothek"])} />
    <Auswahl wert={filter.sortierung} symbol="fa-arrow-down-wide-short" titel="Sortierung" optionen={SORTIERUNGEN}
             onwahl={(w: string) => (filter.sortierung = w as Katalogfilter["sortierung"])} />
    <button class="chip wahl" class:an={filter.nur_neu} onclick={() => (filter.nur_neu = !filter.nur_neu)}><i class="fa-solid fa-star"></i>Nur neue{#if neu} ({neu}){/if}</button>
    <button class="chip wahl" class:an={filter.nur_abonniert} onclick={() => (filter.nur_abonniert = !filter.nur_abonniert)}><i class="fa-solid fa-bell"></i>Nur abonnierte</button>
    {#if stand}
      <span class="hinweis">{stand.regeln.sprachen.map((s) => SPRACHE[s] ?? s).join(", ")}; andere Sprachen ausgeblendet
        (<a href="/einstellungen/buecherlader" onclick={(e) => { e.preventDefault(); gehe("einstellungen/buecherlader"); }}>Einstellungen</a>)</span>
    {/if}
  </div>
  {/snippet}
<div class="katalog-seite">
  {#if durchgang}
    <div class="ordnerzeile">
      <i class="fa-solid fa-clock-rotate-left"></i>
      <span>Durchgesehen am {datum(durchgang.begonnen.slice(0, 10))}: {zahl(durchgang.buecher)} Bücher in {durchgang.ordner} Bereichen
        {#if durchgang.erstaufnahme}(erste Durchsicht, alles bekannt){:else}, neu {durchgang.neue_buecher} {durchgang.neue_buecher === 1 ? "Buch" : "Bücher"}
          und {durchgang.neue_fassungen} {durchgang.neue_fassungen === 1 ? "Fassung" : "Fassungen"}{/if}</span>
      <span class="rechts"><span class="zahl">{zahl(gesamt)} passend</span></span>
    </div>
  {:else if stand}
    <div class="leer-gross katalog-leer">
      <i class="fa-solid fa-list-check"></i>
      <h2>Noch nicht durchgesehen</h2>
      <p>{stand.bereit ? "Der Bücherlader sieht das Verzeichnis der Bücher einmal durch; danach meldet er, was neu ist." : stand.grund}</p>
      {#if stand.bereit}<button class="knopf haupt" disabled={!!arbeitet} onclick={() => tun("durchsicht", durchsichtStarten)}>
        <i class="fa-solid fa-rotate"></i>Jetzt durchsehen</button>{/if}
    </div>
  {/if}
  {#if fehler}<div class="fehlertext">{fehler}</div>{/if}

  <div class="katalog-gitter">
    {#each buecher as b (b.basis)}
      {@const a = b.angaben}
      <div class="katkarte {karteKlasse(b)}" data-karte>
        <div class="kopf-k">
          <span class="sym"><Buchzeichen buch={lokal(b) ?? b} ersatz={katalogZeichen(a.kategorie, b.ordner)} /></span>
          <div>
            <span class="t">{b.titel}</span>
            <span class="u">{b.beschreibung ? `${b.beschreibung} · ` : ""}{b.ordner.replace(/_/g, " ")}</span>
          </div>
          <Sprachmarke kuerzel={KUERZEL[b.sprache] ?? b.sprache} />
        </div>
        <div class="werte-k">
          {#if a.artikel}<span><span class="zahl">{zahl(a.artikel)}</span> Artikel</span>{/if}
          {#if a.medien}<span><span class="zahl">{zahl(a.medien)}</span> Medien</span>{/if}
          {#if a.autor}<span title="Wer den Inhalt erstellt">von {a.autor}</span>{/if}
          {#if a.herausgeber && a.herausgeber !== a.autor}<span title="Wer die Datei erstellt">Datei: {a.herausgeber}</span>{/if}
          <span class="datei-k">{b.basis}</span>
        </div>
        {#if a.kategorie || a.schlagworte.length || a.bilder !== null || a.volltext !== null}
          <div class="angaben-k">
            {#if a.kategorie}<span class="faehigkeit"><i class="fa-solid fa-tag"></i>{a.kategorie.replace(/_/g, " ")}</span>{/if}
            {#if a.volltext}<span class="faehigkeit an"><i class="fa-solid fa-magnifying-glass"></i>Volltextindex</span>{/if}
            {#if a.bilder}<span class="faehigkeit an"><i class="fa-solid fa-image"></i>Bilder</span>{/if}
            {#if a.videos}<span class="faehigkeit an"><i class="fa-solid fa-film"></i>Videos</span>{/if}
            {#each a.schlagworte.slice(0, 6) as s (s)}<span class="schlagwort-k">{s}</span>{/each}
          </div>
        {/if}
        <div class="ausgabe-liste" data-fuss>
          {#each b.varianten as v (v.stamm)}
            <div class="ausgabe-zeile">
              <span class="name-a">{AUSGABE[v.ausgabe] ?? v.ausgabe}{#if v.neu}<span class="neu-fassung">{v.neu === "buch" ? "neu" : "neue Fassung"}</span>{/if}</span>
              <span class="zahl">{groesse(v.groesse)}</span>
              <span class="stand-a" title="aus so vielen Quellen ladbar">Stand {monat(v.stand)}{v.quellen > 1 ? ` · ${v.quellen} Quellen` : ""}</span>
              <span class="zustand-a {ZUSTAND[v.zustand].klasse}"><i class="fa-solid {ZUSTAND[v.zustand].symbol}"></i>{zustandText(v)}</span>
              {#if stand?.bereit}
                {#if v.abonniert}
                  <button class="knopf still" disabled={!!arbeitet} title="Keine neuen Fassungen mehr laden"
                          onclick={() => tun(v.stamm, () => abbestellen(v.stamm))}><i class="fa-solid fa-bell-slash"></i>Abo beenden</button>
                {:else}
                  <button class="knopf" disabled={!!arbeitet} title="Laden und künftig neue Fassungen holen"
                          onclick={() => tun(v.stamm, () => abonnieren(v.stamm))}><i class="fa-solid fa-bell"></i>Abonnieren</button>
                {/if}
              {/if}
              {#if v.zustand === "laedt"}<div class="ausgabe-laden"><Ladebalken stamm={v.stamm} /></div>{/if}
            </div>
          {/each}
        </div>
      </div>
    {/each}
  </div>
  {#if buecher.length}
    <!-- lädt beim Rollen von selbst nach (WIKI-60); der Knopf darin bleibt für die Tastatur -->
    <Nachladen geladen={buecher.length} {gesamt} {laedt} fehler={nachladefehler} onmehr={() => laden(true)} einheit="Bücher" />
  {:else if laedt}
    <div class="leer"><i class="fa-solid fa-spinner fa-spin"></i> lädt ...</div>
  {:else if durchgang && !buecher.length}
    <div class="leer">Nichts passt zu diesen Filtern.</div>
  {/if}
</div>
</Seitenkopf>
