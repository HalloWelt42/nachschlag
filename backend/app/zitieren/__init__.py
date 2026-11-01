"""Zitieren (WIKI-31): Angaben einer Seite und die Zitierformen an einer Stelle."""

from .angaben import aus_artikel, zitierangaben
from .formen import FORMEN, Form, Zitate, Zitierangaben, schluessel, zitate, zitieren

__all__ = ["FORMEN", "Form", "Zitate", "Zitierangaben", "aus_artikel", "schluessel", "zitate", "zitierangaben", "zitieren"]
