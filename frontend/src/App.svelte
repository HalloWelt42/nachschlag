<script lang="ts">
  // Die Bereiche von Nachschlag in der gemeinsamen Schale; die Suche steht in der Mitte des Kopfs. Am Telefon als Reiter
  // nur Start, Merkzettel und Notizen (Entwurf telefon-merkzettel.html), alles andere unter Mehr.
  import { Schale, type Bereich } from "appkern-oberflaeche";
  import Lesen from "./seiten/Lesen.svelte";
  import Merkzettel from "./seiten/Merkzettel.svelte";
  import Notizen from "./seiten/Notizen.svelte";
  import Verlauf from "./seiten/Verlauf.svelte";
  import Start from "./seiten/Start.svelte";
  import Suche from "./seiten/Suche.svelte";
  import Suchfeld from "./teile/Suchfeld.svelte";
  import { meins } from "./lib/meins.svelte";

  const bereiche: Bereich[] = [
    { schluessel: "start", titel: "Start", symbol: "fa-house", seite: Start, reiter: true, hinweis: "Suchen, stöbern, die Bücher der Bibliothek" },
    { schluessel: "lesen", titel: "Artikel", symbol: "fa-book-open", seite: Lesen, reiter: false, hinweis: "Der zuletzt geöffnete Artikel" },
    { schluessel: "suche", titel: "Suche", symbol: "fa-magnifying-glass", seite: Suche, reiter: false, hinweis: "Alle Treffer zu einer Frage" },
    { schluessel: "merkzettel", titel: "Merkzettel", symbol: "fa-bookmark", seite: Merkzettel, reiter: true,
      hinweis: "Gemerkte Seiten mit Lesestand, auf allen Geräten", zahl: () => meins.merkzettel.length },
    { schluessel: "notizen", titel: "Notizen", symbol: "fa-note-sticky", seite: Notizen, reiter: true,
      hinweis: "Notizen und Markierungen an Artikeln und Stellen, auf allen Geräten", zahl: () => meins.notizen.length },
    { schluessel: "verlauf", titel: "Verlauf", symbol: "fa-clock-rotate-left", seite: Verlauf, reiter: false, hinweis: "Gelesenes und Gesuchtes, auf allen Geräten" },
  ];
</script>

{#snippet kopfMitte()}<Suchfeld taste />{/snippet}

<Schale {bereiche} fassung={__APP_FASSUNG__} {kopfMitte} />
