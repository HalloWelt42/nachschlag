<script lang="ts">
  // Startseite, Variante A (Entwurf mockups/start-a.html): Suche in der Mitte, darunter Stöbern mit einem Zufallsfund
  // je Buch mit Lesedesign und die Bibliothek mit ihren Büchern und Fähigkeiten.
  import { onMount } from "svelte";
  import { seitenFehler } from "appkern-oberflaeche";
  import Suchfeld from "../teile/Suchfeld.svelte";
  import { bibliothek, bibliothekLaden, datum, sprache, zahl } from "../lib/bibliothek.svelte";
  import { artikelHolen, zufallHolen } from "../lib/schnittstelle";
  import type { Art, Buch } from "../lib/typen";
  import { lesen } from "../lib/ziele";

  interface Fund { buch: Buch; pfad: string; titel: string; einleitung: string }

  const SYMBOL: Record<Art, string> = { enzyklopaedie: "fa-book", dokumentation: "fa-code", frage_antwort: "fa-comments",
                                       webseite: "fa-globe", sonstiges: "fa-box-archive" };

  let funde = $state<Record<string, Fund | null>>({});
  let fehler = $state("");

  const artikelGesamt = $derived(bibliothek.buecher.reduce((s, b) => s + b.artikel, 0));
  const mitLesedesign = $derived(bibliothek.buecher.filter((b) => b.faehigkeiten.lesedesign));

  async function zufallsfund(b: Buch) {
    try {
      const z = await zufallHolen(b.kennung);
      const a = await artikelHolen(b.kennung, z.pfad);
      const fund = { buch: b, pfad: a.pfad, titel: a.titel, einleitung: a.einleitung };
      funde = { ...funde, [b.kennung]: fund };     // erst nach dem Abwarten zusammensetzen
    } catch (f) {
      fehler = seitenFehler(f);
    }
  }

  onMount(async () => {
    await bibliothekLaden();
    for (const b of mitLesedesign) void zufallsfund(b);
  });
</script>

<div class="rollfeld" style="padding: 0">
  <div class="start-innen">
    <div class="suchmitte">
      <h1>Was möchtest du nachschlagen?</h1>
      <Suchfeld gross />
      {#if bibliothek.buecher.length}
        <div class="unter">Index über <span class="zahl">{zahl(artikelGesamt)}</span> Artikel in {bibliothek.buecher.length}
          {bibliothek.buecher.length === 1 ? "Buch" : "Büchern"}</div>
      {/if}
    </div>

    {#if mitLesedesign.length}
      <section>
        <div class="abschnitt-kopf"><h2><i class="fa-solid fa-shuffle"></i>Stöbern</h2></div>
        <div class="stoebern">
          {#each mitLesedesign as b (b.kennung)}
            {@const f = funde[b.kennung]}
            <div class="kachel-zufall">
              <span class="etikett"><i class="fa-solid fa-dice"></i>Zufallsfund</span>
              {#if f}
                <span class="t">{f.titel}</span>
                <span class="buchname">{b.titel}</span>
                <p>{f.einleitung}</p>
                <div class="knopfreihe">
                  <button class="knopf" onclick={() => lesen(b.kennung, f.pfad)}><i class="fa-solid fa-book-open"></i>Lesen</button>
                  <button class="knopf still" onclick={() => zufallsfund(b)}><i class="fa-solid fa-rotate"></i>Neuer Zufall</button>
                </div>
              {:else}
                <span class="buchname">{b.titel}: sucht ...</span>
              {/if}
            </div>
          {/each}
        </div>
      </section>
    {/if}

    <section>
      <div class="abschnitt-kopf"><h2><i class="fa-solid fa-swatchbook"></i>Bibliothek</h2>
        <span class="neben">{bibliothek.buecher.length} {bibliothek.buecher.length === 1 ? "Buch" : "Bücher"}</span></div>
      {#if bibliothek.meldung}<div class="fehlertext">{bibliothek.meldung}</div>{/if}
      {#if bibliothek.geladen && !bibliothek.buecher.length && !bibliothek.meldung}
        <p class="leer-hinweis">Im Ordner der Bücher liegt noch keine ZIM-Datei. Den Ordner nennen die Einstellungen unter Bibliothek.</p>
      {/if}
      <div class="buecher">
        {#each bibliothek.buecher as b (b.kennung)}
          <button class="buchkarte" title="Startseite des Buchs öffnen" onclick={() => lesen(b.kennung, b.startseite)}>
            <span class="sym"><i class="fa-solid {SYMBOL[b.art]}"></i></span>
            <span class="t">{b.titel}</span>
            <span class="u"><span class="zahl">{zahl(b.artikel)}</span> Artikel · Stand {datum(b.stand)}</span>
            <span class="faehig">
              {#if b.faehigkeiten.volltext}<span class="faehigkeit an"><i class="fa-solid fa-check"></i>Index</span>{/if}
              {#if b.faehigkeiten.lesedesign}<span class="faehigkeit an"><i class="fa-solid fa-book-open-reader"></i>Lesedesign</span>
              {:else}<span class="faehigkeit"><i class="fa-solid fa-file-code"></i>Originalansicht</span>{/if}
              <span class="faehigkeit"><i class="fa-solid fa-language"></i>{sprache(b.sprache)}</span>
            </span>
          </button>
        {/each}
      </div>
      {#each bibliothek.fehler as f}<div class="fehlertext">{f}</div>{/each}
    </section>
    {#if fehler}<div class="fehlertext">{fehler}</div>{/if}
  </div>
</div>
