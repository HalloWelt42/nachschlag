"""Suche: Index der Bücher immer, Bedeutungssuche als Anbindung, gemischt nach Rang, mit Rückfall auf den Index."""

from .dienst import Suche
from .bedeutung import Bedeutung, BedeutungFehlt, Fundstelle

__all__ = ["Suche", "Bedeutung", "BedeutungFehlt", "Fundstelle"]
