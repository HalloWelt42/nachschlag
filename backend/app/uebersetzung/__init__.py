"""Übersetzen: Fragen für englische Quellen (WIKI-40) und Artikel aus anderen Sprachen ins Deutsche (WIKI-8)."""

from .artikel import Artikeluebersetzer, Artikelstand, ArtikelUebersetzung
from .dienst import Uebersetzer, Uebersetzung, UebersetzungFehlt
from .stelle import Stellenuebersetzer

__all__ = ["ArtikelUebersetzung", "Artikelstand", "Artikeluebersetzer", "Stellenuebersetzer", "Uebersetzer", "Uebersetzung",
           "UebersetzungFehlt"]
