"""Übersetzen: Fragen für englische Quellen (WIKI-40) und Artikel aus anderen Sprachen ins Deutsche (WIKI-8)."""

from .artikel import Artikeluebersetzer, Artikelstand, ArtikelUebersetzung
from .dienst import Uebersetzer, Uebersetzung, UebersetzungFehlt

__all__ = ["ArtikelUebersetzung", "Artikelstand", "Artikeluebersetzer", "Uebersetzer", "Uebersetzung", "UebersetzungFehlt"]
