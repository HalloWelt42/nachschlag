<script lang="ts">
  // Notizen (Entwurf mockups/notizen.html): alle Notizen über alle Bücher, nach Artikel gruppiert. Eine Notiz hängt am
  // Artikel oder an einer markierten Stelle (Zitat). Rechts die gewählte Notiz zum Bearbeiten (Leiste des Appkerns,
  // schmaler als Tafel); am Telefon im Blatt von unten. Speichert von selbst, Zur Stelle springt in den Artikel.
  import { onMount } from "svelte";
  import { Auswahl, geraet, Leiste, leisteOeffnen } from "appkern-oberflaeche";
  import { bibliothekLaden, buchName } from "../lib/bibliothek.svelte";
  import { meins, meinsLaden, wann, type Notiz } from "../lib/meins.svelte";
  import { lesen } from "../lib/ziele";
  import { themen, themenLaden, themenVon } from "../lib/themen.svelte";
  import NotizBearbeiten from "../teile/NotizBearbeiten.svelte";
  import NotizBlatt from "../teile/NotizBlatt.svelte";

  type Filter = "alle" | "stellen" | "artikel";
  const FILTER: [Filter, string][] = [["alle", "Alle"], ["stellen", "An Stellen"], ["artikel", "Am Artikel"]];

  let filter = $state<Filter>("alle");
  let suche = $state("");
  let thema = $state("");                                     // Kennung; leer: alle
  let reihenfolge = $state<"neu" | "alt">("neu");
  let gewaehltId = $state("");
  let blattOffen = $state(false);

  const art = (n: Notiz): Exclude<Filter, "alle"> => (n.zitat ? "stellen" : "artikel");
  const zahlen = $derived({ alle: meins.notizen.length, stellen: meins.notizen.filter((n) => n.zitat).length,
                            artikel: meins.notizen.filter((n) => !n.zitat).length } as Record<Filter, number>);
  const gewaehlt = $derived(meins.notizen.find((n) => n.id === gewaehltId) ?? null);

  // Nach Anlage geordnet (nicht nach Änderung: sonst spränge eine Notiz beim Schreiben nach oben), nach Artikel gruppiert
  const gruppen = $derived.by(() => {
    const wort = suche.trim().toLowerCase();
    const passend = meins.notizen
      .filter((n) => (filter === "alle" || art(n) === filter) && (!wort || `${n.titel} ${n.zitat} ${n.text}`.toLowerCase().includes(wort))
                     && (!thema || themenVon(n.buch_name, n.pfad).some((z) => z.thema === thema)))
      .sort((a, b) => (reihenfolge === "neu" ? b.angelegt.localeCompare(a.angelegt) : a.angelegt.localeCompare(b.angelegt)));
    const nachArtikel = new Map<string, Notiz[]>();
    for (const n of passend) {
      const k = `${n.buch_name}\u0000${n.pfad}`;
      nachArtikel.set(k, [...(nachArtikel.get(k) ?? []), n]);
    }
    return [...nachArtikel].map(([schluessel, notizen]) => ({ schluessel, notizen, erste: notizen[0] }));
  });

  function waehlen(n: Notiz) {
    gewaehltId = n.id;
    if (geraet.mobil) blattOffen = true;
    else leisteOeffnen();             // schmaler als die Leiste breit steht, fährt sie herein
  }

  const zurStelle = (n: Notiz) => n.buch && lesen(n.buch, n.pfad, { notiz: n.id });

  onMount(async () => {
    void bibliothekLaden();             // Namen der Bücher statt Kennungen
    void themenLaden(true);
    await meinsLaden(true);
    if (!gewaehltId && !geraet.mobil) gewaehltId = gruppen[0]?.erste.id ?? "";
  });
</script>

