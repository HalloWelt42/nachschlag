"""Große Bilder (WIKI-80): Nachschlag liest die Ablage des Bildholers (eigenes Programm, eigener Container) und spricht
mit ihm über seine Schnittstelle: Regeln aus den Einstellungen schicken, Bilder vormerken (geöffnete Artikel zuerst,
dann Gelesenes, Gemerktes und Themen), Stand zeigen, anhalten. Ohne großes Bild bleibt es beim Vorschaubild."""

from .dienst import Grossbilder, grosse_bilder, wiki_name

__all__ = ["Grossbilder", "grosse_bilder", "wiki_name"]
