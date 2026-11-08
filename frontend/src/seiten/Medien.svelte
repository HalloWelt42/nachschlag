<script lang="ts">
  // Medien (Entwurf mockups/medien.html): Bilder zu einer Frage aus den Artikeln der Bücher, im Mauerwerk mit
  // Unterschrift und Herkunft; Wörter der Frage in der Unterschrift hervorgehoben. Tippen öffnet die große Ansicht.
  // Weg: /medien?frage=.
  import { gehe, geraet, navigation, seitenFehler } from "appkern-oberflaeche";
  import { untrack } from "svelte";
  import { hervorheben, medienSuchen, type Medienart, type Medienergebnis } from "../lib/medien";
  import Leuchtkasten from "../teile/Leuchtkasten.svelte";

  let eingabe = $state("");
  let ergebnis = $state.raw<Medienergebnis | null>(null);
  let laedt = $state(false);
  let fehler = $state("");
  let offen = $state<number | null>(null);
  let fehlen = $state<Record<string, true>>({});        // Bilder, die das Buch nicht mitbringt, zeigen wir nicht

  const sichtbar = $derived((ergebnis?.medien ?? []).filter((m) => !fehlen[m.bild]));
  // Filter (WIKI-24): Art und nur groß geladene; ein Wechsel sucht neu
  const ARTEN: [Medienart, string][] = [["", "Alle"], ["bild", "Bilder"], ["karte", "Karten"], ["ton", "Töne"]];
  let art = $state<Medienart>("");
  let nurGross = $state(false);
  const bilder = $derived(sichtbar.filter((m) => m.art !== "ton"));
  const toene = $derived(sichtbar.filter((m) => m.art === "ton"));
  function filtern(neu: Partial<{ art: Medienart; nurGross: boolean }>) {
    if (neu.art !== undefined) art = neu.art;
    if (neu.nurGross !== undefined) nurGross = neu.nurGross;
    if (frage) void suchen(frage);
  }

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
      ergebnis = await medienSuchen(f, art, nurGross);
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
        <div class="segment">
          {#each ARTEN as [a, wort] (a)}<button class:aktiv={art === a} onclick={() => filtern({ art: a })}>{wort}</button>{/each}
        </div>
        <button class="chip" class:an={nurGross} aria-pressed={nurGross} disabled={art === "ton"} onclick={() => filtern({ nurGross: !nurGross })}
                title="Nur Bilder, deren große Fassung der Bildholer schon geholt hat"><i class="fa-solid fa-expand"></i>nur groß geladene</button>
      </div>
      {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
      {#if !frage}
        <p class="leer-hinweis">Einen Begriff eingeben: die Bilder kommen aus den Artikeln, die ihn behandeln, solche mit dem Begriff in der Unterschrift zuerst.</p>
      {:else if laedt && !ergebnis}
        <p class="leer-hinweis">Sucht Bilder ...</p>
      {:else if ergebnis}
        <div class="trefferzeile" class:laedt>
          {#if ergebnis.medien.length}
            <span>{bilder.length} {art === "karte" ? "Karten" : "Bilder"}{toene.length ? `, ${toene.length} Töne` : ""} aus {artikelZahl(ergebnis.artikel)}</span>
            <span class="weg">{ergebnis.passend} mit "{ergebnis.frage}" in der Unterschrift</span>
          {:else}
            <span>Keine Bilder in den Artikeln zu "{ergebnis.frage}".</span>
          {/if}
        </div>
        {#if toene.length}
          <div class="toene">
            {#each toene as t (t.bild + t.pfad)}
              <div class="ton"><i class="fa-solid fa-volume-high"></i>
                <span class="ton-text"><b>{t.unterschrift || t.datei}</b><span class="herkunft-m"><i class="fa-solid fa-book-open"></i>{t.artikel}</span></span>
                <audio controls preload="none" src={t.bild}></audio></div>
            {/each}
          </div>
        {/if}
        <div class="mediengitter">
          {#each bilder as m, i (m.bild + m.pfad)}
            <button class="medium" onclick={() => (offen = i)} title="Groß ansehen">
              <img src={m.bild} alt={m.unterschrift} loading="lazy" width={m.breite || undefined} height={m.hoehe || undefined}
                   onerror={() => (fehlen = { ...fehlen, [m.bild]: true })} />
              {#if m.breite}<span class="groesse">{m.gross ? "groß · " : ""}{m.art === "karte" ? "Karte · " : ""}{m.breite} px</span>{/if}
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
  <Leuchtkasten medien={bilder} start={offen} titel={`zu "${ergebnis.frage}"`} onzu={() => (offen = null)} />
{/if}
