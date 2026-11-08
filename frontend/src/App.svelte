<script lang="ts">
  // Die Bereiche von Nachschlag in der gemeinsamen Schale; die Suche steht in der Mitte des Kopfs. Am Telefon als Reiter
  // Start, Stöbern, Merkzettel und Themen (Entwurf telefon-merkzettel.html), alles andere unter Mehr.
  import { Schale, Schnittstelle, sitzung, type Bereich, type EinstellungsReiter } from "appkern-oberflaeche";
  import Bildholer from "./seiten/Bildholer.svelte";
  import Bibliothek from "./seiten/Bibliothek.svelte";
  import Lesen from "./seiten/Lesen.svelte";
  import Medien from "./seiten/Medien.svelte";
  import Merkzettel from "./seiten/Merkzettel.svelte";
  import Notizen from "./seiten/Notizen.svelte";
  import Themen from "./seiten/Themen.svelte";
  import Buecher from "./seiten/Buecher.svelte";
  import { buecher, regalLaden } from "./lib/buecher.svelte";
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
  // Zahl der eigenen Bücher am Menüpunkt (WIKI-45)
  $effect(() => {
    if (sitzung.angemeldet) regalLaden().catch(() => {});
  });

  // eigener Reiter in den Einstellungen: der Stand des Bildholers (WIKI-80); seine Regeln stehen im erzeugten Reiter Bilder
  const einstellungen: EinstellungsReiter[] = [{ schluessel: "bildholer", titel: "Bildholer", seite: Bildholer }];
  // gegliedert wie in den Entwürfen (WIKI-22): Lesen, Meins, dann App mit der Schnittstelle vor den Teilen des Appkerns
  const bereiche: Bereich[] = [
    { gruppe: "Lesen", schluessel: "start", titel: "Start", symbol: "fa-house", seite: Start, reiter: true, hinweis: "Suchen, stöbern, die Quellen der Bibliothek" },
    { gruppe: "Lesen", schluessel: "lesen", titel: "Artikel", symbol: "fa-book-open", seite: Lesen, reiter: false, hinweis: "Der zuletzt geöffnete Artikel" },
    { gruppe: "Lesen", schluessel: "suche", titel: "Suche", symbol: "fa-magnifying-glass", seite: Suche, reiter: true, hinweis: "Alle Treffer zu einer Frage" },
    { gruppe: "Lesen", schluessel: "stoebern", titel: "Stöbern", symbol: "fa-shuffle", seite: Stoebern, reiter: false,
      hinweis: "Zufallsfunde, Entdeckungspfad und Blättern wie im Buch" },
    { gruppe: "Lesen", schluessel: "kategorien", titel: "Kategorien", kurz: "Kategorie", symbol: "fa-shapes", seite: Kategorien, reiter: true,
      hinweis: "Die Bücher nach Art: Nachschlagewerke, Dokumentation, Frage und Antwort, Anleitungen" },
    { gruppe: "Lesen", schluessel: "register", titel: "Register", symbol: "fa-tags", seite: Register, reiter: false,
      hinweis: "Schlagwörter und Autoren der Frage-Antwort-Quellen" },
    { gruppe: "Lesen", schluessel: "medien", titel: "Medien", symbol: "fa-images", seite: Medien, reiter: false,
      hinweis: "Bilder zu einem Begriff aus den Artikeln der Quellen, groß ansehen" },
    { gruppe: "Lesen", schluessel: "bibliothek", titel: "Bibliothek", kurz: "Katalog", symbol: "fa-swatchbook", seite: Bibliothek, reiter: true,
      hinweis: "Meine Bücher, der Katalog mit allem Neuen, Fassungen und Laden",
      // beim Laden: wie viele Bücher laden oder warten, dazu der Balken des laufenden; sonst das Neue im Verzeichnis
      zahl: () => ladeZahl() || (lader.stand?.neu_ungesehen ?? 0), fortschritt: ladeAnteil },
    { gruppe: "Meins", schluessel: "merkzettel", titel: "Merkzettel", symbol: "fa-bookmark", seite: Merkzettel, reiter: false,
      hinweis: "Gemerkte Seiten mit Lesestand, auf allen Geräten", zahl: () => meins.merkzettel.length },
    { gruppe: "Meins", schluessel: "notizen", titel: "Notizen", symbol: "fa-note-sticky", seite: Notizen, reiter: false,
      hinweis: "Notizen und Markierungen an Artikeln und Stellen, auf allen Geräten", zahl: () => meins.notizen.length },
    { gruppe: "Meins", schluessel: "themen", titel: "Themen", symbol: "fa-layer-group", seite: Themen, reiter: false,
      hinweis: "Eigene Sammlungen von Artikeln aus allen Quellen, in Bereichen", zahl: () => themen.liste.length },
    { gruppe: "Meins", schluessel: "buecher", titel: "Eigene Bücher", kurz: "Bücher", symbol: "fa-book-bookmark", seite: Buecher, reiter: false,
      hinweis: "Themen als Buch (EPUB und PDF): was gerade entsteht und das Regal der fertigen", zahl: () => buecher.regal?.fertig.length ?? 0 },
    { gruppe: "Meins", schluessel: "verlauf", titel: "Verlauf", symbol: "fa-clock-rotate-left", seite: Verlauf, reiter: false, hinweis: "Gelesenes und Gesuchtes, auf allen Geräten" },
    { gruppe: "App", schluessel: "schnittstelle", titel: "Schnittstelle", symbol: "fa-plug", seite: Schnittstelle, reiter: false,
      hinweis: "Alle Wege der Schnittstelle zum Nachlesen und Ausprobieren (für eigene Werkzeuge und andere Apps)" },
  ];
</script>

{#snippet kopfMitte()}<Suchfeld taste />{/snippet}

<!-- am Telefon unten: Start, Suche, Kategorie, Katalog, Mehr; Aufträge unter Mehr (WIKI-74) -->
<Schale {bereiche} {einstellungen} fassung={__APP_FASSUNG__} {kopfMitte} auftraegeReiter={false} />
