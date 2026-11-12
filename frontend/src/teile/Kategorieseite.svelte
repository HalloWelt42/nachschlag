<script lang="ts">
  // Eine Kategorie eines Buchs mit Kategorien (WIKI-75): Beschreibung, Oberkategorien, Unterkategorien als Kacheln und
  // alle Seiten darin, nach Anfangsbuchstaben gruppiert (wie in der Quelle, aber vollständig), mit Filter im stehenden Kopf.
  // Kategorien aus der Kategoriendatei (Wikipedia) können riesig sein: die ersten Seiten kommen mit, weitere auf Knopfdruck.
  import { Seitenkopf } from "appkern-oberflaeche";
  import { kategorieSeitenHolen } from "../lib/schnittstelle";
  import type { Artikel, Kategorieverweis } from "../lib/typen";
  import { lesen, lesenZiel } from "../lib/ziele";
  import Kachel from "./Kachel.svelte";

  let { artikel }: { artikel: Artikel } = $props();
  const k = $derived(artikel.kategorie!);
  let filter = $state("");
  let nachgeladen = $state<Kategorieverweis[]>([]);
  let laedt = $state(false);
  $effect(() => {
    void artikel.pfad;
    nachgeladen = [];
  });
  const alle = $derived([...k.seiten, ...nachgeladen]);
  const gesamt = $derived(Math.max(k.seiten_gesamt ?? 0, alle.length));
  const fehlen = $derived(gesamt - alle.length);
  const f = $derived(filter.trim().toLowerCase());
  const seiten = $derived(f ? alle.filter((s) => s.titel.toLowerCase().includes(f)) : alle);
  async function weitere() {
    const letzte = alle.at(-1)?.nr;
    if (letzte == null || laedt) return;
    laedt = true;
    try {
      nachgeladen = [...nachgeladen, ...(await kategorieSeitenHolen(artikel.buch, artikel.pfad, letzte))];
    } finally {
      laedt = false;
    }
  }
  const zahl = (n: number) => n.toLocaleString("de-DE");
  /** Nach dem ersten Buchstaben (Umlaute bei ihrem Grundbuchstaben, Ziffern und Zeichen unter #) */
  const gruppen = $derived.by(() => {
    const je = new Map<string, Kategorieverweis[]>();
    for (const s of seiten) {
      const b = s.titel.normalize("NFD").charAt(0).toUpperCase();
      const g = /[A-Z]/.test(b) ? b : "#";
      je.set(g, [...(je.get(g) ?? []), s]);
    }
    return [...je.entries()].sort(([a], [b]) => (a === "#" ? -1 : b === "#" ? 1 : a.localeCompare(b, "de")));
  });
  const ziel = (pfad: string) => "/" + lesenZiel(artikel.buch, pfad);
  function folgen(e: MouseEvent, pfad: string) {
    if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault();
    lesen(artikel.buch, pfad);
  }
</script>

<div class="rollfeld" style="padding: 0">
  <div class="kat-seite kat-kategorie mit-kopf">
    <Seitenkopf rand="var(--kat-rand)">
      {#snippet kopf()}
        <div class="kat-kopfzeile">
          {#if k.ober.length}
            <span class="kat-ober"><i class="fa-solid fa-turn-up"></i>
              {#each k.ober as o (o.pfad)}<a href={ziel(o.pfad)} onclick={(e) => folgen(e, o.pfad)}>{o.titel}</a>{/each}</span>
          {/if}
          {#if alle.length > 12}
            <label class="suchfeld kat-filter"><i class="fa-solid fa-filter"></i>
              <input name="filter" type="search" bind:value={filter} placeholder="In {zahl(alle.length)} {fehlen ? 'geladenen ' : ''}Seiten filtern" aria-label="Seiten filtern" /></label>
          {/if}
        </div>
      {/snippet}
    </Seitenkopf>
    {#if artikel.html}
      <!-- eslint-disable-next-line svelte/no-at-html-tags -- vom Baustein gesäubert -->
      <div class="artikel-text kat-beschreibung">{@html artikel.html}</div>
    {/if}
    {#if k.unter.length && !f}
      <section class="kat-gruppe">
        <h2><i class="fa-solid fa-folder-tree"></i>Unterkategorien<span class="kat-zahl">{k.unter.length}</span></h2>
        <div class="anl-kacheln text">
          {#each k.unter as u (u.pfad)}<Kachel art="text" titel={u.titel} untertitel={u.anzahl ? `${zahl(u.anzahl)} ${k.einheit ?? "Seiten"}` : ""}
              adresse={ziel(u.pfad)} ziel={() => lesen(artikel.buch, u.pfad)} />{/each}
        </div>
      </section>
    {/if}
    {#if alle.length}
      <section class="kat-gruppe">
        <h2><i class="fa-solid fa-file-lines"></i>Seiten<span class="kat-zahl">{f ? `${zahl(seiten.length)} von ${zahl(alle.length)}` : fehlen ? `${zahl(alle.length)} von ${zahl(gesamt)}` : zahl(alle.length)}</span></h2>
        <div class="kat-buchstaben">
          {#each gruppen as [b, liste] (b)}
            <div class="kat-buchstabe">
              <h3>{b}</h3>
              <ul>{#each liste as s (s.pfad)}<li><a href={ziel(s.pfad)} onclick={(e) => folgen(e, s.pfad)}>{s.titel}</a></li>{/each}</ul>
            </div>
          {/each}
        </div>
        {#if f && !seiten.length}<p class="ueb-leise">Keine Seite passt zu "{filter}".</p>{/if}
        {#if fehlen > 0}
          <button class="knopf kat-weitere" onclick={weitere} disabled={laedt}>
            <i class="fa-solid {laedt ? 'fa-spinner fa-spin' : 'fa-angles-down'}"></i>Weitere Seiten ({zahl(fehlen)} fehlen noch)</button>
        {/if}
      </section>
    {/if}
  </div>
</div>
