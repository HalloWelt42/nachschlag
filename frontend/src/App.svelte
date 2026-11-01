<script lang="ts">
  // Die Bereiche von Nachschlag in der gemeinsamen Schale; die Suche steht in der Mitte des Kopfs.
  import { Schale, type Bereich } from "appkern-oberflaeche";
  import Lesen from "./seiten/Lesen.svelte";
  import Start from "./seiten/Start.svelte";
  import Suche from "./seiten/Suche.svelte";
  import Suchfeld from "./teile/Suchfeld.svelte";

  const bereiche: Bereich[] = [
    { schluessel: "start", titel: "Start", symbol: "fa-house", seite: Start, reiter: true, hinweis: "Suchen, stöbern, die Bücher der Bibliothek" },
    { schluessel: "lesen", titel: "Artikel", symbol: "fa-book-open", seite: Lesen, reiter: true, hinweis: "Der zuletzt geöffnete Artikel" },
    { schluessel: "suche", titel: "Suche", symbol: "fa-magnifying-glass", seite: Suche, reiter: true, hinweis: "Alle Treffer zu einer Frage" },
  ];
</script>

{#snippet kopfMitte()}<Suchfeld taste />{/snippet}

<Schale {bereiche} fassung={__APP_FASSUNG__} {kopfMitte} />
