<script lang="ts">
  // Stöbern (Entwurf mockups/stoebern.html): drei Arten zu blättern. Zufall mit Filtern (Leertaste für den nächsten),
  // der Entdeckungspfad (von hier weiter über Verweise, Nennungen und Bedeutung; der Weg bleibt sichtbar) und Blättern
  // wie im gedruckten Lexikon (Titel in der Reihenfolge des Buchs um den Fund herum).
  import { onMount } from "svelte";
  import { Auswahl, gehe, geraet, seitenFehler } from "appkern-oberflaeche";
  import { bezeichnung, bibliothek, bibliothekLaden, hauptbuch } from "../lib/bibliothek.svelte";
  import { gemerkt, meins, meinsLaden, merken, vergessen, vorliebeSetzen } from "../lib/meins.svelte";
  import { EBEN_HOECHSTENS, fundHolen, schrittHolen, seiteHolen, stoebern, zufallHolen, type Fund, type Nachbar } from "../lib/stoebern.svelte";
  import { eintragen, themaAnlegen, themenVon } from "../lib/themen.svelte";
  import { lesen } from "../lib/ziele";

  const BUCHSTABEN = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

  let fehler = $state("");
  let zieht = $state(false);
  let schrittLaedt = $state(false);

  const buecher = $derived(bibliothek.buecher.filter((b) => b.faehigkeiten.lesedesign));
  const buch = $derived(bibliothek.buecher.find((b) => b.kennung === stoebern.buch));

  async function zufall() {
    if (!stoebern.buch || zieht) return;
    zieht = true;
    try {
      const neu = await zufallHolen(stoebern.buch, stoebern.mitBild, stoebern.ungelesen);
      if (stoebern.fund) stoebern.eben = [stoebern.fund, ...stoebern.eben.filter((f) => f.pfad !== stoebern.fund!.pfad)].slice(0, EBEN_HOECHSTENS);
      stoebern.fund = neu;
      fehler = "";
      void blaettern({ um: neu.pfad });
    } catch (f) {
      fehler = seitenFehler(f);
    } finally {
      zieht = false;
    }
  }

  const BUCH_VORLIEBE = "stoebern:buch";                 // gewähltes Buch, auf allen Geräten (Name ohne Datum)

  function buchWaehlen(kennung: string) {
    stoebern.buch = kennung;
    const b = bibliothek.buecher.find((x) => x.kennung === kennung);
    if (b) void vorliebeSetzen(BUCH_VORLIEBE, b.name);
    stoebern.fund = null;
    stoebern.eben = [];
    stoebern.pfad = [];
    stoebern.schritt = null;
    stoebern.seite = null;
    stoebern.vorschau = null;
    void zufall();
  }

  function filterUmschalten(welcher: "mitBild" | "ungelesen") {
    stoebern[welcher] = !stoebern[welcher];
    void zufall();
  }

  // --- Entdeckungspfad -----------------------------------------------------------------------------------------
  async function schrittZu(pfad: string, bisher: Fund[]) {
    schrittLaedt = true;
    try {
      const s = await schrittHolen(stoebern.buch, pfad);
      stoebern.schritt = s;
      stoebern.pfad = [...bisher, s.fund];
      fehler = "";
    } catch (f) {
      fehler = seitenFehler(f);
    } finally {
      schrittLaedt = false;
    }
  }

  const vonHier = (f: Fund) => schrittZu(f.pfad, []);
  const weiter = (n: Nachbar) => schrittZu(n.pfad, stoebern.pfad);
  const zurueckZu = (i: number) => schrittZu(stoebern.pfad[i].pfad, stoebern.pfad.slice(0, i));

  async function pfadAlsThema() {
    if (!stoebern.pfad.length) return;
    try {
      const t = await themaAnlegen(`Pfad ab ${stoebern.pfad[0].titel}`);
      for (const f of stoebern.pfad) await eintragen(t.id, { buch: f.buch, pfad: f.pfad, titel: f.titel, bild: f.bild });
      gehe(`themen/${t.id}`);
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  // --- Blättern wie im Buch ------------------------------------------------------------------------------------
  async function blaettern(wo: { um?: string; buchstabe?: string; ab?: number; bis?: number }) {
    if (!stoebern.buch) return;
    try {
      const seite = await seiteHolen(stoebern.buch, wo);
      stoebern.seite = seite;
      stoebern.buchstabe = wo.buchstabe ?? (seite.eintraege[0]?.titel[0] ?? "").toUpperCase();
      const zeigen = seite.hier || seite.eintraege[0]?.pfad;
      if (zeigen && zeigen !== stoebern.vorschau?.pfad) void vorschauZu(zeigen);
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  async function vorschauZu(pfad: string) {
    try {
      stoebern.vorschau = stoebern.fund?.pfad === pfad ? stoebern.fund : await fundHolen(stoebern.buch, pfad);
    } catch {
      stoebern.vorschau = null;
    }
  }

  // --- Merken (wie im Artikel) --------------------------------------------------------------------------------
  const merkeintrag = (f: Fund) => (buch ? gemerkt(buch.name, f.pfad) : undefined);

  async function merkenUmschalten(f: Fund) {
    try {
      const e = merkeintrag(f);
      if (e) await vergessen(e.id);
      else await merken(f.buch, f.pfad, f.titel, f.bild);
    } catch (x) {
      fehler = seitenFehler(x);
    }
  }

  /** Was man über einen früheren Fund weiß (Entwurf: gemerkt, zum Thema gelegt). */
  function ebenStand(f: Fund): string {
    const themen = buch ? themenVon(buch.name, f.pfad) : [];
    if (themen.length) return `im Thema ${themen[0].titel}`;
    if (merkeintrag(f)) return "gemerkt";
    return f.auszug.slice(0, 80);
  }

  function taste(e: KeyboardEvent) {
    const ziel = e.target as HTMLElement;
    if (e.key !== " " || ziel.closest("input, textarea, button, [contenteditable]")) return;
    e.preventDefault();
    void zufall();
  }

  onMount(async () => {
    await Promise.all([bibliothekLaden(), meinsLaden()]);
    if (!stoebern.buch) {
      const gewaehlt = buecher.filter((b) => b.name === meins.vorlieben[BUCH_VORLIEBE]).sort((a, b) => b.stand.localeCompare(a.stand))[0];
      stoebern.buch = gewaehlt?.kennung ?? hauptbuch()?.kennung ?? buecher[0]?.kennung ?? "";
    }
    if (!stoebern.fund) void zufall();
  });
</script>

<svelte:window onkeydown={taste} />
<div class="inhalt-stufe" data-schrift="klein">
  <div class="rollfeld" style="padding: 0">
    <div class="stoebern-seite">
      <div class="meins-kopf">
        {#if !geraet.mobil}<h1>Stöbern</h1>{/if}          <!-- am Telefon steht der Titel im Kopf -->
        <div class="filterzeile">
          {#if buecher.length > 1}
            <Auswahl wert={stoebern.buch} symbol="fa-book" titel="Buch zum Stöbern" onwahl={buchWaehlen}
                     optionen={buecher.map((b) => ({ wert: b.kennung, titel: bezeichnung(b) }))} />
          {/if}
          <button class="chip" class:an={stoebern.mitBild} aria-pressed={stoebern.mitBild} onclick={() => filterUmschalten("mitBild")}>
            <i class="fa-solid fa-image"></i>nur mit Bild</button>
          <button class="chip" class:an={stoebern.ungelesen} aria-pressed={stoebern.ungelesen} onclick={() => filterUmschalten("ungelesen")}>
            <i class="fa-solid fa-eye-slash"></i>noch nicht gelesen</button>
        </div>
      </div>
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}

      <section>
        <div class="abschnitt-kopf"><h2><i class="fa-solid fa-dice"></i>Zufall</h2>
          <span class="neben">aus {buch ? bezeichnung(buch) : "dem Buch"}{stoebern.mitBild ? ", mit Bild" : ""}{stoebern.ungelesen ? ", noch nicht gelesen" : ""}</span></div>
        <div class="zufall-buehne" class:mit-eben={stoebern.eben.length > 0}>
          {#if stoebern.fund}
            {@const f = stoebern.fund}
            <div class="zufall-gross" class:laedt={zieht} class:ohne-bild={!f.bild}>
              {#if f.bild}<div class="bildflaeche"><img src={f.bild} alt="" /></div>{/if}
              <div class="koerper">
                <span class="etikett"><i class="fa-solid fa-dice"></i>Zufallsfund</span>
                <span class="t">{f.titel}</span>
                {#if f.auszug}<p>{f.auszug}</p>{/if}
                <div class="zufall-knoepfe">
                  <button class="knopf primaer" onclick={() => lesen(f.buch, f.pfad)}><i class="fa-solid fa-book-open"></i>Lesen</button>
                  <button class="knopf" class:an={!!merkeintrag(f)} onclick={() => merkenUmschalten(f)}>
                    <i class="fa-{merkeintrag(f) ? 'solid' : 'regular'} fa-bookmark"></i>{merkeintrag(f) ? "Gemerkt" : "Merken"}</button>
                  <button class="knopf" onclick={() => vonHier(f)}><i class="fa-solid fa-route"></i>Von hier weiter</button>
                  <button class="knopf still" disabled={zieht} onclick={zufall}><i class="fa-solid fa-forward"></i>Nächster{#if !geraet.mobil} <kbd>Leertaste</kbd>{/if}</button>
                </div>
              </div>
            </div>
          {:else}
            <div class="zufall-gross laedt"><div class="bildflaeche"><i class="fa-solid fa-dice"></i></div><div class="koerper"><span class="etikett">Zieht einen Fund ...</span></div></div>
          {/if}
          {#if stoebern.eben.length}
            <div class="eben">
              <span class="etikett"><i class="fa-solid fa-clock-rotate-left"></i>Eben gesehen</span>
              <div class="liste">
                {#each stoebern.eben as f (f.pfad)}
                  <button class="liste-ziel kompakt" onclick={() => lesen(f.buch, f.pfad)}>
                    {#if f.bild}<img src={f.bild} alt="" loading="lazy" />{:else}<span class="ohne-bild"><i class="fa-solid fa-file-lines"></i></span>{/if}
                    <span><span class="t">{f.titel}</span><span class="u">{ebenStand(f)}</span></span>
                  </button>
                {/each}
              </div>
            </div>
          {/if}
        </div>
      </section>

      <section>
        <div class="abschnitt-kopf"><h2><i class="fa-solid fa-route"></i>Entdeckungspfad</h2><span class="neben">von Artikel zu Artikel, der Weg bleibt sichtbar</span></div>
        {#if !stoebern.pfad.length}
          <p class="leer-hinweis">Beim Zufallsfund "Von hier weiter" wählen: dann geht es über Verweise und verwandte Artikel weiter, und der Weg bleibt hier stehen.</p>
        {:else}
          <div class="pfad-leiste">
            {#each stoebern.pfad as f, i (i)}
              {#if i}<i class="fa-solid fa-chevron-right"></i>{/if}
              <button class="schritt-p" class:jetzt={i === stoebern.pfad.length - 1} onclick={() => (i === stoebern.pfad.length - 1 ? lesen(f.buch, f.pfad) : zurueckZu(i))}
                      title={i === stoebern.pfad.length - 1 ? "Lesen" : "Von hier neu weiter"}>
                {#if f.bild}<img src={f.bild} alt="" />{/if}{f.titel}</button>
            {/each}
            <span class="rechts">
              <button class="knopf still" onclick={pfadAlsThema}><i class="fa-solid fa-layer-group"></i>Pfad als Thema</button>
              <button class="knopf still" onclick={() => { stoebern.pfad = []; stoebern.schritt = null; }}><i class="fa-solid fa-rotate-left"></i>Neu beginnen</button>
            </span>
          </div>
          {#if stoebern.schritt}
            {@const s = stoebern.schritt}
            <div class="schritte-gitter" class:laedt={schrittLaedt}>
              {#each [{ titel: "Verweist von hier", symbol: "fa-arrow-right-from-bracket", liste: s.von_hier, weg: "" },
                      { titel: "Erwähnt in", symbol: "fa-arrow-right-to-bracket", liste: s.erwaehnt_in, weg: "Index" },
                      { titel: "Ähnlich nach Bedeutung", symbol: "fa-wand-magic-sparkles", liste: s.aehnlich, weg: "Bedeutung" }].filter((sp) => sp.liste.length) as sp (sp.titel)}
                <div class="schritt-spalte">
                  <h3><i class="fa-solid {sp.symbol}"></i>{sp.titel}{#if sp.weg}<span class="weg">{sp.weg}</span>{/if}</h3>
                  <div class="liste">
                    {#each sp.liste as n (n.pfad)}
                      <button class="liste-ziel kompakt ohne-bildspalte" onclick={() => weiter(n)}>
                        <span><span class="t">{n.titel}</span>{#if n.hinweis}<span class="u">{n.hinweis}</span>{/if}</span>
                      </button>
                    {/each}
                  </div>
                </div>
              {/each}
            </div>
          {/if}
        {/if}
      </section>

      <section>
        <div class="abschnitt-kopf"><h2><i class="fa-solid fa-book-open"></i>Blättern wie im Buch</h2><span class="neben">Titel in der Reihenfolge des Buchs, ohne Weiterleitungen</span></div>
        <div class="alphabet">
          {#each BUCHSTABEN as b (b)}
            <button class:an={stoebern.buchstabe === b} onclick={() => blaettern({ buchstabe: b })}>{b}</button>
          {/each}
        </div>
        {#if stoebern.seite}
          {@const seite = stoebern.seite}
          <div class="buch-blaettern">
            <div class="buchseite">
              {#if seite.eintraege.length}
                <div class="lauf"><span>{seite.eintraege[0].titel}</span><span>{seite.eintraege.at(-1)?.titel}</span></div>
              {/if}
              {#each seite.eintraege as e (e.pfad)}
                <button class:hier={e.pfad === (stoebern.vorschau?.pfad ?? seite.hier)} onclick={() => vorschauZu(e.pfad)}
                        ondblclick={() => lesen(stoebern.buch, e.pfad)}>{e.titel}{#if e.pfad === seite.hier}<span class="art">Zufallsfund</span>{/if}</button>
              {/each}
              <div class="blaetter">
                <button class="knopf" disabled={seite.erste <= 0} onclick={() => blaettern({ bis: seite.erste })}><i class="fa-solid fa-chevron-left"></i>Seite zurück</button>
                <button class="knopf" disabled={seite.naechste < 0} onclick={() => blaettern({ ab: seite.naechste })}>Seite vor<i class="fa-solid fa-chevron-right"></i></button>
              </div>
            </div>
            {#if stoebern.vorschau}
              {@const v = stoebern.vorschau}
              <div class="vorschau-spalte">
                {#if v.bild}<img src={v.bild} alt="" />{/if}
                <div class="koerper">
                  <b>{v.titel}</b>
                  {#if v.auszug}<p>{v.auszug}</p>{/if}
                  <div class="zufall-knoepfe">
                    <button class="knopf primaer" onclick={() => lesen(v.buch, v.pfad)}><i class="fa-solid fa-book-open"></i>Lesen</button>
                    <button class="knopf" class:an={!!merkeintrag(v)} onclick={() => merkenUmschalten(v)}>
                      <i class="fa-{merkeintrag(v) ? 'solid' : 'regular'} fa-bookmark"></i>{merkeintrag(v) ? "Gemerkt" : "Merken"}</button>
                  </div>
                </div>
              </div>
            {/if}
          </div>
        {/if}
      </section>
    </div>
  </div>
</div>
