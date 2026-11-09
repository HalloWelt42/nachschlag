"""Originalansicht mit den Skripten der Bücher (WIKI-85).

Manche Bücher sind ganze Webseiten mit eigenen Skripten (etwa The Last Codex: Atlas, Graph, bewegliche Modelle, Suche).
Ihre Seiten laufen hier unverändert, aber nie mit der Herkunft der App:

- **eigene Herkunft:** die Originalseiten kommen über einen eigenen Port desselben Backends (`Originalherkunft.port`, im
  Betrieb ein zweiter Port des Vorschaltdienstes). Die Anmeldung der App liegt im Speicher ihrer Herkunft, ihre Cookies
  gelten nur unter /api/v1/inhalt: beides erreicht ein Buch von dort nicht.
- **Weiche:** auf dem Port der Originalansicht gibt es nur die Originalseiten, auf jedem anderen Port nie
  (`Herkunftsweiche`). So läuft kein Skript eines Buchs mit der Herkunft der App.
- **Schein statt Cookie:** jede Adresse trägt einen signierten, befristeten Schein für genau ein Buch im Pfad; relative
  Verweise der Seite behalten ihn. Ohne gültigen Schein gibt es nichts.
- **Inhaltsregeln:** die Seite lädt nur von ihrer eigenen Herkunft (keine Verbindungen nach außen) und lässt sich nur von
  Seiten desselben Rechners einbetten.
- **Brücke:** ein kleines Skript in jeder Seite, das ihr Aussehen nicht ändert: es meldet der App, welche Seite offen ist,
  reicht Verweise im Buch an die App weiter, öffnet Verweise nach außen in einem neuen Tab und nimmt die Lesegröße an.
"""

from .herkunft import GUELTIG_TAGE, PRAEFIX, Originalherkunft
from .weiche import Herkunftsweiche

__all__ = ["GUELTIG_TAGE", "PRAEFIX", "Herkunftsweiche", "Originalherkunft"]
