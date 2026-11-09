<script lang="ts">
  // Ein Buch als Kachel (Startseite, Kategorien): Symbol der Art, Titel, Artikel und Stand, Sprache, ob es einen Index
  // und eine eigene Ansicht hat; ein Tipp öffnet seine Startseite. Eine Stelle für beide Seiten.
  import { datum, zahl } from "../lib/bibliothek.svelte";
  import { ART_SYMBOL } from "../lib/arten";
  import type { Buch } from "../lib/typen";
  import { lesen } from "../lib/ziele";
  import Kachel from "./Kachel.svelte";
  import Sprachmarke from "./Sprachmarke.svelte";

  // `titel`: ein anderer Name, etwa ein Thema im Bündel ohne den Namen der Ebene davor (WIKI-83)
  let { buch: b, titel = "" }: { buch: Buch; titel?: string } = $props();
</script>

<Kachel art="quer" symbol={ART_SYMBOL[b.art]} titel={titel || b.titel} untertitel={`${zahl(b.artikel)} Artikel · Stand ${datum(b.stand)}`}
        hinweis="Startseite der Quelle öffnen" ziel={() => lesen(b.kennung, b.startseite)}>
  {#snippet ecke()}<Sprachmarke kuerzel={b.sprache} />{/snippet}
  {#snippet fuss()}
    <span class="faehig">
      {#if b.faehigkeiten.volltext}<span class="faehigkeit an"><i class="fa-solid fa-check"></i>Index</span>{/if}
      {#if b.faehigkeiten.lesedesign}<span class="faehigkeit an"><i class="fa-solid fa-book-open-reader"></i>Lesedesign</span>
      {:else}<span class="faehigkeit fehlt" title="Für diese Art von Buch ({b.erzeuger || 'Erzeuger unbekannt'}) gibt es noch keine eigene Ansicht; es öffnet in der Originalansicht">
        <i class="fa-solid fa-person-digging"></i>Ansicht fehlt</span>{/if}
    </span>
  {/snippet}
</Kachel>
