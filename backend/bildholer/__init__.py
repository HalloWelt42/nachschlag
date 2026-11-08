"""Bildholer (WIKI-80): eigenes Programm im eigenen Container auf dem Pi. Holt zu den Vorschaubildern der Bücher aus
Wikis von Wikimedia das große Bild aus der Bildquelle (Wikimedia Commons oder das Wiki selbst), mit Urheber und Lizenz,
eins nach dem anderen im eingestellten Abstand, und legt es in seine Ablage. Nachschlag liest nur diese Ablage (feste
Pfade, ablage.py) und spricht mit dem Bildholer über eine kleine Schnittstelle im eigenen Netz der Container (api.py):
Regeln setzen, Bilder vormerken, Stand lesen, anhalten. Der Bildholer kennt keine Bücher; er bekommt Namen von Bildern.

Aufbau: modelle.py (Verträge), ablage.py (Dateien), quelle.py (Bildquelle), schlange.py (Warteschlange und Zähler in
SQLite), arbeiter.py (die Schleife), api.py (Schnittstelle), __main__.py (Start)."""
