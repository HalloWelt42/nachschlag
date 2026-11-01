# Suche: Entwurf und Entscheidungen (WIKI-17)

Abgestimmt mit dem Nutzer am 01.11.2026. Ausgangslage: Alle Bücher bringen einen Volltextindex in der Datei mit; die
Suche scheitert vor allem am fehlenden Kontext, an der Rangfolge (Namen aus dem Code wie `array_map`) und an
fehlenden Feldern (Schlagwörter, Stimmen, Autoren, Rubriken).

## Entscheidungen

1. **Kontext:** In einem Buch (Artikel oder Übersicht) stehen Treffer aus diesem Buch zuerst, darunter sichtbar
   abgesetzt die anderen Bücher; ein Tipp schränkt ganz auf das Buch ein. Auf Start und Bibliothek sucht sie in allen.
2. **Übersichten** (Rubriken, Fragenliste, Themen, Merkzettel): Das Feld filtert beim Tippen sofort die sichtbare
   Liste, darunter ein Eintrag "Im ganzen Buch suchen".
3. **Eigener Index für alle Bücher, gestaffelt:** kleine Bücher zuerst, große (Stack Overflow, Wikipedia) als langer
   Auftrag. Bis ein Index steht, sucht das Buch über den Index der Datei.
4. **Wo gerechnet wird:** auf dem Mac (der Pi liefert nur Daten). Der Index-Dienst liest das Buch übers Heimnetz
   (Freigabe des Bücherordners, nur lesend), baut den Index und liefert die Indexdatei an Nachschlag auf dem Pi. Keine
   Kopie der Bücher auf dem Mac. Platz auf dem Pi: 1,3 TB frei (Stand 01.11.2026).
5. **Übersetzte Suche:** automatisch, wenn englische Bücher dabei sind. Die Leitstelle übersetzt lokal; Fachbegriffe,
   Code und Bezeichner bleiben. Die englischen Treffer kommen nach, sobald die Übersetzung da ist. Die Übersetzung
   steht sichtbar über den Treffern und lässt sich ändern; einmal übersetzte Fragen werden gemerkt.
6. **Treffer nach Buch gruppiert:** je Buch ein Abschnitt mit Flagge, Stand und den besten Treffern (etwa 5),
   "alle aus diesem Buch" klappt auf. Trefferkarte je Buchart (Handbuch: Name und Rubrik; Frage und Antwort: Stimmen,
   Antworten, Haken). Blöcke erscheinen, sobald ihr Buch geantwortet hat.
7. **Rückmeldung während der Suche:** je Buch ein Stand (sucht, fertig mit n Treffern, keine Antwort), dazu der Stand
   von Übersetzung und Bedeutungssuche.
8. **Spracheingabe:** Mikrofon am Suchfeld, verschriftet über die Leitstelle. Tippen startet, Tippen oder Stille
   beendet; der Text steht im Feld, die Suche läuft sofort los und er bleibt änderbar. Derselbe Baustein auch für
   Notizen.
9. **Suchkorrektur:** normal "Meintest du: ..." zum Antippen; bei null Treffern sucht Nachschlag gleich mit der
   Korrektur und sagt das deutlich. Zuerst über die Titel der Bücher, das lokale Modell nur, wenn die nichts hergeben.
10. **Register:** eigener Bereich mit Reitern Schlagwörter und Autoren (später Rubriken), Wahl "alle Bücher" oder ein
    Buch. Schlagwörter und Autorennamen in Artikeln und Treffern führen dorthin. Je Autor eine Seite mit allen
    Beiträgen, Stimmen und Zeitraum.
11. **Metadaten je Inhaltsart** im eigenen Index zum Filtern und Sortieren: Frage und Antwort (Stimmen, Antworten,
    akzeptiert, Datum, Schlagwörter, Autoren), Dokumentation (Rubrik, Fassungen, Art), Enzyklopädie (Kategorien,
    Koordinaten, Bild vorhanden).
12. **Sichtbarkeit:** Jeder Aufbau läuft als Auftrag des Appkerns (Seite Aufträge, Fußleiste) mit Was, Fortschritt,
    bisheriger Dauer und Restzeit. Eine neue Fassung eines Buchs baut ihren Index neu; der alte gilt, bis der neue
    fertig ist.
13. **Sicherung (WIKI-32):** Gesichert wird nur selbst Erzeugtes: die Datenbank und die eigenen Indizes (sie kosten
    Rechenzeit), nicht die Bücher (ZIM, lassen sich neu laden). Die Indizes kommen beim Bau in die zentrale Sicherung
    (Werkzeuge/Sicherungen, quellen.toml), mit einem eigenen Eintrag je Buch.
14. **Vektoren als Verbesserung, nie als Bedingung:** Die Bedeutungssuche (Vektoren im Fundus) bleibt eine
    austauschbare Stufe hinter einer Schnittstelle (heute `Bedeutung` mit `angebunden()`). Jedes Buch kann eine eigene
    Sammlung bekommen (heute nur ein Buch); der eigene Index liefert dafür die Textabschnitte (Abschnitt, Text, Pfad),
    damit Vektoren später ohne neues Lesen der Bücher entstehen. Index und Register arbeiten immer ohne Vektoren; fehlt
    die Sammlung oder antwortet der Fundus nicht, sucht das Buch ohne sie und sagt das (Rückmeldung je Buch).
15. **Fehlertoleranz (Mac ist ein Laptop mit WLAN):** Der Index-Dienst hält seinen Fortschritt in der Indexdatei fest
    (Stand nach je einem Stapel Seiten) und macht nach Abbruch, Ruhezustand oder Netzwechsel dort weiter. Lesefehler
    über die Freigabe: anhalten, Freigabe neu einhängen, mit wachsendem Abstand erneut versuchen; der Auftrag zeigt
    'wartet auf Netz' statt eines Fehlers. Ein Index geht erst vollständig und mit geprüfter Prüfsumme an den Pi
    (Übertragung in Teilen, fortsetzbar) und wird dort in einem Schritt ausgetauscht; bis dahin gilt der alte oder
    der Index der Datei. Ist der Mac nicht erreichbar, steht der Auftrag auf dem Pi auf 'wartet auf den Mac' und läuft
    von selbst weiter.
16. **Freigabe:** Samba-Freigabe `buecher` auf dem Pi (/mnt/data/zim), nur lesend, ohne Passwort, nur aus dem
    Heimnetz (eingerichtet 01.11.2026, vorher gesichert als /etc/samba/smb.conf.vor-buecher-freigabe); am Mac nur
    lesend eingehängt. Gemessen: PHP Docs (7.560 Einträge, 34 MB HTML) in 0,5 s über die Freigabe gelesen.

## Reihenfolge des Baus

Jeder Schritt wird einzeln ausgerollt und ist sofort nutzbar.

1. Kontext, Filter in Übersichten, gruppierte Treffer mit Rückmeldung je Buch (ohne neuen Index)
2. Index-Dienst auf dem Mac, zuerst die Handbücher (PHP Docs, PHP Manual)
3. Frage und Antwort (vi, Stack Overflow) mit Schlagwörtern, Autoren und Register
4. Übersetzte Suche
5. Suchkorrektur
6. Spracheingabe
7. Index der Enzyklopädien

## Später

Bilder in Treffern (WIKI-19), Rückverweise (WIKI-20) und deutsche Titelfolge (WIKI-21) entstehen aus demselben
eigenen Index.
