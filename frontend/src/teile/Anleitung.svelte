<script lang="ts">
  // Anleitung (iFixit, WIKI-64; Entwürfe ifixit-anleitung.html und ifixit-werkstatt.html). Zwei Ansichten, umschaltbar
  // und gemerkt (Meins, auf allen Geräten): Lesen zeigt alle Schritte untereinander (Bild links mit weiteren Bildern,
  // Zeilen rechts mit Farbpunkt zur Markierung im Bild oder Marke Hinweis, Vorsicht, Erinnerung), links die Schritte als
  // Inhalt, rechts der Steckbrief. Werkstatt zeigt einen Schritt groß, die Leiste aller Schritte, Zurück und Weiter (auch
  // Pfeiltasten und Leertaste) und merkt sich den Schritt über den Lesestand. Meine Erfahrung (WIKI-71): eigene Sterne,
  // die eigenen Notizen samt Fotos (das Notizblatt hält Lesen, `onnotiz` öffnet es) am Ende und nach dem letzten Schritt.
  import { onMount, untrack } from "svelte";
  import { bewerten, bewertungenHolen, lesestandHolen, lesestandMelden, meins, notizBildAdresse, vorliebeSetzen, wann,
           type Notiz } from "../lib/meins.svelte";
  import type { Anleitungsschritt, Anleitungszeile, Artikel } from "../lib/typen";
  import type { Medium } from "../lib/medien";
  import Einordnung from "./Einordnung.svelte";
  import Leuchtkasten from "./Leuchtkasten.svelte";
  import Sterne from "./Sterne.svelte";

  let { artikel, notizen = [], onnotiz, onnotizzeigen }: {
    artikel: Artikel; notizen?: Notiz[]; onnotiz?: () => void; onnotizzeigen?: (n: Notiz) => void } = $props();

  // Meine Bewertung dieser Anleitung (über Fassungen des Buchs hinweg)
  let sterne = $state(0);
  $effect(() => {
    const [b, p] = [artikel.buch, artikel.pfad];
    sterne = 0;
    bewertungenHolen(b).then((l) => { if (b === artikel.buch && p === artikel.pfad) sterne = l.find((x) => x.pfad === p)?.sterne ?? 0; })
      .catch(() => {});
  });
  async function sterneSetzen(n: number) {
    const vorher = sterne;
    sterne = n;
    try {
      await bewerten(artikel.buch, artikel.pfad, n);
    } catch {
      sterne = vorher;
    }
  }
  const a = $derived(artikel.anleitung!);
  const MARKE: Record<string, { symbol: string; wort: string }> = {
    hinweis: { symbol: "fa-circle-info", wort: "Hinweis" },
    vorsicht: { symbol: "fa-triangle-exclamation", wort: "Vorsicht" },
    erinnerung: { symbol: "fa-thumbtack", wort: "Erinnerung" },
  };
  const FARBEN = new Set(["red", "orange", "yellow", "green", "blue", "light_blue", "violet", "pink"]);
  const VORLIEBE = "anleitung.ansicht";

  const ansicht = $derived(meins.vorlieben[VORLIEBE] === "werkstatt" ? "werkstatt" : "lesen");
  let nr = $state(1);
  let bildwahl = $state<Record<number, number>>({});
  const schritt = $derived<Anleitungsschritt | undefined>(a.schritte[nr - 1]);
  const titelVon = (s: Anleitungsschritt) => s.titel || `Schritt ${s.nr}`;
  const kurz = (s: Anleitungsschritt) => s.titel || (s.zeilen[0]?.text ?? "").split(/[.:!]/)[0].slice(0, 48);
  const bild = (s: Anleitungsschritt) => s.bilder[bildwahl[s.nr] ?? 0] ?? "";
  const punkt = (z: Anleitungszeile) => (FARBEN.has(z.farbe) ? `f-${z.farbe}` : "");

  // Den Schritt der Werkstatt vom letzten Mal holen (auf jedem Gerät derselbe)
  onMount(async () => {
    const stand = await lesestandHolen(artikel.buch, artikel.pfad);
    const gemerkt = Number(stand?.abschnitt.match(/Schritt (\d+)/)?.[1] ?? 0);
    if (gemerkt >= 1 && gemerkt <= a.schritte.length) nr = gemerkt;
  });

  // Den Schritt merken, sobald er wechselt (nur in der Werkstatt; dort ist er der Lesestand)
  let seit = Date.now();
  $effect(() => {
    const n = nr;
    if (ansicht !== "werkstatt" || !a.schritte.length) return;
    untrack(() => {
      const jetzt = Date.now();
      void lesestandMelden({ buch: artikel.buch, pfad: artikel.pfad, titel: artikel.titel, bild: artikel.bild,
                             abschnitt: `Schritt ${n}`, anteil: Math.round((n / a.schritte.length) * 100) / 100,
                             sekunden: Math.min(86400, Math.round((jetzt - seit) / 1000)) });
      seit = jetzt;
    });
  });

  function gehe(n: number) {
    nr = Math.min(Math.max(1, n), Math.max(1, a.schritte.length));
  }

  function taste(e: KeyboardEvent) {
    if (ansicht !== "werkstatt" || grossbild !== null || (e.target as HTMLElement)?.closest("input, textarea, [contenteditable]")) return;
    if (e.key === "ArrowRight" || e.key === " ") { e.preventDefault(); gehe(nr + 1); }
    else if (e.key === "ArrowLeft") { e.preventDefault(); gehe(nr - 1); }
  }

  // Jedes Bild groß (WIKI-69): Hauptbild und alle Bilder der Schritte in einer Reihe, beim angetippten beginnend
  let grossbild = $state<number | null>(null);
  const medien = $derived<Medium[]>([
    ...(a.hauptbild ? [{ bild: a.hauptbild, abschnitt: "", unterschrift: artikel.titel }] : []),
    ...a.schritte.flatMap((s) => s.bilder.map((b, i) => ({ bild: b, abschnitt: `Schritt ${s.nr}`,
                                                            unterschrift: `${titelVon(s)}${s.bilder.length > 1 ? `, Bild ${i + 1}` : ""}` }))),
  ].map((m) => ({ ...m, buch: artikel.buch, pfad: artikel.pfad, artikel: artikel.titel, breite: 0, hoehe: 0,
                  datei: decodeURIComponent(m.bild.split("/").pop() ?? "") })));
  function grossZeigen(b: string) {
    grossbild = Math.max(0, medien.findIndex((m) => m.bild === b));
  }

  function zumSchritt(n: number) {
    document.getElementById(`schritt-${n}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
</script>

<svelte:window onkeydown={taste} />

{#snippet zeilen(liste: Anleitungszeile[])}
  <ul class="anl-zeilen">
    {#each liste as z, i (i)}
      <li class="anl-zeile stufe-{z.stufe}" class:mit-marke={!!z.marke} data-marke={z.marke || undefined}>
        {#if z.marke}<i class="fa-solid {MARKE[z.marke].symbol}" title={MARKE[z.marke].wort}></i>
        {:else}<span class="anl-punkt {punkt(z)}" title={z.farbe ? "Markierung im Bild" : undefined}></span>{/if}
        <span>{z.text}</span>
      </li>
    {/each}
  </ul>
{/snippet}

{#snippet bilder(s: Anleitungsschritt, gross: boolean)}
  {#if s.bilder.length}
    <figure class="anl-bild" class:gross>
      <button class="anl-bildknopf" title="Groß ansehen" onclick={() => grossZeigen(bild(s))}><img src={bild(s)} alt="Bild zu Schritt {s.nr}" loading="lazy" /></button>
      {#if s.bilder.length > 1}
        <div class="anl-vorschau">
          {#each s.bilder as b, i (b)}
            <button class:an={(bildwahl[s.nr] ?? 0) === i} title="Bild {i + 1}" onclick={() => (bildwahl = { ...bildwahl, [s.nr]: i })}>
              <img src={b} alt="" loading="lazy" /></button>
          {/each}
        </div>
      {/if}
    </figure>
  {/if}
{/snippet}

{#snippet erfahrung()}
  <section class="anl-erfahrung">
    <h2><i class="fa-solid fa-user-pen"></i>Meine Erfahrung</h2>
    <div class="anl-erf-zeile"><span class="blass">Wie lief es?</span><Sterne {sterne} onwahl={sterneSetzen} /></div>
    {#each notizen as n (n.id)}
      <button class="anl-erf-notiz" onclick={() => onnotizzeigen?.(n)}>
        {#if n.zitat}<span class="zitat">"{n.zitat}"</span>{/if}
        {#if n.text}<span class="text">{n.text}</span>{/if}
        {#if n.bilder.length}<span class="anl-erf-bilder">{#each n.bilder as b (b.id)}<img src={notizBildAdresse(n.id, b.id)} alt={b.name} loading="lazy" />{/each}</span>{/if}
        <span class="blass">{wann(n.geaendert)}</span>
      </button>
    {/each}
    {#if onnotiz}
      <button class="knopf still" onclick={onnotiz}><i class="fa-solid fa-camera"></i>{notizen.length ? "Notiz oder Foto ergänzen" : "Notiz oder Foto hinzufügen"}</button>
    {/if}
  </section>
{/snippet}

{#snippet stufe(n: number)}
  <span class="anl-stufe" title="Schwierigkeit {n} von 5">{#each [1, 2, 3, 4, 5] as i (i)}<span class:an={i <= n}></span>{/each}</span>
{/snippet}

<div class="anl-einordnung-rand"><Einordnung buch={artikel.buch} pfad={artikel.pfad} /></div>
<div class="anl-kopf">
  <span class="anl-werte">
    {#if a.schwierigkeit}<span>{@render stufe(a.schwierigkeit)}{a.schwierigkeit_text}</span>{/if}
    {#if a.zeit}<span><i class="fa-regular fa-clock"></i>{a.zeit}</span>{/if}
    <span><i class="fa-solid fa-list-ol"></i>{a.schritte.length} {a.schritte.length === 1 ? "Schritt" : "Schritte"}</span>
    {#if a.werkzeuge.length}<span><i class="fa-solid fa-toolbox"></i>{a.werkzeuge.length} Werkzeuge</span>{/if}
    {#if a.art === "zerlegung"}<span class="faehigkeit"><i class="fa-solid fa-magnifying-glass-plus"></i>Zerlegung</span>{/if}
  </span>
  {#if a.schritte.length}
    <span class="segment" role="radiogroup" aria-label="Ansicht der Anleitung">
      <button class:aktiv={ansicht === "lesen"} onclick={() => vorliebeSetzen(VORLIEBE, "")}><i class="fa-solid fa-book-open"></i> Lesen</button>
      <button class:aktiv={ansicht === "werkstatt"} onclick={() => vorliebeSetzen(VORLIEBE, "werkstatt")}><i class="fa-solid fa-screwdriver-wrench"></i> Werkstatt</button>
    </span>
  {/if}
</div>

{#if ansicht === "werkstatt" && schritt}
  <div class="anl-leiste" title="Alle Schritte: grün erledigt, hervorgehoben der aktuelle">
    {#each a.schritte as s (s.nr)}
      <button class:fertig={s.nr < nr} class:jetzt={s.nr === nr} title="Schritt {s.nr}" aria-label="Schritt {s.nr}" onclick={() => gehe(s.nr)}></button>
    {/each}
  </div>
  <div class="rollfeld anl-werkstatt-feld">
    <div class="anl-werkstatt">
      {@render bilder(schritt, true)}
      <div class="anl-w-text">
        <div class="anl-w-nr">Schritt {nr}<span>von {a.schritte.length}</span></div>
        {#if schritt.titel}<h2>{schritt.titel}</h2>{/if}
        {@render zeilen(schritt.zeilen)}
        {#if a.schritte[nr]}
          <button class="anl-w-naechster" onclick={() => gehe(nr + 1)}><span class="blass">Als Nächstes</span>
            {(a.schritte[nr].zeilen[0]?.text ?? "").slice(0, 140)}{(a.schritte[nr].zeilen[0]?.text ?? "").length > 140 ? " ..." : ""}</button>
        {:else}
          {#if a.abschluss}<div class="anl-w-naechster"><span class="blass">Abschluss</span>{a.abschluss}</div>{/if}
          {@render erfahrung()}
        {/if}
      </div>
    </div>
  </div>
  <div class="anl-steuer">
    <button class="knopf anl-gross" disabled={nr <= 1} onclick={() => gehe(nr - 1)}><i class="fa-solid fa-arrow-left"></i>Zurück</button>
    <span class="anl-stand"><b>Schritt {nr}</b> von {a.schritte.length}<span class="blass">, gemerkt auf allen Geräten</span></span>
    <span class="anl-taste"><kbd>←</kbd><kbd>→</kbd> oder <kbd>Leertaste</kbd></span>
    <button class="knopf haupt anl-gross" disabled={nr >= a.schritte.length} onclick={() => gehe(nr + 1)}>Weiter<i class="fa-solid fa-arrow-right"></i></button>
  </div>
{:else}
  <div class="rollfeld" style="padding: 0">
    <div class="anl-lesen" class:ohne-inhalt={!a.schritte.length}>
      {#if a.schritte.length}
        <nav class="inhalt anl-inhalt" aria-label="Schritte">
          <div class="inhalt-titel">{a.schritte.length} Schritte</div>
          <ol>
            {#each a.schritte as s (s.nr)}
              <li><a href="#schritt-{s.nr}" onclick={(e) => { e.preventDefault(); zumSchritt(s.nr); }}><span class="nr">{s.nr}</span>{kurz(s)}</a></li>
            {/each}
          </ol>
        </nav>
      {/if}
      <article class="artikel anl-artikel">
        <aside class="steckbrief anl-steckbrief">
          <div class="steckbrief-kopf">{a.art === "zerlegung" ? "Zerlegung" : "Anleitung"}</div>
          {#if a.hauptbild}<figure class="steckbrief-bild"><button class="anl-bildknopf" title="Groß ansehen" onclick={() => grossZeigen(a.hauptbild)}><img src={a.hauptbild} alt="" /></button></figure>{/if}
          <dl class="steckbrief-werte">
            {#if a.schwierigkeit}<dt>Schwierigkeit</dt><dd>{@render stufe(a.schwierigkeit)}{a.schwierigkeit_text}</dd>{/if}
            {#if a.zeit}<dt>Zeit</dt><dd>{a.zeit}</dd>{/if}
            <dt>Schritte</dt><dd>{a.schritte.length}</dd>
            {#if a.autor}<dt>Von</dt><dd>{a.autor}</dd>{/if}
          </dl>
          {#if a.werkzeuge.length}
            <div class="steckbrief-gruppe">Werkzeuge</div>
            <ul class="anl-werkzeuge">{#each a.werkzeuge as w (w.name)}<li>{#if w.bild}<img src={w.bild} alt="" loading="lazy" />{:else}<span class="ohne"><i class="fa-solid fa-screwdriver-wrench"></i></span>{/if}<span>{w.name}</span></li>{/each}</ul>
          {/if}
          {#if a.teile.length}
            <div class="steckbrief-gruppe">Ersatzteile</div>
            <ul class="anl-werkzeuge">{#each a.teile as w (w.name)}<li>{#if w.bild}<img src={w.bild} alt="" loading="lazy" />{:else}<span class="ohne"><i class="fa-solid fa-gear"></i></span>{/if}<span>{w.name}</span></li>{/each}</ul>
          {/if}
        </aside>
        {#if a.einleitung}<p class="anl-einleitung">{a.einleitung}</p>{/if}
        {#if !a.schritte.length}<p class="leer-hinweis">Diese Anleitung hat keine Schritte; die Quelle verweist dafür auf ein Video. Das Original zeigt den Verweis.</p>{/if}
        {#each a.schritte as s (s.nr)}
          <section class="anl-schritt" id="schritt-{s.nr}">
            <h2><span class="anl-nr">{s.nr}</span>{titelVon(s)}</h2>
            {@render bilder(s, false)}
            {@render zeilen(s.zeilen)}
          </section>
        {/each}
        {#if a.abschluss}<section class="anl-abschluss"><h2><i class="fa-solid fa-flag-checkered"></i>Abschluss</h2><p>{a.abschluss}</p></section>{/if}
        {@render erfahrung()}
      </article>
    </div>
  </div>
{/if}

{#if grossbild !== null}
  <Leuchtkasten {medien} start={grossbild} titel={`in ${artikel.titel}`} onzu={() => (grossbild = null)} />
{/if}
