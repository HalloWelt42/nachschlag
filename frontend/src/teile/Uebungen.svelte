<script lang="ts">
  // Startseite eines Übungsbuchs (freeCodeCamp, WIKI-66): die Kurse mit ihrer Einführung, darunter je Block die Aufgaben
  // als nummerierte Liste (aufklappbar; ein Kurs mit nur einem Block steht offen). Oben ein Filter über die Titel aller
  // Aufgaben, der die passenden Blöcke aufklappt.
  import { Seitenkopf } from "appkern-oberflaeche";
  import type { Artikel, Uebungsblock } from "../lib/typen";
  import { lesen, lesenZiel } from "../lib/ziele";

  let { artikel }: { artikel: Artikel } = $props();
  const kurse = $derived(artikel.kurse?.kurse ?? []);
  let filter = $state("");
  const f = $derived(filter.trim().toLowerCase());
  const passend = (b: Uebungsblock) => (f ? b.aufgaben.map((a, i) => ({ a, i })).filter(({ a }) => a.titel.toLowerCase().includes(f))
                                         : b.aufgaben.map((a, i) => ({ a, i })));
  const ziel = (pfad: string) => "/" + lesenZiel(artikel.buch, pfad);
  function folgen(e: MouseEvent, pfad: string) {
    if (e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault();
    lesen(artikel.buch, pfad);
  }
</script>

<div class="rollfeld" style="padding: 0">
  <div class="ueb-seite mit-kopf">
    <Seitenkopf rand="var(--ueb-rand)">
      {#snippet kopf()}
        <label class="suchfeld ueb-filter"><i class="fa-solid fa-filter"></i>
          <input type="search" bind:value={filter} placeholder="Aufgabe finden" aria-label="Aufgaben nach Titel filtern" /></label>
      {/snippet}
    </Seitenkopf>
    {#each kurse as k (k.kennung)}
      <section class="ueb-kurs">
        <h2><i class="fa-solid fa-graduation-cap"></i>{k.titel}</h2>
        {#if k.einleitung.length && !f}<p class="ueb-einleitung">{k.einleitung[0]}</p>{/if}
        {#each k.bloecke as b (b.kennung)}
          {@const liste = passend(b)}
          {#if liste.length}
            <details class="ueb-block" open={k.bloecke.length === 1 || !!f}>
              <summary><span>{b.titel}</span><span class="ueb-zahl">{f ? `${liste.length} von ${b.aufgaben.length}` : b.aufgaben.length}</span></summary>
              <ol class="ueb-aufgaben">
                {#each liste as { a, i } (a.pfad)}
                  <li><a href={ziel(a.pfad)} onclick={(e) => folgen(e, a.pfad)}><span class="ueb-nr">{i + 1}</span><span class="ueb-titel">{a.titel}</span></a></li>
                {/each}
              </ol>
            </details>
          {/if}
        {/each}
      </section>
    {/each}
    {#if f && !kurse.some((k) => k.bloecke.some((b) => passend(b).length))}<p class="ueb-leise">Keine Aufgabe passt zu "{filter}".</p>{/if}
  </div>
</div>
