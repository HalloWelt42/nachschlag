<script lang="ts">
  // Die Bereiche von Nachschlag in der gemeinsamen Schale; die Suche steht in der Mitte des Kopfs. Am Telefon als Reiter
  // Start, Stöbern, Merkzettel und Themen (Entwurf telefon-merkzettel.html), alles andere unter Mehr.
  import { Schale, sitzung, type Bereich } from "appkern-oberflaeche";
  import Bibliothek from "./seiten/Bibliothek.svelte";
  import Lesen from "./seiten/Lesen.svelte";
  import Medien from "./seiten/Medien.svelte";
  import Merkzettel from "./seiten/Merkzettel.svelte";
  import Notizen from "./seiten/Notizen.svelte";
  import Themen from "./seiten/Themen.svelte";
  import { themen } from "./lib/themen.svelte";
  import Verlauf from "./seiten/Verlauf.svelte";
  import Start from "./seiten/Start.svelte";
  import Stoebern from "./seiten/Stoebern.svelte";
  import Suche from "./seiten/Suche.svelte";
  import Register from "./seiten/Register.svelte";
  import Kategorien from "./seiten/Kategorien.svelte";
  import Suchfeld from "./teile/Suchfeld.svelte";
  import { meins } from "./lib/meins.svelte";
  import { ladeAnteil, ladeZahl, lader, laderLaden } from "./lib/buecherlader.svelte";

  // Zahl des Neuen am Menüpunkt Bibliothek: geholt, sobald jemand angemeldet ist
  $effect(() => {
    if (sitzung.angemeldet) void laderLaden(true);
  });

  const bereiche: Bereich[] = [
    { schluessel: "start", titel: "Start", symbol: "fa-house", seite: Start, reiter: true, hinweis: "Suchen, stöbern, die Quellen der Bibliothek" },
    { schluessel: "lesen", titel: "Artikel", symbol: "fa-book-open", seite: Lesen, reiter: false, hinweis: "Der zuletzt geöffnete Artikel" },
    { schluessel: "stoebern", titel: "Stöbern", symbol: "fa-shuffle", seite: Stoebern, reiter: false,
      hinweis: "Zufallsfunde, Entdeckungspfad und Blättern wie im Buch" },
    { schluessel: "medien", titel: "Medien", symbol: "fa-images", seite: Medien, reiter: false,
      hinweis: "Bilder zu einem Begriff aus den Artikeln der Quellen, groß ansehen" },
    { schluessel: "suche", titel: "Suche", symbol: "fa-magnifying-glass", seite: Suche, reiter: true, hinweis: "Alle Treffer zu einer Frage" },
    { schluessel: "kategorien", titel: "Kategorien", kurz: "Kategorie", symbol: "fa-shapes", seite: Kategorien, reiter: true,
      hinweis: "Die Bücher nach Art: Nachschlagewerke, Dokumentation, Frage und Antwort, Anleitungen" },
    { schluessel: "register", titel: "Register", symbol: "fa-tags", seite: Register, reiter: false,
      hinweis: "Schlagwörter und Autoren der Frage-Antwort-Quellen" },
    { schluessel: "merkzettel", titel: "Merkzettel", symbol: "fa-bookmark", seite: Merkzettel, reiter: false,
      hinweis: "Gemerkte Seiten mit Lesestand, auf allen Geräten", zahl: () => meins.merkzettel.length },
    { schluessel: "notizen", titel: "Notizen", symbol: "fa-note-sticky", seite: Notizen, reiter: false,
      hinweis: "Notizen und Markierungen an Artikeln und Stellen, auf allen Geräten", zahl: () => meins.notizen.length },
    { schluessel: "themen", titel: "Themen", symbol: "fa-layer-group", seite: Themen, reiter: false,
      hinweis: "Eigene Sammlungen von Artikeln aus allen Quellen, in Bereichen", zahl: () => themen.liste.length },
    { schluessel: "bibliothek", titel: "Bibliothek", kurz: "Katalog", symbol: "fa-swatchbook", seite: Bibliothek, reiter: true,
      hinweis: "Meine Bücher, der Katalog mit allem Neuen, Fassungen und Laden",
      // beim Laden: wie viele Bücher laden oder warten, dazu der Balken des laufenden; sonst das Neue im Verzeichnis
      zahl: () => ladeZahl() || (lader.stand?.neu_ungesehen ?? 0), fortschritt: ladeAnteil },
    { schluessel: "verlauf", titel: "Verlauf", symbol: "fa-clock-rotate-left", seite: Verlauf, reiter: false, hinweis: "Gelesenes und Gesuchtes, auf allen Geräten" },
  ];
</script>

{#snippet kopfMitte()}<Suchfeld taste />{/snippet}

<!-- am Telefon unten: Start, Suche, Kategorie, Katalog, Mehr; Aufträge unter Mehr (WIKI-74) -->
<Schale {bereiche} fassung={__APP_FASSUNG__} {kopfMitte} auftraegeReiter={false} />
