<script lang="ts">
  // Eine Kategorie eines Buchs mit Kategorien (WIKI-75): Beschreibung, Oberkategorien, Unterkategorien als Kacheln und
  // alle Seiten darin, nach Anfangsbuchstaben gruppiert (wie in der Quelle, aber vollständig), mit Filter im stehenden Kopf.
  import { Seitenkopf } from "appkern-oberflaeche";
  import type { Artikel, Kategorieverweis } from "../lib/typen";
  import { lesen, lesenZiel } from "../lib/ziele";
  import Kachel from "./Kachel.svelte";

  let { artikel }: { artikel: Artikel } = $props();
  const k = $derived(artikel.kategorie!);
  let filter = $state("");
  const f = $derived(filter.trim().toLowerCase());
  const seiten = $derived(f ? k.seiten.filter((s) => s.titel.toLowerCase().includes(f)) : k.seiten);
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
          {#if k.seiten.length > 12}
            <label class="suchfeld kat-filter"><i class="fa-solid fa-filter"></i>
              <input type="search" bind:value={filter} placeholder="In {k.seiten.length} Seiten filtern" aria-label="Seiten filtern" /></label>
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
          {#each k.unter as u (u.pfad)}<Kachel art="text" titel={u.titel} adresse={ziel(u.pfad)} ziel={() => lesen(artikel.buch, u.pfad)} />{/each}
        </div>
      </section>
    {/if}
    {#if k.seiten.length}
      <section class="kat-gruppe">
        <h2><i class="fa-solid fa-file-lines"></i>Seiten<span class="kat-zahl">{f ? `${seiten.length} von ${k.seiten.length}` : k.seiten.length}</span></h2>
        <div class="kat-buchstaben">
          {#each gruppen as [b, liste] (b)}
            <div class="kat-buchstabe">
              <h3>{b}</h3>
              <ul>{#each liste as s (s.pfad)}<li><a href={ziel(s.pfad)} onclick={(e) => folgen(e, s.pfad)}>{s.titel}</a></li>{/each}</ul>
            </div>
          {/each}
        </div>
        {#if f && !seiten.length}<p class="ueb-leise">Keine Seite passt zu "{filter}".</p>{/if}
      </section>
    {/if}
  </div>
</div>
