# Bildholer (WIKI-80)

Die Bücher der Wikipedia bringen nur Vorschaubilder mit (meist 200 bis 350 Pixel breit). Der Bildholer holt dazu das
große Bild aus der Bildquelle des Wikis (Wikimedia Commons oder das Wiki selbst), mit Urheber und Lizenz.

## Aufbau

- **Eigenes Programm, eigener Container:** `backend/bildholer/`, gestartet mit `python -m bildholer` aus demselben
  Abbild wie Nachschlag (`compose.pi.yml`, Dienst `bildholer`, Container `nachschlag-bildholer`). Kein Port nach außen;
  Nachschlag spricht mit ihm im eigenen Netz der Container (`http://bildholer:8000`).
- **Ablage:** `./bilder` auf dem Pi, im Bildholer beschreibbar, in Nachschlag nur lesend (`/bilder`). Feste Pfade
  `<Wiki>/<zwei Zeichen>/<Dateiname>` und daneben `<Dateiname>.json` mit Urheber, Lizenz, Breite und Herkunft
  (`bildholer/ablage.py`). Nachschlag fragt den Bildholer nie, ob ein Bild da ist; es sieht nach.
- **Warteschlange, Zähler, zuletzt geschickte Regeln:** `./bildholer/bildholer.sqlite`.

## Ablauf

1. Nachschlag kennzeichnet beim Aufbereiten jedes Bild, dessen Original deutlich größer ist (mindestens 1,5-fach, ab
   80 Pixel gezeigter Breite), mit `data-gross`.
2. Wird ein Artikel geöffnet, merkt Nachschlag diese Bilder mit Vorrang 0 vor (sie kommen als Nächstes). Stündlich kommen
   gelesene, gemerkte und in Themen gesammelte Artikel mit Vorrang 1 dazu (je Artikel einmal je Lauf).
3. Der Bildholer fragt je 50 Dateien die Schnittstelle des Wikis (Größe, Urheber, Lizenz, Vorschaubild in der
   eingestellten Breite 960, 1.280 oder 1.920 Pixel; schmalere Originale kommen unverändert) und lädt dann ein Bild nach
   dem anderen mit Pause.
4. Die große Bildansicht zeigt das große Bild mit Urheber und Lizenz, sobald es da ist; sonst das Vorschaubild.

## Regeln

Einstellungen, Reiter Bilder (Nachschlag schickt sie dem Bildholer bei jeder Änderung, spätestens nach einer Minute):
an oder aus, zuerst beim Öffnen, Abstand, nur nachts (Fenster aus Über Nacht), größte Breite, Platz höchstens, Verhalten
bei Drosselung (warten und langsamer oder anhalten), Absender. Stand, Anhalten und Fortsetzen: Reiter Bildholer.

Die Bildquelle verlangt einen Absender mit Kontakt (gemessen 08.11.2026: ohne Kontakt 403 mit Hinweis auf ihre Regeln
für Roboter). Vorgabe ist die Seite des Projekts. Lehnt sie ab, hält der Bildholer an und nennt den Grund; neue Regeln
setzen ihn fort.

## Später

Stufen für alle Bilder eines Buchs (Steckbriefbilder, übrige) brauchen eine Liste aller Bilder je Artikel; die entsteht
am besten auf dem Mac beim Bau des eigenen Index (der Pi liefert nur Daten).
