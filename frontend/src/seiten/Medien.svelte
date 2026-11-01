<script lang="ts">
  // Medien (Entwurf mockups/medien.html): Bilder zu einer Frage aus den Artikeln der Bücher, im Mauerwerk mit
  // Unterschrift und Herkunft; Wörter der Frage in der Unterschrift hervorgehoben. Tippen öffnet die große Ansicht.
  // Weg: /medien?frage=.
  import { gehe, geraet, navigation, seitenFehler } from "appkern-oberflaeche";
  import { untrack } from "svelte";
  import { hervorheben, medienSuchen, type Medienergebnis } from "../lib/medien";
  import Leuchtkasten from "../teile/Leuchtkasten.svelte";

  let eingabe = $state("");
  let ergebnis = $state.raw<Medienergebnis | null>(null);
  let laedt = $state(false);
  let fehler = $state("");
  let offen = $state<number | null>(null);
  let fehlen = $state<Record<string, true>>({});        // Bilder, die das Buch nicht mitbringt, zeigen wir nicht

  const sichtbar = $derived((ergebnis?.medien ?? []).filter((m) => !fehlen[m.bild]));

  const frage = $derived(new URLSearchParams(navigation.suche).get("frage") ?? "");

  $effect(() => {
    const f = frage;
    untrack(() => {
      eingabe = f;
      void suchen(f);
    });
  });

  async function suchen(f: string) {
    offen = null;
    if (!f.trim()) {
      ergebnis = null;
      return;
    }
    laedt = true;
    try {
      ergebnis = await medienSuchen(f);
      fehler = "";
    } catch (x) {
      fehler = seitenFehler(x);
    } finally {
      laedt = false;
    }
  }

  function absenden(e: SubmitEvent) {
    e.preventDefault();
    if (eingabe.trim()) gehe(`medien?${new URLSearchParams({ frage: eingabe.trim() })}`);
  }

  const artikelZahl = (n: number) => `${n} ${n === 1 ? "Artikel" : "Artikeln"}`;
</script>

<div class="inhalt-stufe" data-schrift="klein">
  <div class="rollfeld" style="padding: 0">
    <div class="medien-seite">
      <div class="meins-kopf">
        {#if !geraet.mobil}<h1>Medien</h1>{/if}          <!-- am Telefon steht der Titel im Kopf -->
        <form class="suchfeld medien-suche" onsubmit={absenden} role="search">
          <i class="fa-solid fa-magnifying-glass"></i>
          <input type="search" bind:value={eingabe} placeholder="Bilder zu einem Begriff" aria-label="Bilder zu einem Begriff" />
        </form>
      </div>
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
      {#if !frage}
        <p class="leer-hinweis">Einen Begriff eingeben: die Bilder kommen aus den Artikeln, die ihn behandeln, solche mit dem Begriff in der Unterschrift zuerst.</p>
      {:else if laedt && !ergebnis}
        <p class="leer-hinweis">Sucht Bilder ...</p>
      {:else if ergebnis}
        <div class="trefferzeile" class:laedt>
          {#if ergebnis.medien.length}
            <span>{sichtbar.length} Bilder aus {artikelZahl(ergebnis.artikel)}</span>
            <span class="weg">{ergebnis.passend} mit "{ergebnis.frage}" in der Unterschrift</span>
          {:else}
            <span>Keine Bilder in den Artikeln zu "{ergebnis.frage}".</span>
          {/if}
        </div>
        <div class="mediengitter">
          {#each sichtbar as m, i (m.bild + m.pfad)}
            <button class="medium" onclick={() => (offen = i)} title="Groß ansehen">
              <img src={m.bild} alt={m.unterschrift} loading="lazy" width={m.breite || undefined} height={m.hoehe || undefined}
                   onerror={() => (fehlen = { ...fehlen, [m.bild]: true })} />
              {#if m.breite}<span class="groesse">{m.breite} px</span>{/if}
              <span class="unter">
                {#if m.unterschrift}{#each hervorheben(m.unterschrift, ergebnis.frage) as teil, ti (ti)}{#if teil.treffer}<em>{teil.text}</em>{:else}{teil.text}{/if}{/each}{/if}
                <span class="herkunft-m"><i class="fa-solid fa-book-open"></i>{m.artikel}</span>
              </span>
            </button>
          {/each}
        </div>
      {/if}
    </div>
  </div>
</div>
{#if offen !== null && ergebnis}
  <Leuchtkasten medien={sichtbar} start={offen} titel={`zu "${ergebnis.frage}"`} onzu={() => (offen = null)} />
{/if}
