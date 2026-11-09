"""Originalansicht mit den Skripten der Bücher (WIKI-85).

Manche Bücher sind ganze Webseiten mit eigenen Skripten (etwa The Last Codex: Atlas, Graph, bewegliche Modelle, Suche).
Ihre Seiten laufen hier unverändert, über den Port der App, aber nie mit ihrer Herkunft:

- **anonyme Herkunft:** jede Originalseite läuft abgeschirmt ohne eigene Herkunft (Sandbox ohne allow-same-origin, im
  Rahmen und als Inhaltsregel der Seite selbst, also auch allein geöffnet). Den Speicher der App (mit der Anmeldung)
  erreicht sie so nicht, und ihre Anfragen tragen keine Cookies der App. Ein zweiter Port ist nicht nötig (er war es
  zuerst; manche Geräte erreichten ihn nicht).
- **Schein statt Cookie:** jede Adresse trägt einen signierten, befristeten Schein für genau ein Buch im Pfad; relative
  Verweise der Seite behalten ihn. Ohne gültigen Schein gibt es nichts. Weil die Herkunft anonym ist, dürfen Skripte
  der Seite ihre Dateien nur mit Freigabe (CORS) holen; die Originalseiten geben sie, der Schein ist der Zugang.
- **Inhaltsregeln:** die Seite lädt und verbindet sich nur mit den Wegen der Originalseiten (nicht mit der Schnittstelle
  der App, nichts nach außen) und lässt sich nur von der App einbetten.
- **Brücke:** ein kleines Skript in jeder Seite, das ihr Aussehen nicht ändert: es meldet der App, welche Seite offen ist,
  reicht Verweise im Buch an die App weiter, öffnet Verweise nach außen in einem neuen Tab und nimmt die Lesegröße an.
"""

from .herkunft import GUELTIG_TAGE, PRAEFIX, Originalscheine

__all__ = ["GUELTIG_TAGE", "PRAEFIX", "Originalscheine"]
