<script lang="ts">
  // Als Buch (Entwurf mockups/export.html, am Telefon telefon-export.html): ein Thema wird ein Buch. Vier Schritte
  // untereinander (Inhalt, Vorlage, Umformung, Format und Ablage), rechts immer Vorschau, Dauer aus der Hausmessung und
  // wann gebaut wird. Erst ein Probekapitel ansehen, dann jetzt oder heute Nacht bauen. Weg: themen/<thema>/buch.
  import { onMount, untrack } from "svelte";
  import { gehe, geraet, navigation, seitenFehler } from "appkern-oberflaeche";
  import Buchblatt from "./Buchblatt.svelte";
  import Buchdeckel from "./Buchdeckel.svelte";
  import {
    FUER_WEN, LAENGE, SEITEN, bauen, bestellungFuer, buecher, buchwahlHolen, dauerText, probeAnstossen, probeHolen,
    schaetzen, teileVon, titelVon, uhrzeit, vorlagenLaden, zahl, type Bestellung, type Buchwahl, type Schaetzung,
  } from "../lib/buecher.svelte";

  let { thema }: { thema: string } = $props();

  const SCHAETZEN_MS = 300;
  let wahl = $state.raw<Buchwahl | null>(null);
  let b = $state<Bestellung | null>(null);
  let schaetzung = $state.raw<Schaetzung | null>(null);
  let probeDa = $state("");                       // Vorlage der letzten Probe dieses Themas
  let fehler = $state("");
  let sendet = $state(false);
  let ziehe = $state<number | null>(null);

  async function laden(t: string) {
    fehler = "";
    try {
      const [w] = await Promise.all([buchwahlHolen(t), buecher.vorlagen.length ? Promise.resolve() : vorlagenLaden()]);
      if (t !== thema) return;
      wahl = w;
      navigation.titel = "Als Buch";
      b = buecher.entwuerfe[t] ?? bestellungFuer(w, buecher.vorlagen);
      probeDa = (await probeHolen(t))?.vorlage ?? "";
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }
  $effect(() => {
    const t = thema;
    untrack(() => void laden(t));
  });

  // jede Änderung: Entwurf merken (Probekapitel und Vorlagen nehmen ihn mit) und neu schätzen
  $effect(() => {
    if (!b) return;
    const jetzt = $state.snapshot(b) as Bestellung;
    buecher.entwuerfe[thema] = jetzt;
    const abbruch = new AbortController();
    const takt = setTimeout(() => {
      schaetzen(jetzt, abbruch.signal).then((s) => (schaetzung = s)).catch((f) => (fehler = seitenFehler(f)));
    }, SCHAETZEN_MS);
    return () => { clearTimeout(takt); abbruch.abort(); };
  });

  const vorlage = $derived(buecher.vorlagen.find((v) => v.kennung === b?.vorlage));
  const teile = $derived(teileVon(vorlage));
  const kapitel = $derived(wahl && b ? b.kapitel.map((k) => ({ ...k, angabe: wahl!.kapitel.find((x) => x.bereich === k.bereich) }))
    .filter((k) => k.angabe) : []);
  const imBuch = $derived(kapitel.filter((k) => k.an));
  const artikelImBuch = $derived(imBuch.reduce((n, k) => n + (k.angabe?.lesbar ?? 0), 0));
  const mitgeliefert = $derived(buecher.vorlagen.filter((v) => v.mitgeliefert));
  const eigene = $derived(buecher.vorlagen.filter((v) => !v.mitgeliefert));
  const vorschauText = $derived(wahl?.auszug ? `${wahl.auszug}${wahl.auszug.length >= 240 ? " ..." : ""}` : "");
  const pfad = $derived(wahl ? wahl.ablage.replace(/^Apps\//, "").split("/").join(" / ") : "");

  function vorlageWaehlen(kennung: string) {
    const v = buecher.vorlagen.find((x) => x.kennung === kennung);
    if (!b || !v) return;
    b.vorlage = kennung;                                    // Vorgaben der Vorlage, beim Bauen änderbar
    b.fuer_wen = v.anweisung.fuer_wen;
    b.laenge = v.anweisung.laenge;
    b.fragen = v.anweisung.fragen;
  }

  // Ziehen ändert die Reihenfolge der Kapitel nur im Buch
  function ablegen(ziel: number) {
    if (!b || ziehe === null || ziehe === ziel) return;
    const [k] = b.kapitel.splice(ziehe, 1);
    b.kapitel.splice(ziel, 0, k);
    ziehe = null;
  }

  async function probeAnsehen() {
    if (!b) return;
    sendet = true;
    try {
      buecher.proben[thema] = (await probeAnstossen($state.snapshot(b) as Bestellung)).id;
      gehe(`themen/${thema}/buch/probe`);
    } catch (f) {
      fehler = seitenFehler(f);
    } finally {
      sendet = false;
    }
  }

  async function buchBauen() {
    if (!b) return;
    sendet = true;
    try {
      await bauen($state.snapshot(b) as Bestellung);
      gehe("buecher");
    } catch (f) {
      fehler = seitenFehler(f);
    } finally {
      sendet = false;
    }
  }

  const fertigUm = $derived(schaetzung?.ende ? uhrzeit(schaetzung.ende) : "");
  const bauenText = $derived(b?.wann === "nachts" ? "Heute Nacht bauen" : "Jetzt bauen");
  const probeText = $derived(schaetzung?.probe_titel
    ? `Probekapitel ansehen (${schaetzung.probe_titel}, etwa ${dauerText(schaetzung.probe_sekunden)})` : "Probekapitel ansehen");
  const kannBauen = $derived(!!b && !!vorlage && artikelImBuch > 0 && (b.epub || b.pdf) && (!vorlage.ki || !!wahl?.leitstelle) && !sendet);
  const grundNicht = $derived(!vorlage ? "Eine Vorlage wählen" : !artikelImBuch ? "Mindestens ein Kapitel mit Artikeln wählen"
    : vorlage.ki && !wahl?.leitstelle ? "Diese Vorlage braucht die KI; die Leitstelle ist nicht eingerichtet (Einstellungen, Verbindungen)" : "");

  onMount(() => () => { navigation.titel = ""; });
</script>

{#snippet wannZeile()}
  {#if schaetzung && b}
    {#if b.wann === "nachts"}
      Beginnt um <b>{uhrzeit(schaetzung.beginn)}</b>, fertig gegen <b>{fertigUm}</b>.
      {#if !schaetzung.nacht_reicht}Eine Nacht reicht nicht; der Rest läuft in der nächsten weiter.{/if}
      Das Zeitfenster für Nachtarbeit steht in den <button class="exp-verweis" onclick={() => gehe("einstellungen")}>Einstellungen</button>.
    {:else}
      Fertig gegen <b>{fertigUm}</b>, wenn die Leitstelle frei ist.
    {/if}
  {/if}
{/snippet}

{#if fehler && !wahl}
  <div class="fehlertext">{fehler}</div>
{:else if !wahl || !b}
  <div class="rollfeld"><p class="leer-hinweis">Liest das Thema: Kapitel, Notizen, Bilder ...</p></div>
{:else}
  {#if geraet.mobil}
    <!-- Telefon: Vorlage und Format wählen und bauen; Kapitel und Feinheiten bleiben wie zuletzt eingestellt -->
    <div class="rollfeld exp-telefon">
      <div class="exp-t-kopf">
        <Buchdeckel bild={b.titelbild} titel={wahl.titel} />
        <div><b>{wahl.titel}</b><div class="u">{artikelImBuch} Artikel in {imBuch.length} {imBuch.length === 1 ? "Kapitel" : "Kapiteln"}{b.notizen && wahl.notizen ? ", Notizen" : ""}{b.bilder && wahl.bilder ? " und Bilder" : ""} dabei</div></div>
      </div>
      <h2 class="exp-t-h2">Vorlage</h2>
      <div class="exp-t-wahl" role="radiogroup" aria-label="Vorlage">
        {#each buecher.vorlagen as v (v.kennung)}
          <button class="zeile" class:an={b.vorlage === v.kennung} role="radio" aria-checked={b.vorlage === v.kennung} onclick={() => vorlageWaehlen(v.kennung)}>
            <i class={b.vorlage === v.kennung ? "fa-solid fa-circle-dot" : "fa-regular fa-circle"}></i><span>{v.titel}</span><span class="u">{v.ki ? "KI" : ""}</span></button>
        {/each}
      </div>
      <h2 class="exp-t-h2">Formate</h2>
      <div class="exp-t-formate">
        <button class="chip exp-chip" class:an={b.epub} aria-pressed={b.epub} onclick={() => (b!.epub = !b!.epub || !b!.pdf)}>
          <i class={b.epub ? "fa-solid fa-square-check" : "fa-regular fa-square"}></i>EPUB</button>
        <button class="chip exp-chip" class:an={b.pdf} aria-pressed={b.pdf} disabled={!!wahl.pdf} title={wahl.pdf} onclick={() => (b!.pdf = !b!.pdf || !b!.epub)}>
          <i class={b.pdf ? "fa-solid fa-square-check" : "fa-regular fa-square"}></i>PDF {titelVon(SEITEN, b.seiten)}</button>
      </div>
      <h2 class="exp-t-h2">Dauer</h2>
      <div class="exp-t-schaetzung">
        <b>etwa {schaetzung ? dauerText(schaetzung.sekunden) : "..."}</b>
        {#if schaetzung}<span>{b.wann === "nachts" ? `Heute Nacht ab ${uhrzeit(schaetzung.beginn)}, fertig gegen ${fertigUm}` : `Jetzt, fertig gegen ${fertigUm}`}</span>{/if}
      </div>
      {#if grundNicht}<p class="exp-hinweis">{grundNicht}</p>{/if}
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
    </div>
    <div class="exp-t-steuer">
      <button class="knopf gross" title="Probekapitel ansehen" disabled={!schaetzung?.probe_titel || !kannBauen} onclick={probeAnsehen}><i class="fa-solid fa-flask"></i></button>
      <button class="knopf primaer gross" disabled={!kannBauen} onclick={buchBauen}><i class="fa-solid {b.wann === 'nachts' ? 'fa-moon' : 'fa-play'}"></i>{bauenText}</button>
    </div>
  {:else}
    <div class="seiten-kopf">
      <button class="rund still" title="Zurück zum Thema" onclick={() => gehe(`themen/${thema}`)}><i class="fa-solid fa-chevron-left"></i></button>
      <h1>Als Buch: {wahl.titel}</h1>
      <span class="pille"><i class="fa-solid fa-layer-group"></i>aus dem Thema, {wahl.artikel} Artikel</span>
    </div>
    <div class="rollfeld">
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
      <div class="exp-buehne">
        <div class="exp-schritte">
          <!-- 1 Inhalt -->
          <div class="karte">
            <h2><span class="exp-nr" class:fertig={artikelImBuch > 0}>1</span>Inhalt<span class="neben">{artikelImBuch} Artikel in {imBuch.length} {imBuch.length === 1 ? "Kapitel" : "Kapiteln"}</span></h2>
            <div class="karte-unter">Jeder Bereich des Themas wird ein Kapitel, in seiner Reihenfolge. Ziehen ändert die Reihenfolge nur im Buch.
              {#if vorlage?.aufbau.gliederung === "abc"}Diese Vorlage ordnet alle Artikel von A bis Z; hier zählt nur, welche Bereiche hinein kommen.{/if}</div>
            <div class="exp-kapitel" role="list">
              {#each kapitel as k, i (k.bereich)}
                <div class="zeile" class:aus={!k.an} class:zieht={ziehe === i} role="listitem" draggable="true"
                     ondragstart={() => (ziehe = i)} ondragover={(e) => e.preventDefault()} ondrop={() => ablegen(i)} ondragend={() => (ziehe = null)}>
                  <i class="fa-solid fa-grip-vertical griff" title="Ziehen zum Umordnen"></i>
                  <button class="wahl" role="checkbox" aria-checked={k.an} title={k.an ? "Aus dem Buch nehmen" : "Ins Buch nehmen"}
                          onclick={() => (b!.kapitel[i].an = !k.an)}><i class={k.an ? "fa-solid fa-square-check" : "fa-regular fa-square"}></i></button>
                  <span class="nr">{k.an ? imBuch.indexOf(k) + 1 : ""}</span><b>{k.angabe?.titel}</b>
                  <span class="u">{k.an ? `${k.angabe?.artikel} Artikel` : `${k.angabe?.artikel} Artikel, nicht im Buch`}{#if k.angabe && k.angabe.lesbar < k.angabe.artikel}, {k.angabe.artikel - k.angabe.lesbar} ohne Quelle{/if}
                    {#if k.an && k.angabe?.bilder.length}<span class="bilder">{#each k.angabe.bilder as bild (bild)}<img src={bild} alt="" loading="lazy" />{/each}</span>{/if}</span>
                </div>
              {/each}
            </div>
            <div class="feld"><div class="was"><div class="name">Mit hinein</div><div class="beschreibung">Notizen stehen als Randnotiz an ihrer Stelle, gemerkte Stellen als Hervorhebung.{#if !teile.has("notizen")} Diese Vorlage hat keine Notizen.{/if}</div></div>
              <span class="wert-rechts">
                <button class="chip exp-chip" class:an={b.notizen && teile.has("notizen")} disabled={!teile.has("notizen")} onclick={() => (b!.notizen = !b!.notizen)}>
                  <i class={b.notizen && teile.has("notizen") ? "fa-solid fa-square-check" : "fa-regular fa-square"}></i>Notizen ({wahl.notizen})</button>
                <button class="chip exp-chip" class:an={b.markierungen} onclick={() => (b!.markierungen = !b!.markierungen)}>
                  <i class={b.markierungen ? "fa-solid fa-square-check" : "fa-regular fa-square"}></i>Gemerkte Stellen ({wahl.markierungen})</button>
                <button class="chip exp-chip" class:an={b.bilder && vorlage?.gestaltung.bilder !== "ohne"} disabled={vorlage?.gestaltung.bilder === "ohne"}
                        title={vorlage?.gestaltung.bilder === "ohne" ? "Die Vorlage setzt keine Bilder" : ""} onclick={() => (b!.bilder = !b!.bilder)}>
                  <i class={b.bilder && vorlage?.gestaltung.bilder !== "ohne" ? "fa-solid fa-square-check" : "fa-regular fa-square"}></i>Bilder ({wahl.bilder})</button>
                <button class="chip exp-chip" class:an={b.steckbriefe} disabled={!wahl.steckbriefe} onclick={() => (b!.steckbriefe = !b!.steckbriefe)}>
                  <i class={b.steckbriefe ? "fa-solid fa-square-check" : "fa-regular fa-square"}></i>Steckbriefe{wahl.steckbriefe ? ` (${wahl.steckbriefe})` : ""}</button>
              </span></div>
            {#if wahl.fremd.length}
              {@const uebersetzt = wahl.fremd.filter((f) => f.uebersetzt)}
              <div class="feld"><div class="was"><div class="name">Artikel in anderer Sprache</div>
                <div class="beschreibung">{#if uebersetzt.length}{uebersetzt.map((f) => `"${f.titel}"`).join(", ")} {uebersetzt.length === 1 ? "ist" : "sind"} schon übersetzt; die Übersetzung geht ins Buch.{/if}
                  {#if wahl.fremd.length > uebersetzt.length}{wahl.fremd.length - uebersetzt.length} noch nicht übersetzt: {vorlage?.ki ? "die KI schreibt sie gleich auf Deutsch" : "sie bleiben im Original"}.{/if}</div></div>
                <span class="segment">
                  <button class:aktiv={b.uebersetzung} onclick={() => (b!.uebersetzung = true)}>Übersetzung nehmen</button>
                  <button class:aktiv={!b.uebersetzung} onclick={() => (b!.uebersetzung = false)}>Original lassen</button>
                </span></div>
            {/if}
            <div class="feld"><div class="was"><div class="name">Quellen und Lizenzen</div><div class="beschreibung">Am Ende des Buchs, je Artikel Buch, Fassung, Urheber und Lizenz; die Lizenz der Bücher verlangt das.</div></div>
              <span class="exp-regeln"><span class="chip"><i class="fa-solid fa-lock"></i>immer dabei</span></span></div>
          </div>

          <!-- 2 Vorlage -->
          <div class="karte">
            <h2><span class="exp-nr" class:fertig={!!vorlage}>2</span>Vorlage<span class="neben">bestimmt Aufbau, Ton und Gestaltung</span></h2>
            <div class="exp-vorlagen" role="radiogroup" aria-label="Vorlage">
              {#each [...mitgeliefert, ...eigene] as v (v.kennung)}
                <button class="exp-vorlage" class:aktiv={b.vorlage === v.kennung} role="radio" aria-checked={b.vorlage === v.kennung} onclick={() => vorlageWaehlen(v.kennung)}>
                  <Buchblatt vorlage={v} />
                  <b>{#if b.vorlage === v.kennung}<i class="fa-solid fa-circle-check"></i>{/if}{v.titel}{#if v.ki}<span class="ki">KI</span>{/if}</b>
                  <span class="u">{v.mitgeliefert ? v.beschreibung : `eigene Vorlage${v.kopiert_aus ? `, aus ${v.kopiert_aus}` : ""}`}</span></button>
              {/each}
              <button class="exp-vorlage neu" onclick={() => gehe(`themen/${thema}/buch/vorlagen?vorlage=${b!.vorlage}`)}><i class="fa-solid fa-pen-ruler"></i><b>Vorlagen bearbeiten</b></button>
            </div>
            {#if buecher.hinweis}<p class="exp-hinweis">{buecher.hinweis}</p>{/if}
          </div>

          <!-- 3 Umformung -->
          <div class="karte">
            <h2><span class="exp-nr" class:fertig={!!vorlage && (!vorlage.ki || probeDa === vorlage.kennung)}>3</span>Umformung
              <span class="neben">{vorlage?.ki ? (wahl.leitstelle ? `über die Leitstelle, ${wahl.modell}` : "Leitstelle nicht eingerichtet") : "ohne KI"}</span></h2>
            {#if vorlage?.ki}
              <div class="feld"><div class="was"><div class="name">Für wen</div><div class="beschreibung">Wortwahl und wie viel vorausgesetzt wird.</div></div>
                <span class="segment">{#each FUER_WEN as x (x.wert)}<button class:aktiv={b.fuer_wen === x.wert} onclick={() => (b!.fuer_wen = x.wert)}>{x.titel}</button>{/each}</span></div>
              {#if teile.has("umgeformt")}
                <div class="feld"><div class="was"><div class="name">Länge</div><div class="beschreibung">Gekürzt wird an Einzelheiten, nie an den Aussagen{teile.has("blick") ? ", die in Auf einen Blick stehen" : ""}.</div></div>
                  <span class="segment">{#each LAENGE as x (x.wert)}<button class:aktiv={b.laenge === x.wert} onclick={() => (b!.laenge = x.wert)}>{x.titel}</button>{/each}</span></div>
              {/if}
              {#if teile.has("fragen")}
                <div class="feld"><div class="was"><div class="name">Fragen je Kapitel</div><div class="beschreibung">Mit Antwort zum Aufklappen (EPUB) oder hinten im Heft (PDF).</div></div>
                  <span class="wert-zahl"><button class="knopf" title="Weniger" disabled={b.fragen <= 0} onclick={() => (b!.fragen -= 1)}><i class="fa-solid fa-minus"></i></button><b>{b.fragen}</b>
                    <button class="knopf" title="Mehr" disabled={b.fragen >= 10} onclick={() => (b!.fragen += 1)}><i class="fa-solid fa-plus"></i></button></span></div>
              {/if}
              <div class="feld"><div class="was"><div class="name">Feste Regeln</div><div class="beschreibung">Gelten für jede Vorlage. Die Prüfung nach dem Umformen zeigt jede Abweichung im Probekapitel und im Auftrag.</div></div>
                <span class="exp-regeln">{#each buecher.katalog?.regeln ?? [] as r (r)}<span class="chip"><i class="fa-solid fa-check"></i>{r}</span>{/each}</span></div>
            {:else}
              <p class="karte-unter exp-ohne-ki">Diese Vorlage formt nicht um: die Artikel stehen wie in den Büchern, mit Listen und Tabellen. Es braucht keine Leitstelle.</p>
            {/if}
          </div>

          <!-- 4 Format und Ablage -->
          <div class="karte">
            <h2><span class="exp-nr" class:fertig={b.epub || b.pdf}>4</span>Format und Ablage</h2>
            <div class="feld"><div class="was"><div class="name">Formate</div><div class="beschreibung">{["EPUB für Lesegerät und Telefon, PDF zum Drucken.", wahl.pdf ? `${wahl.pdf}.` : ""].join(" ")}</div></div>
              <span class="wert-rechts">
                <button class="chip exp-chip" class:an={b.epub} onclick={() => (b!.epub = !b!.epub || !b!.pdf)}><i class={b.epub ? "fa-solid fa-square-check" : "fa-regular fa-square"}></i>EPUB</button>
                <button class="chip exp-chip" class:an={b.pdf} disabled={!!wahl.pdf} onclick={() => (b!.pdf = !b!.pdf || !b!.epub)}><i class={b.pdf ? "fa-solid fa-square-check" : "fa-regular fa-square"}></i>PDF</button>
              </span></div>
            {#if b.pdf}
              <div class="feld"><div class="was"><div class="name">Seitengröße des PDF</div></div>
                <span class="segment">{#each SEITEN as x (x.wert)}<button class:aktiv={b.seiten === x.wert} onclick={() => (b!.seiten = x.wert)}>{x.titel}</button>{/each}</span></div>
            {/if}
            {#if teile.has("titelseite")}
              <div class="feld"><div class="was"><div class="name">Titelbild</div><div class="beschreibung">Aus den Bildern der Artikel; groß, sobald der Bildholer es geladen hat.</div></div>
                <span class="exp-titelbilder">
                  {#each wahl.titelbilder as bild (bild)}
                    <button class:an={b.titelbild === bild} aria-pressed={b.titelbild === bild} title="Als Titelbild" onclick={() => (b!.titelbild = bild)}><img src={bild} alt="" loading="lazy" /></button>
                  {:else}<span class="exp-leise">Die Artikel haben keine Bilder; der Deckel bleibt in der Farbe der Vorlage.</span>{/each}
                </span></div>
            {/if}
            <div class="feld"><div class="was"><div class="name">Ablage</div><div class="beschreibung">Fertige Bücher liegen in der Kellerwolke und unter Eigene Bücher zum Herunterladen.</div></div>
              <span class="eingabe-schein"><i class="fa-solid fa-cloud"></i>{pfad}</span></div>
          </div>
        </div>

        <aside class="exp-vorschau">
          <div class="karte">
            <h3>Vorschau</h3>
            <div class="exp-buch">
              <Buchdeckel bild={teile.has("titelseite") ? b.titelbild : ""} titel={wahl.titel} untertitel={vorlage?.untertitel ?? ""} />
              <div class="exp-seite" class:serifen={vorlage?.gestaltung.schrift !== "ohne"} style="--exp-farbe: var(--{vorlage?.gestaltung.farbe ?? 'petrol'})">
                <b>{vorlage?.aufbau.gliederung === "abc" ? (wahl.auszug_titel[0] ?? "A") : `1 ${imBuch[0]?.angabe?.titel ?? wahl.titel}`}</b>
                {#if teile.has("blick")}<div class="kasten"><em>Auf einen Blick</em>{wahl.auszug_titel}</div>{/if}
                <span>{vorschauText}</span>
              </div>
            </div>
          </div>
          <div class="karte">
            <h3>Dauer</h3>
            {#if schaetzung}
              <div class="exp-zahlen">
                <div class="kennzahl"><span class="k">Text</span><span class="w">{zahl(schaetzung.zeichen)}</span><span class="exp-leise">Zeichen in {schaetzung.artikel} Artikeln</span></div>
                <div class="kennzahl"><span class="k">Etwa</span><span class="w">{dauerText(schaetzung.sekunden)}</span><span class="exp-leise">im Buch rund {schaetzung.seiten} Seiten {b.pdf ? titelVon(SEITEN, b.seiten) : "A5"}</span></div>
              </div>
              <div class="exp-zeitleiste">
                {#each schaetzung.schritte as s (s.titel)}<div class="z"><span>{s.titel}</span><span>{dauerText(s.sekunden)}</span></div>{/each}
                <div class="z summe"><span>Zusammen</span><span>{dauerText(schaetzung.sekunden)}</span></div>
              </div>
              <div class="exp-grundlage">{#if vorlage?.ki}Grundlage: {schaetzung.gemessen ? "gemessen beim letzten Buch" : "Hausmessung"} über die Leitstelle, {schaetzung.modell} schreibt rund {zahl(schaetzung.tempo)} Zeichen je Sekunde; nach jedem Auftrag misst Nachschlag neu.{:else}Ohne KI: Artikel lesen, Bilder holen, Satz.{/if}</div>
            {:else}<p class="exp-leise">Rechnet ...</p>{/if}
          </div>
          <div class="karte">
            <h3>Wann</h3>
            <div class="exp-wann">
              <span class="segment"><button class:aktiv={b.wann === "jetzt"} onclick={() => (b!.wann = "jetzt")}>Jetzt</button><button class:aktiv={b.wann === "nachts"} onclick={() => (b!.wann = "nachts")}>Heute Nacht</button></span>
              <span class="fertig-um">{@render wannZeile()}</span>
            </div>
          </div>
          {#if grundNicht}<p class="exp-hinweis">{grundNicht}</p>{/if}
          <div class="exp-knoepfe">
            <button class="knopf" disabled={!schaetzung?.probe_titel || !kannBauen} onclick={probeAnsehen}><i class="fa-solid fa-flask"></i>{probeText}</button>
            {#if probeDa}<button class="knopf still" onclick={() => gehe(`themen/${thema}/buch/probe`)}><i class="fa-solid fa-table-columns"></i>Letztes Probekapitel</button>{/if}
            <button class="knopf primaer" disabled={!kannBauen} onclick={buchBauen}><i class="fa-solid {b.wann === 'nachts' ? 'fa-moon' : 'fa-play'}"></i>{bauenText}</button>
          </div>
        </aside>
      </div>
    </div>
  {/if}
{/if}
