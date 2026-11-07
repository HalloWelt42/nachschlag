<script lang="ts">
  // Anleitungen finden (iFixit, WIKI-64; Entwurf ifixit-anleitungen.html): Startseite eines Anleitungsbuchs und Ziel der
  // Suche darin. Oben stehend Suche und Filter (Art, Sprache, Schwierigkeit, Zeit, Ich habe, Reihenfolge); alles steht in
  // der Adresse (zurück, teilen, neu laden). Ohne Filter zeigt die Seite die Kategorien der Quelle, mit Filtern die
  // Treffer: links die Geräte des gewählten Asts und die Bauteile mit Zahl, rechts die Liste, nachgeladen beim Rollen.
  // Ich habe: die eigenen Werkzeuge (in Meins, auf allen Geräten); dann zählen nur Anleitungen, für die sie reichen.
  import { Auswahl, gehe, Nachladen, navigation, seitenFehler, Seitenkopf } from "appkern-oberflaeche";
  import { untrack } from "svelte";
  import { zahl } from "../lib/bibliothek.svelte";
  import { meins, vorliebeSetzen } from "../lib/meins.svelte";
  import { anleitungenFinden, werkzeugeHolen } from "../lib/schnittstelle";
  import type { Anleitungsfrage, Anleitungsfunde, Anleitungsreihenfolge, Artikel, Suchart, Werkzeugeintrag } from "../lib/typen";
  import { lesen, lesenZiel } from "../lib/ziele";
  import Geraeteseite from "./Geraeteseite.svelte";
  import Kachel from "./Kachel.svelte";

  let { artikel }: { artikel: Artikel } = $props();

  const ANZAHL = 30;
  const WERKZEUGE = "anleitung.werkzeuge";
  /** Schlüssel der Adresse; steht einer davon da, zeigt die Seite Treffer statt Kategorien */
  const FILTER = ["text", "art", "en", "stufe", "zeit", "ich", "mehr", "geraet", "bauteil", "folge"];
  const ARTEN: { wert: Suchart; titel: string }[] = [{ wert: "anleitung", titel: "Anleitungen" }, { wert: "zerlegung", titel: "Zerlegungen" },
                                                      { wert: "geraet", titel: "Geräte" }];
  const STUFEN = ["sehr einfach", "einfach", "mittel", "schwierig", "sehr schwierig"];
  const ZEITEN = [{ wert: "", titel: "Jeder Zeitaufwand" }, { wert: "15", titel: "bis 15 Minuten" }, { wert: "30", titel: "bis 30 Minuten" },
                  { wert: "60", titel: "bis 1 Stunde" }, { wert: "120", titel: "bis 2 Stunden" }, { wert: "240", titel: "bis 4 Stunden" }];
  const FOLGEN = [{ wert: "passend", titel: "Passendste zuerst" }, { wert: "einfach", titel: "Einfachste zuerst" },
                  { wert: "schnell", titel: "Schnellste zuerst" }, { wert: "titel", titel: "Nach Titel" }];

  const q = $derived(new URLSearchParams(navigation.suche));
  const aktiv = $derived(FILTER.some((k) => q.has(k)));
  const meine = $derived((meins.vorlieben[WERKZEUGE] ?? "").split("\n").filter(Boolean));
  const ich = $derived(q.get("ich") === "1" && meine.length > 0);
  const frage = $derived<Anleitungsfrage>({
    text: q.get("text") ?? "", art: (q.get("art") as Suchart) || "anleitung", sprachen: q.get("en") === "1" ? ["de", "en"] : ["de"],
    schwierigkeit: q.get("stufe") ? [Number(q.get("stufe"))] : [], zeit_bis: Number(q.get("zeit")) || null,
    werkzeuge: ich ? meine : [], mehr_noetig: q.get("mehr") === "1", geraet: q.get("geraet") ?? "", bauteil: q.get("bauteil") ?? "",
    reihenfolge: (q.get("folge") as Anleitungsreihenfolge) || "passend", ab: 0, anzahl: ANZAHL });

  /** Filter in die Adresse; leere Werte fallen weg. `ersetzen`: beim Tippen kein neuer Eintrag im Verlauf. */
  function setze(werte: Record<string, string | null>, ersetzen = false) {
    const p = new URLSearchParams(navigation.suche);
    for (const [k, w] of Object.entries(werte)) {
      if (w) p.set(k, w);
      else p.delete(k);
    }
    const s = p.toString();
    gehe(`${navigation.seite}/${navigation.teile.join("/")}${s ? "?" + s : ""}`, ersetzen);
  }

  // Suchfeld: tippt in die Adresse, kurz verzögert
  let eingabe = $state("");
  $effect(() => {
    const text = q.get("text") ?? "";
    untrack(() => { if (text !== eingabe.trim()) eingabe = text; });
  });
  let tippen: ReturnType<typeof setTimeout> | undefined;
  function getippt() {
    clearTimeout(tippen);
    tippen = setTimeout(() => setze({ text: eingabe.trim() || null }, q.has("text")), 300);
  }

  // Treffer laden: neu bei jeder Änderung der Frage, weitere beim Rollen
  let funde = $state.raw<Anleitungsfunde | null>(null);
  let laedt = $state(false);
  let fehler = $state("");
  let stand = 0;
  async function laden(weiter = false) {
    const mein = ++stand;
    laedt = true;
    try {
      const geladen = weiter && funde ? (frage.art === "geraet" ? funde.geraete.length : funde.anleitungen.length) : 0;
      const neu = await anleitungenFinden(artikel.buch, { ...frage, ab: geladen });
      if (mein !== stand) return;
      funde = weiter && funde ? { ...neu, anleitungen: [...funde.anleitungen, ...neu.anleitungen], geraete: [...funde.geraete, ...neu.geraete] } : neu;
      fehler = "";
    } catch (f) {
      if (mein === stand) fehler = seitenFehler(f);
    } finally {
      if (mein === stand) laedt = false;
    }
  }
  // auch ohne Filter: der Bestand im Kopf und ob der Index schon da ist
  $effect(() => {
    void JSON.stringify(frage);
    untrack(() => void laden());
  });

  // Ich habe: Auswahl der eigenen Werkzeuge in einem Band unter dem Kopf
  let wahlOffen = $state(false);
  let werkzeuge = $state.raw<Werkzeugeintrag[]>([]);
  let werkzeugFilter = $state("");
  async function wahlUmschalten() {
    wahlOffen = !wahlOffen;
    if (wahlOffen && !werkzeuge.length) werkzeuge = await werkzeugeHolen(artikel.buch, frage.sprachen).catch(() => []);
  }
  const sichtbar = $derived(werkzeuge.filter((w) => !werkzeugFilter || w.wort.toLowerCase().includes(werkzeugFilter.toLowerCase())).slice(0, 80));
  function werkzeugUmschalten(wort: string) {
    const neu = meine.includes(wort) ? meine.filter((w) => w !== wort) : [...meine, wort];
    void vorliebeSetzen(WERKZEUGE, neu.join("\n"));
    if (neu.length && !q.has("ich")) setze({ ich: "1" });
  }

  const geladen = $derived(funde ? (frage.art === "geraet" ? funde.geraete.length : funde.anleitungen.length) : 0);
  const einheit = $derived(frage.art === "geraet" ? "Geräte" : frage.art === "zerlegung" ? "Zerlegungen" : "Anleitungen");
  const sprachText = $derived(frage.sprachen.length > 1 ? "auf Deutsch und Englisch" : "auf Deutsch");
  const ziel = (pfad: string) => "/" + lesenZiel(artikel.buch, pfad);
