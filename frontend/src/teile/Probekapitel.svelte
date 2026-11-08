<script lang="ts">
  // Probekapitel (Entwurf mockups/export-probe.html): der Anfang eines Artikels nach der Vorlage, links das Original,
  // rechts das Ergebnis. Jeder Absatz trägt Belege auf die Absätze des Originals; mit dem Zeiger (oder einem Tipp) auf
  // einem Beleg leuchtet die Stelle links auf. Oben die Prüfung: Zahlen und Belege gegen das Original, Sätze ohne Beleg
  // sind markiert und lassen sich neu schreiben lassen. Weg: themen/<thema>/buch/probe.
  import { onMount, tick, untrack } from "svelte";
  import { Auswahl, beiAuftrag, gehe, geraet, hole, navigation, seitenFehler, type Auftrag } from "appkern-oberflaeche";
  import {
    FUER_WEN, LAENGE, bestellungFuer, buecher, buchwahlHolen, dauerText, probeAnstossen, probeHolen, teileVon, titelVon,
    vorlagenLaden, zahl, type Absatz, type Bestellung, type Probe,
  } from "../lib/buecher.svelte";
  import { themaHolen, type Themeneintrag } from "../lib/themen.svelte";

  let { thema }: { thema: string } = $props();

  let probe = $state.raw<Probe | null>(null);
  let bestellung = $state.raw<Bestellung | null>(null);
  let artikel = $state.raw<Themeneintrag[]>([]);
  let fehler = $state("");
  let geladen = $state(false);
  let ansicht = $state<"nebeneinander" | "buchseite">("nebeneinander");
  let leuchtet = $state<number[]>([]);
  let offen = $state<Set<number>>(new Set());
  let original: HTMLElement | undefined = $state();

  const auftrag = $derived(buecher.proben[thema] ?? "");
  const vorlage = $derived(buecher.vorlagen.find((v) => v.kennung === (probe?.vorlage ?? bestellung?.vorlage)));
  const innen = $derived(vorlage?.aufbau.innen ?? []);
  const teile = $derived(teileVon(vorlage));

  async function laden(t: string) {
    try {
      if (!buecher.vorlagen.length) await vorlagenLaden();
      const [p, th] = await Promise.all([probeHolen(t), themaHolen(t)]);
      if (t !== thema) return;
      probe = p;
      geladen = true;
      artikel = th.eintraege.filter((x) => x.buch);
      bestellung = buecher.entwuerfe[t] ?? bestellungFuer(await buchwahlHolen(t), buecher.vorlagen);
      navigation.titel = p ? `Probe: ${p.artikel.titel}` : "Probekapitel";
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }
  $effect(() => {
    const t = thema;
    untrack(() => void laden(t));
  });

  onMount(() => {
    const aus = beiAuftrag(async (a: Auftrag) => {
      if (a.id !== buecher.proben[thema] || !["fertig", "fehler", "abgebrochen"].includes(a.zustand)) return;
      delete buecher.proben[thema];
      if (a.zustand !== "fertig") {
        fehler = (await hole<Auftrag>(`/auftraege/${a.id}`)).fehler ?? "Das Probekapitel ist nicht gelungen";
        return;
      }
      fehler = "";
      await laden(thema);
    });
    return () => { aus(); navigation.titel = ""; };
  });

  async function anstossen(eintrag = "", neu: number[] = []) {
    if (!bestellung) return;
    fehler = "";
    try {
      buecher.proben[thema] = (await probeAnstossen(bestellung, eintrag || probe?.eintrag || "", neu)).id;
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  const ohneBeleg = $derived(probe ? probe.artikel.absaetze.flatMap((a, i) => (a.ohne_beleg.length ? [i] : [])) : []);
  const saetze = $derived(probe ? probe.pruefung.hinweise.filter((h) => h.art === "satz").length : 0);
  const ergebnisZeichen = $derived(probe ? probe.artikel.absaetze.reduce((n, a) => n + (a.text || a.html).length, 0) : 0);

  async function zeigen(belege: number[]) {
    leuchtet = belege;
    await tick();
    original?.querySelector(".belegt")?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  // ein Absatz mit seinen markierten Sätzen als Teile (Text, markiert)
  function stuecke(a: Absatz): { text: string; markiert: boolean }[] {
    if (!a.ohne_beleg.length) return [{ text: a.text, markiert: false }];
    const aus: { text: string; markiert: boolean }[] = [];
    let rest = a.text;
    for (const satz of a.ohne_beleg) {
      const stelle = rest.indexOf(satz);
      if (stelle < 0) continue;
      if (stelle) aus.push({ text: rest.slice(0, stelle), markiert: false });
      aus.push({ text: satz, markiert: true });
      rest = rest.slice(stelle + satz.length);
    }
    if (rest) aus.push({ text: rest, markiert: false });
    return aus;
  }
</script>

{#snippet belege(nummern: number[])}
  {#each nummern as n (n)}<button class="exp-beleg" class:an={leuchtet.includes(n)} title="Absatz {n} im Original"
    onmouseenter={() => zeigen([n])} onfocus={() => zeigen([n])} onclick={() => zeigen([n])}>{n}</button>{/each}
{/snippet}

{#snippet kasten(k: { titel: string; punkte: { text: string; belege: number[] }[] }, eigen: boolean)}
  {#if k.punkte.length}
    <div class="exp-blick" class:eigen><b>{k.titel}</b>
      <ul>{#each k.punkte as p, i (i)}<li>{p.text}{@render belege(p.belege)}</li>{/each}</ul></div>
  {/if}
{/snippet}

{#snippet ergebnis(p: Probe)}
  {@const a = p.artikel}
  <h2>{a.titel}</h2>
  {#if p.kapitel.einleitung.length && teile.has("kapiteleinleitung")}<p class="exp-einleitung">{p.kapitel.einleitung.map((s) => s.text).join(" ")}</p>{/if}
  {#each innen as t, ti (ti)}
    {#if t.art === "blick" && a.blick}{@render kasten(a.blick, false)}
    {:else if t.art === "kasten"}
      {@const nr = innen.slice(0, ti).filter((x) => x.art === "kasten").length}
      {#if a.kaesten[nr]}{@render kasten(a.kaesten[nr], true)}{/if}
    {:else if t.art === "notizen"}
      {#each a.notizen as n, i (i)}<div class="exp-randnotiz"><i class="fa-solid fa-note-sticky"></i><span><b>Meine Notiz:</b> {n.text}</span></div>{/each}
    {:else if t.art === "umgeformt" || t.art === "originaltext"}
      {#each a.absaetze as x, i (i)}
        {#if x.ueberschrift}<h3>{x.ueberschrift}</h3>{/if}
        {#if x.html}
          <p class="exp-wie-im-buch" class:hervorgehoben={x.hervorgehoben}>{@html x.html}{@render belege(x.belege)}</p>
        {:else}
          <p class:hervorgehoben={x.hervorgehoben}>{#each stuecke(x) as s, si (si)}{#if s.markiert}<span class="ohne-beleg">{s.text}</span><span class="exp-hinweisblase"><i class="fa-solid fa-triangle-exclamation"></i>steht so nicht im Original</span>{:else}{s.text}{/if}{/each}{@render belege(x.belege)}</p>
        {/if}
        {#each x.notizen as n, ni (ni)}<div class="exp-randnotiz"><i class="fa-solid fa-note-sticky"></i><span><b>Meine Notiz:</b> {n.text}</span></div>{/each}
        {#each x.bilder as bild (bild.adresse)}<figure class="exp-bild"><img src={bild.adresse} alt="" loading="lazy" />{#if bild.unterschrift}<figcaption>{bild.unterschrift}</figcaption>{/if}</figure>{/each}
      {/each}
    {/if}
  {/each}
  {#if p.kapitel.fragen.length}
    <h3>Fragen zum Kapitel</h3>
    <ol class="exp-fragen">
      {#each p.kapitel.fragen as f, i (i)}
        <li>{f.frage}<button class="antwort" aria-expanded={offen.has(i)} onclick={() => { const s = new Set(offen); if (s.has(i)) s.delete(i); else s.add(i); offen = s; }}>
          <i class="fa-solid {offen.has(i) ? 'fa-chevron-down' : 'fa-chevron-right'}"></i> {offen.has(i) ? f.antwort : "Antwort aufklappen"}</button></li>
      {/each}
    </ol>
  {/if}
{/snippet}

<div class="seiten-kopf">
  {#if !geraet.mobil}<button class="rund still" title="Zurück zu Als Buch" onclick={() => gehe(`themen/${thema}/buch`)}><i class="fa-solid fa-chevron-left"></i></button>{/if}
  <h1>Probe{probe ? `: ${probe.artikel.titel}` : "kapitel"}</h1>
  {#if probe && vorlage?.ki}
    <span class="pille"><i class="fa-solid fa-book"></i>{probe.vorlage_titel}, {titelVon(FUER_WEN, probe.fuer_wen)}, {titelVon(LAENGE, probe.laenge).toLowerCase()}</span>
    <span class="pille exp-gut"><i class="fa-solid fa-stopwatch"></i>umgeformt in {dauerText(probe.sekunden)}</span>
  {:else if probe}
    <span class="pille"><i class="fa-solid fa-book"></i>{probe.vorlage_titel}, ohne Umformung</span>
  {/if}
  {#if auftrag}<span class="pille aktiv"><i class="fa-solid fa-spinner fa-spin"></i>die KI arbeitet</span>{/if}
</div>
<div class="exp-werkzeuge">
  <span class="segment">
    <button class:aktiv={ansicht === "nebeneinander"} onclick={() => (ansicht = "nebeneinander")}><i class="fa-solid fa-table-columns"></i> Nebeneinander</button>
    <button class:aktiv={ansicht === "buchseite"} onclick={() => (ansicht = "buchseite")}><i class="fa-solid fa-file-lines"></i> Als Buchseite</button>
  </span>
  <div class="rechts">
    {#if artikel.length > 1}
      <Auswahl wert={probe?.eintrag ?? ""} symbol="fa-shuffle" titel="Anderen Artikel probieren" platzhalter="Anderen Artikel probieren"
               optionen={artikel.map((x) => ({ wert: x.id, titel: x.titel }))} onwahl={(w) => w !== probe?.eintrag && anstossen(w)} />
    {/if}
    <button class="knopf" onclick={() => gehe(`themen/${thema}/buch/vorlagen?vorlage=${vorlage?.kennung ?? ""}`)}><i class="fa-solid fa-pen-ruler"></i>Vorlage anpassen</button>
    <button class="knopf primaer" onclick={() => gehe(`themen/${thema}/buch`)}><i class="fa-solid fa-check"></i>Passt, so bauen</button>
  </div>
</div>
<div class="rollfeld">
  {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
  {#if probe}
    {@const pr = probe.pruefung}
    <div class="exp-pruefung">
      <b>Prüfung</b>
      {#if !pr.absaetze && !pr.zahlen}
      <span class="ok"><i class="fa-solid fa-circle-check"></i> Text wie im Buch: nichts umgeformt, nichts zu prüfen</span>
      {:else}
      <span class:ok={pr.zahlen_gefunden === pr.zahlen} class:hinweis={pr.zahlen_gefunden < pr.zahlen}>
        <i class="fa-solid {pr.zahlen_gefunden === pr.zahlen ? 'fa-circle-check' : 'fa-triangle-exclamation'}"></i> {pr.zahlen_gefunden} von {pr.zahlen} Zahlen im Original gefunden</span>
      <span class:ok={pr.belegt === pr.absaetze} class:hinweis={pr.belegt < pr.absaetze}>
        <i class="fa-solid {pr.belegt === pr.absaetze ? 'fa-circle-check' : 'fa-triangle-exclamation'}"></i> {pr.belegt === pr.absaetze ? "jeder Absatz belegt" : `${pr.absaetze - pr.belegt} ohne Beleg`}</span>
      {#if saetze}
        <span class="hinweis"><i class="fa-solid fa-triangle-exclamation"></i> {saetze} {saetze === 1 ? "Satz steht" : "Sätze stehen"} so nicht im Original</span>
        <span class="rechts"><button class="knopf still" disabled={!!auftrag} onclick={() => anstossen(probe!.eintrag, ohneBeleg)}>
          <i class="fa-solid fa-rotate"></i>{saetze === 1 ? "Diesen Satz neu schreiben lassen" : "Diese Sätze neu schreiben lassen"}</button></span>
      {:else}
        <span class="ok"><i class="fa-solid fa-circle-check"></i> jeder Satz steht so im Original</span>
      {/if}
      {/if}
    </div>
    {#if ansicht === "nebeneinander"}
      <div class="exp-vergleich">
        <div class="exp-spalte exp-original" bind:this={original}>
          <div class="exp-spaltenkopf"><i class="fa-solid fa-book-open"></i>Original<span class="rechts">{probe.quelle}, {zahl(probe.zeichen_original)} Zeichen{probe.original.length && probe.artikel.zeichen_original > probe.original.reduce((n, o) => n + o.text.length, 0) ? ", gezeigt der Anfang" : ""}</span></div>
          {#each probe.original as o (o.nr)}
            {#if o.ueberschrift}<h3>{o.ueberschrift}</h3>{/if}
            <p class:belegt={leuchtet.includes(o.nr)}><span class="exp-nr-klein">{o.nr}</span>{o.text}</p>
          {/each}
        </div>
        <div class="exp-spalte">
          <div class="exp-spaltenkopf"><i class="fa-solid fa-wand-magic-sparkles exp-ki"></i>Im {probe.vorlage_titel}<span class="rechts">{zahl(ergebnisZeichen)} Zeichen, rund {probe.seiten} {probe.seiten === 1 ? "Seite" : "Seiten"} A5</span></div>
          {@render ergebnis(probe)}
        </div>
      </div>
    {:else}
      <div class="exp-buchseite" class:serifen={vorlage?.gestaltung.schrift !== "ohne"} style="--exp-farbe: var(--{vorlage?.gestaltung.farbe ?? 'petrol'})">
        {@render ergebnis(probe)}
      </div>
    {/if}
  {:else if !geladen}
    <p class="leer-hinweis">Liest das Probekapitel ...</p>
  {:else if !auftrag}
    <p class="leer-hinweis">Noch kein Probekapitel. Auf der Seite Als Buch "Probekapitel ansehen" wählen{artikel.length ? ", oder hier einen Artikel probieren" : ""}.</p>
    {#if artikel.length}<button class="knopf primaer" onclick={() => anstossen(artikel[0].id)}><i class="fa-solid fa-flask"></i>Probekapitel mit {artikel[0].titel}</button>{/if}
  {:else}
    <p class="leer-hinweis">Die KI formt den Anfang des Artikels um; das Ergebnis erscheint hier, sobald es fertig ist.</p>
  {/if}
</div>