<div class="inhalt-stufe" data-schrift="klein">
  <div class="notizseite">
    <div class="rollfeld" style="padding: 0">
      <div class="meins-seite">
        <div class="meins-kopf">
          {#if !geraet.mobil}<h1>Notizen</h1>{/if}          <!-- am Telefon steht der Titel im Kopf -->
          <div class="segment meins-filter">
            {#each FILTER as [f, name] (f)}
              <button class:aktiv={filter === f} onclick={() => (filter = f)}>{name} {zahlen[f]}</button>
            {/each}
          </div>
          <label class="suchfeld meins-suche"><i class="fa-solid fa-magnifying-glass"></i>
            <input type="search" placeholder="In Notizen und Zitaten suchen" bind:value={suche} aria-label="In Notizen und Zitaten suchen" /></label>
          {#if themen.liste.length}
            <Auswahl bind:wert={thema} symbol="fa-layer-group" titel="Nur Notizen an Artikeln dieses Themas"
                     optionen={[{ wert: "", titel: "Thema: alle" }, ...themen.liste.map((t) => ({ wert: t.id, titel: `Thema: ${t.titel}` }))]} />
          {/if}
          <Auswahl bind:wert={reihenfolge} symbol="fa-arrow-down-wide-short" titel="Reihenfolge"
                   optionen={[{ wert: "neu", titel: "Neueste zuerst" }, { wert: "alt", titel: "Älteste zuerst" }]} />
        </div>
        {#if meins.geladen && !meins.notizen.length}
          <p class="leer-hinweis">Noch keine Notizen. Im Artikel Text markieren und "Notiz" wählen, oder oben "Notiz" für den ganzen Artikel; Notizen gelten auf allen deinen Geräten.</p>
        {:else if meins.geladen && !gruppen.length}
          <p class="leer-hinweis">Keine Notiz passt zu Filter und Suche.</p>
        {/if}
        {#each gruppen as g (g.schluessel)}
          <section class="notiz-gruppe">
            <button class="gruppenkopf" disabled={!g.erste.buch} onclick={() => lesen(g.erste.buch, g.erste.pfad)} title="Artikel öffnen">
              {#if g.erste.bild}<img src={g.erste.bild} alt="" loading="lazy" />{:else}<span class="ohne-bild"><i class="fa-solid fa-file-lines"></i></span>{/if}
              <b>{g.erste.titel}</b><span class="neben">{g.notizen.length} {g.notizen.length === 1 ? "Notiz" : "Notizen"}</span>
              <span class="marke-buch"><i class="fa-solid fa-book"></i>{g.erste.buch ? buchName(g.erste.buch) : g.erste.buch_name}</span>
            </button>
            {#each g.notizen as n (n.id)}
              <div class="notiz-eintrag" class:gewaehlt={n.id === gewaehltId} role="button" tabindex="0" onclick={() => waehlen(n)}
                   onkeydown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), waehlen(n))}>
                {#if n.zitat}<div class="zitat">"{n.zitat}"</div>{/if}
                <div class="text" class:ohne-text={!n.text}>{n.text || "Markierung ohne Notiz"}</div>
                <div class="wo">
                  {#if n.zitat}<span><i class="fa-solid fa-paragraph"></i>{n.abschnitt || "Einleitung"}</span>
                  {:else}<span><i class="fa-solid fa-file-lines"></i>am ganzen Artikel</span>{/if}
                  <span class="zahl">{wann(n.angelegt)}</span>
                  {#each themenVon(n.buch_name, n.pfad) as z (z.thema)}<span class="etikettchen">{z.titel}</span>{/each}
                </div>
                <div class="notiz-aktionen">
                  <button class="rund" title={n.zitat ? "Zur Stelle" : "Zum Artikel"} disabled={!n.buch}
                          onclick={(e) => { e.stopPropagation(); zurStelle(n); }}><i class="fa-solid fa-arrow-up-right-from-square"></i></button>
                </div>
              </div>
            {/each}
          </section>
        {/each}
      </div>
    </div>
    {#if !geraet.mobil}
      <Leiste>
        <div class="leiste-kopf"><h2>Notiz bearbeiten</h2></div>
        <div class="rollfeld">
          {#if gewaehlt}
            <NotizBearbeiten notiz={gewaehlt} zurStelle={gewaehlt.buch ? () => zurStelle(gewaehlt!) : undefined} onweg={() => (gewaehltId = "")} />
          {:else}
            <p class="leer-hinweis">Links eine Notiz wählen.</p>
          {/if}
        </div>
      </Leiste>
    {/if}
  </div>
</div>
{#if geraet.mobil && blattOffen && gewaehlt}
  <NotizBlatt notiz={gewaehlt} zurStelle={gewaehlt.buch ? () => zurStelle(gewaehlt!) : undefined} onzu={() => (blattOffen = false)} />
{/if}