</script>

{#snippet kopf()}
  <Seitenkopf rand="var(--a5)">
    {#snippet kopf()}
      {#if funde?.index}
        <div class="anl-titelzeile"><i class="fa-solid fa-screwdriver-wrench"></i>{zahl(funde.bestand_anleitungen)} Anleitungen {sprachText} ·
          {zahl(funde.bestand_geraete)} Geräte und Kategorien</div>
      {/if}
      <div class="katalog-filter">
        <label class="suchfeld katalog-suche"><i class="fa-solid fa-magnifying-glass"></i>
          <input type="search" bind:value={eingabe} oninput={getippt} placeholder="Gerät, Bauteil oder Fehler" aria-label="Anleitungen suchen" /></label>
        <div class="segment" role="radiogroup" aria-label="Art">
          {#each ARTEN as a (a.wert)}
            <button class:aktiv={aktiv && frage.art === a.wert} onclick={() => setze({ art: a.wert, bauteil: null })}>{a.titel}</button>
          {/each}
        </div>
        <div class="segment" role="radiogroup" aria-label="Sprache">
          <button class:aktiv={frage.sprachen.length === 1} onclick={() => setze({ en: null })}>Deutsch</button>
          <button class:aktiv={frage.sprachen.length > 1} onclick={() => setze({ en: "1" })}>auch Englisch</button>
        </div>
      </div>
      {#if frage.art !== "geraet"}
        <div class="katalog-filter">
          <div class="segment anl-schw" role="radiogroup" aria-label="Schwierigkeit">
            <button class:aktiv={!frage.schwierigkeit.length} onclick={() => setze({ stufe: null })}>jede Schwierigkeit</button>
            {#each STUFEN as s, i (s)}
              <button class:aktiv={frage.schwierigkeit[0] === i + 1} onclick={() => setze({ stufe: String(i + 1) })}>{s}</button>
            {/each}
          </div>
          <Auswahl wert={String(frage.zeit_bis ?? "")} symbol="fa-clock" titel="Zeitaufwand" optionen={ZEITEN} onwahl={(w: string) => setze({ zeit: w || null })} />
          <button class="chip wahl" class:an={ich} disabled={!meine.length} title={meine.length ? "Nur Anleitungen, für die meine Werkzeuge reichen" : "Erst Werkzeuge wählen"}
                  onclick={() => setze({ ich: ich ? null : "1", mehr: null })}><i class="fa-solid fa-toolbox"></i>Ich habe{#if meine.length}: {meine.length} Werkzeuge{/if}</button>
          <button class="chip wahl" class:an={wahlOffen} onclick={wahlUmschalten}><i class="fa-solid fa-sliders"></i>Werkzeuge wählen</button>
          <Auswahl wert={frage.reihenfolge} symbol="fa-arrow-down-wide-short" titel="Reihenfolge" optionen={FOLGEN} onwahl={(w: string) => setze({ folge: w === "passend" ? null : w })} />
          {#if aktiv}<button class="knopf still" onclick={() => gehe(`${navigation.seite}/${navigation.teile.join("/")}`)}><i class="fa-solid fa-xmark"></i>Zurücksetzen</button>{/if}
        </div>
      {/if}
      {#if wahlOffen}
        <div class="anl-werkzeugwahl">
          <label class="suchfeld"><i class="fa-solid fa-filter"></i><input type="search" bind:value={werkzeugFilter} placeholder="Werkzeug suchen" aria-label="Werkzeug suchen" /></label>
          <div class="anl-chips">
            {#each sichtbar as w (w.wort)}
              <button class="chip wahl" class:an={meine.includes(w.wort)} onclick={() => werkzeugUmschalten(w.wort)} title="{zahl(w.anleitungen)} Anleitungen brauchen es">
                {#if meine.includes(w.wort)}<i class="fa-solid fa-check"></i>{/if}{w.wort}</button>
            {/each}
          </div>
        </div>
      {/if}
    {/snippet}
  </Seitenkopf>
{/snippet}

{#snippet treffer()}
  {#if funde && !funde.index}
    <p class="anl-hinweis"><i class="fa-solid fa-hourglass-half"></i>Der eigene Index dieses Buchs entsteht noch (Seite Aufträge).
      Suche und Filter gehen, sobald er fertig ist; bis dahin führen die Kategorien zu den Anleitungen.</p>
  {:else if funde}
    {#if funde.einordnung.length}
      <nav class="anl-einordnung" aria-label="Einordnung">
        <button class="knopf still" onclick={() => setze({ geraet: null, bauteil: null })}><i class="fa-solid fa-sitemap"></i>Alle Geräte</button>
        {#each funde.einordnung.slice(1) as s (s.pfad)}<i class="fa-solid fa-chevron-right"></i><button class="knopf still" onclick={() => setze({ geraet: s.pfad })}>{s.titel}</button>{/each}
        <a class="knopf still" href={ziel(frage.geraet)} onclick={(e) => { e.preventDefault(); lesen(artikel.buch, frage.geraet); }}><i class="fa-solid fa-arrow-up-right-from-square"></i>Seite des Geräts</a>
      </nav>
    {/if}
    <div class="anl-treffer-seite">
      {#if frage.art !== "geraet" && (funde.unter.length || funde.bauteile.length || frage.bauteil)}
        <aside class="anl-facetten">
          {#if funde.unter.length}
            <div class="inhalt-titel">Geräte</div>
            <ul>{#each funde.unter as u (u.wert)}<li><button onclick={() => setze({ geraet: u.wert })}><span>{u.titel}</span><b>{zahl(u.zahl)}</b></button></li>{/each}</ul>
          {/if}
          {#if funde.bauteile.length || frage.bauteil}
            <div class="inhalt-titel">Bauteil</div>
            <ul>
              {#if frage.bauteil}<li class="an"><button onclick={() => setze({ bauteil: null })}><span>{frage.bauteil}</span><i class="fa-solid fa-xmark"></i></button></li>{/if}
              {#each funde.bauteile as b (b.wert)}<li><button onclick={() => setze({ bauteil: b.wert })}><span>{b.titel}</span><b>{zahl(b.zahl)}</b></button></li>{/each}
            </ul>
          {/if}
        </aside>
      {/if}
      <div class="anl-treffer">
        <div class="anl-trefferzahl">
          <b>{zahl(funde.gesamt)}</b> {einheit} {frage.art !== "geraet" ? sprachText : ""}{#if frage.text} zu <b>{frage.text}</b>{/if}{#if frage.bauteil}, Bauteil <b>{frage.bauteil}</b>{/if}{#if ich && !frage.mehr_noetig}, für die deine Werkzeuge reichen{/if}
          {#if ich && funde.brauchen_mehr}
            · <button class="knopf still" onclick={() => setze({ mehr: frage.mehr_noetig ? null : "1" })}>
              {frage.mehr_noetig ? "nur die, für die meine Werkzeuge reichen" : `weitere ${zahl(funde.brauchen_mehr)} brauchen mehr`}</button>
          {/if}
        </div>
        {#if frage.art === "geraet"}
          <div class="anl-kacheln">
            {#each funde.geraete as g (g.pfad)}
              <Kachel bild={g.bild} symbol="fa-mobile-screen" titel={g.titel} untertitel={g.anleitungen ? `${zahl(g.anleitungen)} Anleitungen` : ""}
                      adresse={ziel(g.pfad)} ziel={() => lesen(artikel.buch, g.pfad)} />
            {/each}
          </div>
        {:else}
          <div class="anl-liste">
            {#each funde.anleitungen as a (a.pfad)}
              <a class="anl-zeile-liste" href={ziel(a.pfad)} onclick={(e) => { if (e.button === 0 && !e.ctrlKey && !e.metaKey && !e.shiftKey) { e.preventDefault(); lesen(artikel.buch, a.pfad); } }}>
                {#if a.bild}<img src={a.bild} alt="" loading="lazy" />{:else}<span class="anl-ohne-bild"><i class="fa-solid fa-screwdriver-wrench"></i></span>{/if}
                <span class="t">{a.titel}{#if a.sprache === "en"} <span class="anl-sprache">EN</span>{/if}</span>
                {#if a.geraet}<span class="u">{a.geraet}{#if a.bauteil && a.bauteil !== a.titel} · {a.bauteil}{/if}</span>{/if}
                <span class="werte">
                  {#if a.schwierigkeit}<span class="w"><span class="anl-stufe" title="Schwierigkeit {a.schwierigkeit} von 5">{#each [1, 2, 3, 4, 5] as i (i)}<span class:an={i <= a.schwierigkeit}></span>{/each}</span>{a.schwierigkeit_text}</span>{/if}
                  {#if a.zeit}<span class="w"><i class="fa-regular fa-clock"></i>{a.zeit}</span>{/if}
                  <span class="w"><i class="fa-solid fa-list-ol"></i>{a.schritte} Schritte</span>
                </span>
                {#if a.werkzeuge.length}
                  <span class="anl-chips">{#each a.werkzeuge as w (w)}<span class="faehigkeit" class:fehlt={a.fehlt.includes(w)} title={a.fehlt.includes(w) ? "fehlt dir" : undefined}>{w}</span>{/each}</span>
                {/if}
              </a>
            {/each}
          </div>
        {/if}
        {#if !geladen && !laedt}<p class="anl-hinweis">Nichts gefunden. Weniger Filter oder auch Englisch helfen.</p>{/if}
        <Nachladen {geladen} gesamt={funde.gesamt} {laedt} {fehler} onmehr={() => laden(true)} einheit={einheit} />
      </div>
    </div>
  {:else if fehler}
    <p class="anl-hinweis">{fehler}</p>
  {/if}
{/snippet}

<Geraeteseite {artikel} {kopf} statt={aktiv ? treffer : undefined} />
