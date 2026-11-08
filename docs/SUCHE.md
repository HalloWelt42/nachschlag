# Suche: Entwurf und Entscheidungen (WIKI-17)

Stand der Entscheidungen 01.11.2026. Ausgangslage: Alle Bücher bringen einen Volltextindex in der Datei mit; die
Suche scheitert vor allem am fehlenden Kontext, an der Rangfolge (Namen aus dem Code wie `array_map`) und an
fehlenden Feldern (Schlagwörter, Stimmen, Autoren, Rubriken).

## Entscheidungen

1. **Kontext:** In einem Buch (Artikel oder Übersicht) stehen Treffer aus diesem Buch zuerst, darunter sichtbar
   abgesetzt die anderen Bücher; ein Tipp schränkt ganz auf das Buch ein. Auf Start und Bibliothek sucht sie in allen.
2. **Übersichten** (Rubriken, Fragenliste, Themen, Merkzettel): Das Feld filtert beim Tippen sofort die sichtbare
   Liste, darunter ein Eintrag "Im ganzen Buch suchen".
3. **Eigener Index für alle Bücher, gestaffelt:** kleine Bücher zuerst, große (Stack Overflow, Wikipedia) als langer
   Auftrag. Bis ein Index steht, sucht das Buch über den Index der Datei.
   **Titelfolge (WIKI-21):** der eigene Index trägt je Seite einen Sortierschlüssel nach deutscher Ordnung (DIN 5007:
   Umlaute wie ihr Grundlaut, ß wie ss, Groß und Klein gleich); Blättern wie im Buch folgt dann ihr statt der Bytefolge
   der Pfade. Sie ist eine Ergänzung: ein fertiger Index ohne sie gilt weiter, Nachschlag reiht einen Auftrag ein, und
   der Index-Dienst zieht sie in seiner Kopie nach (liest nur den Index, nicht das Buch) und liefert die Datei neu.
4. **Wo gerechnet wird:** auf einem eigenen Rechner, dem Index-Dienst (der Server mit Nachschlag liefert nur Daten).
   Der Index-Dienst liest das Buch über das eigene Netz (Freigabe des Bücherordners, nur lesend), baut den Index und
   liefert die Indexdatei an Nachschlag. Keine Kopie der Bücher auf seinem Rechner.
   **Umgesetzt (Schritt 2):** Der Index-Dienst ruft nur an, bei ihm lauscht nichts im Netz. Er holt den laufenden Auftrag bei Nachschlag ab (`/api/v1/indexdienst`,
   nur mit seinem eigenen Schlüssel), meldet den Fortschritt, lädt die fertige Datei in Stücken hoch und meldet sie
   fertig; Nachschlag prüft die Prüfsumme und tauscht aus. Er läuft als eigener Prozess von Nachschlag
   (`python -m app.indexdienst`, Einstellungen aus der Umgebung, siehe `backend/app/indexdienst/__main__.py`). Welche Bücher einen eigenen Index bekommen, steht in
   den Einstellungen in Stufen nach der Reihenfolge des Baus (keine, Handbücher, dazu Frage und Antwort, alle).
5. **Übersetzte Suche:** automatisch, wenn englische Bücher dabei sind. Die Leitstelle übersetzt lokal; Fachbegriffe,
   Code und Bezeichner bleiben. Die englischen Treffer kommen nach, sobald die Übersetzung da ist. Die Übersetzung
   steht sichtbar über den Treffern und lässt sich ändern; einmal übersetzte Fragen werden gemerkt.
   **Umgesetzt (Schritt 4, WIKI-40):** Sind englische Quellen dabei, fragt die Suchseite die Leitstelle nach der
   Übersetzung (Modell einstellbar, Vorgabe Qwen 80B; jede Anfrage nennt es, die Leitstelle wählt nie selbst, LS-19)
   und fragt die englischen Quellen damit zusätzlich; deren
   Treffer stehen vorn, jede Seite einmal. Ein Band über den Treffern zeigt die Übersetzung, "Ändern" speichert die
   eigene; gemerkt wird für alle Konten. Ohne Leitstelle steht der Grund im Band, die Suche läuft ohne Übersetzung.
6. **Treffer nach Buch gruppiert:** je Buch ein Abschnitt mit Flagge, Stand und den besten Treffern (etwa 5),
   "alle aus diesem Buch" klappt auf. Trefferkarte je Buchart (Handbuch: Name und Rubrik; Frage und Antwort: Stimmen,
   Antworten, Haken). Blöcke erscheinen, sobald ihr Buch geantwortet hat.
7. **Rückmeldung während der Suche:** je Buch ein Stand (sucht, fertig mit n Treffern, keine Antwort), dazu der Stand
   von Übersetzung und Bedeutungssuche.
8. **Spracheingabe:** Mikrofon am Suchfeld, verschriftet über die Leitstelle. Tippen startet, Tippen oder Stille
   beendet; der Text steht im Feld, die Suche läuft sofort los und er bleibt änderbar. Derselbe Baustein auch für
   Notizen.
   **Umgesetzt (Schritt 6, WIKI-42):** Baustein Sprechknopf (Suchfeld und Notizen) mit der Aufnahme des Appkerns:
   Live-Mitschrift an Sprechpausen über den Hördienst der Leitstelle (Einstellung, Vorgabe klangwerk-hoeren), Ende per
   Tippen oder drei Sekunden Stille. Das Mikrofon erscheint nur, wenn die Leitstelle den Hördienst für Nachschlag
   freigibt (GET /api/v1/sprache).
9. **Suchkorrektur:** normal "Meintest du: ..." zum Antippen; bei null Treffern sucht Nachschlag gleich mit der
   Korrektur und sagt das deutlich. Zuerst über die Titel der Bücher, das lokale Modell nur, wenn die nichts hergeben.
   **Umgesetzt (Schritt 5, WIKI-41):** Vorschlag aus dem Wortschatz der eigenen Indizes: ein Wort der Frage weicht
   einem ähnlichen (Schreibabstand 1, ab 8 Zeichen 2, Vertauschen zählt 1), das häufig genug ist und mindestens 20-mal
   häufiger als es selbst; häufige Schreibfehler (subsitute, autocomand) führen so zum richtigen Wort. Ohne Treffer
   sucht die Seite gleich mit dem Vorschlag (?statt=) und bietet "Doch nach ... suchen" (?genau=1); erst dann fragt
   sie auch das Modell (dieselbe Einstellung wie die Übersetzung).
10. **Register:** eigener Bereich mit Reitern Schlagwörter und Autoren (später Rubriken), Wahl "alle Bücher" oder ein
    Buch. Schlagwörter und Autorennamen in Artikeln und Treffern führen dorthin. Je Autor eine Seite mit allen
    Beiträgen, Stimmen und Zeitraum.
    **Umgesetzt (Schritt 3, WIKI-39):** Bereich Register mit Reitern Schlagwörter und Autoren, Wahl aller
    Frage-Antwort-Bücher oder eines, Filter auf den Anfang; Seite je Schlagwort (Fragen nach Stimmen oder neueste) und
    je Autor (Beiträge, Fragen, Antworten, akzeptiert, Stimmen, Zeitraum). Autoren sind über ihre Kontonummer im Buch
    eindeutig. Gezählt wird beim Bau des Index (Tabellen register_*), die Seiten lesen nur.
11. **Metadaten je Inhaltsart** im eigenen Index zum Filtern und Sortieren: Frage und Antwort (Stimmen, Antworten,
    akzeptiert, Datum, Schlagwörter, Autoren), Dokumentation (Rubrik, Fassungen, Art), Enzyklopädie (Kategorien,
    Koordinaten, Bild vorhanden).
    **Umgesetzt für Frage und Antwort (WIKI-39):** je Frage Stimmen, Antworten, Haken, Datum, Schlagwörter und die
    Beiträge mit Autor; nur Fragen kommen in den Index (keine Listen, Konten, Schlagwortseiten). Stimmen heben eine
    Frage in der Rangfolge (logarithmisch), die Trefferkarte zeigt Stimmen, Antworten mit Haken und Schlagwörter.
    Bücher über einer einstellbaren Größe (Vorgabe 5 GB) bekommen ihren Index nicht von selbst: Stack Overflow
    (115 GB, 30 Mio. Seiten) braucht beim Index-Dienst viele Stunden und mehrere hundert GB.
    **Umgesetzt für Anleitungen (iFixit, WIKI-64):** je Anleitung Art (Anleitung, Zerlegung), Sprache (aus dem Text,
    die Seiten nennen keine verlässliche), Schwierigkeit, Zeitaufwand in Minuten, Zahl der Schritte, Bild und Werkzeuge;
    je Geräteseite Bild, Kurztext, Unterkategorien und Anleitungen mit Bauteil (der Titel in ihrer Liste). Daraus beim
    Bau der Baum (`register_einordnung`: je Anleitung jede Geräteseite darüber) und das Register der Werkzeuge je
    Sprache. Benutzer- und Infoseiten bleiben draußen. Die Startseite des Buchs ist "Anleitungen finden": ohne Filter
    die Kategorien der Quelle, mit Filtern die Treffer (Art, Sprache, vorerst Deutsch, Schwierigkeit, Zeit, Ich habe,
    Gerät mit ganzem Ast, Bauteil, Reihenfolge), alles in der Adresse. Ich habe: die eigenen Werkzeuge stehen in Meins
    (auf allen Geräten); dann zählen nur Anleitungen, für die sie reichen, die übrigen auf Wunsch mit den fehlenden.
    Geräte- und Anleitungsseiten zeigen ihre Einordnung (Startseite, Kategorien, Gerät, Bauteil) mit Sprung in die
    Suche dieses Asts.
12. **Sichtbarkeit:** Jeder Aufbau läuft als Auftrag des Appkerns (Seite Aufträge, Fußleiste) mit Was, Fortschritt,
    bisheriger Dauer und Restzeit. Eine neue Fassung eines Buchs bekommt einen eigenen Index; Seiten mit gleichem
    Rohinhalt (Abdruck) kommen aus dem Index der vorigen, aufbereitet wird nur Neues und Geändertes (WIKI-58). Der alte
    gilt, bis der neue fertig ist.
13. **Sicherung (WIKI-32):** Gesichert wird nur selbst Erzeugtes: die Datenbank und die eigenen Indizes (sie kosten
    Rechenzeit), nicht die Bücher (ZIM, lassen sich neu laden). Die Indizes gehören in die Sicherung des Betreibers,
    am besten mit einem eigenen Eintrag je Buch.
14. **Vektoren als Verbesserung, nie als Bedingung:** Die Bedeutungssuche (Vektoren im Fundus) bleibt eine
    austauschbare Stufe hinter einer Schnittstelle (heute `Bedeutung` mit `angebunden()`). Jedes Buch kann eine eigene
    Sammlung bekommen (heute nur ein Buch); der eigene Index liefert dafür die Textabschnitte (Abschnitt, Text, Pfad),
    damit Vektoren später ohne neues Lesen der Bücher entstehen. Index und Register arbeiten immer ohne Vektoren; fehlt
    die Sammlung oder antwortet der Fundus nicht, sucht das Buch ohne sie und sagt das (Rückmeldung je Buch).
15. **Fehlertoleranz (der Rechner des Index-Dienstes kann ein Laptop mit WLAN sein):** Der Index-Dienst hält seinen Fortschritt in der Indexdatei fest
    (Stand nach je einem Stapel Seiten) und macht nach Abbruch, Ruhezustand oder Netzwechsel dort weiter. Lesefehler
    über die Freigabe: anhalten, Freigabe neu einhängen, mit wachsendem Abstand erneut versuchen; der Auftrag zeigt
    'wartet auf Netz' statt eines Fehlers. Ein Index geht erst vollständig und mit geprüfter Prüfsumme an Nachschlag
    (Übertragung in Teilen, fortsetzbar) und wird dort in einem Schritt ausgetauscht; bis dahin gilt der alte oder
    der Index der Datei. Ist der Index-Dienst nicht erreichbar, steht der Auftrag in Nachschlag auf 'wartet auf den
    Index-Dienst' und läuft von selbst weiter.
16. **Freigabe:** der Ordner der Bücher als Freigabe im eigenen Netz (etwa SMB), nur lesend; der Rechner des
    Index-Dienstes hängt sie nur lesend ein. Über eine Freigabe im eigenen Netz liest der Index-Dienst ein Handbuch
    in Sekundenbruchteilen.
17. **Ablage sichtbar machen (wahlweise):** Bücherordner und Ordner der eigenen Indizes lassen sich in der Kellerwolke
    als externe Quellen einhängen, nur lesend. Den Ordner der Indizes nennt Nachschlag in seinen Einstellungen (nie
    fest im Code; im Container `/eigenindex`).

18. **Kategorien für Wikipedia (WIKI-75):** Die ZIM-Dateien der Wikipedia bringen keine Kategorien mit. Eine zweite
    Sorte von Aufträgen für den Index-Dienst baut sie je Buch aus den Datenabzügen von Wikimedia (page, linktarget,
    categorylinks, page_props und die Namen der Namensräume, zusammen gut 1 GB je Wiki). Der Index-Dienst lädt sie
    fortsetzbar nach `<NACHSCHLAG_INDEX_ZIEL>/abzuege/<wiki>/`, höchstens einmal in 30 Tagen, und bereitet sie zu
    `<wiki>.sqlite` auf (für die deutsche Wikipedia etwa 5 Minuten). Daraus
    entsteht je Buch eine Kategoriendatei mit nur den Kategorien, in denen eine Seite des Buchs steht, und allen darüber;
    versteckte Wartungskategorien fehlen. Übertragen wird sie wie ein Index in den Unterordner `kategorien` des Ordners der
    eigenen Indizes (im Container `/eigenindex/kategorien`). Ein- und ausschalten: Einstellungen, Suche,
    "Kategorien für Wikipedia". Große Kategorien zeigt die Kategorieseite seitenweise (2.000 Seiten je Schritt).
    Neue Fassungen kategorisieren sich selbst: der Begleiter sieht stündlich nach und reiht für jede
    geltende Fassung ohne Kategoriendatei einen Auftrag ein; ein Abzug älter als 30 Tage wird dabei neu geladen. Wird
    eine Fassung entfernt (gelöscht oder nach der Frist des Bücherladers), gehen ihre Kategorien mit.

## Reihenfolge des Baus

Jeder Schritt wird einzeln ausgerollt und ist sofort nutzbar.

1. Kontext, Filter in Übersichten, gruppierte Treffer mit Rückmeldung je Buch (ohne neuen Index)
2. Index-Dienst auf eigenem Rechner, zuerst die Handbücher (PHP Docs, PHP Manual)
3. Frage und Antwort (vi, Stack Overflow) mit Schlagwörtern, Autoren und Register
4. Übersetzte Suche
5. Suchkorrektur
6. Spracheingabe
7. Index der Enzyklopädien

## Später

Bilder in Treffern (WIKI-19), Rückverweise (WIKI-20) und deutsche Titelfolge (WIKI-21) entstehen aus demselben
eigenen Index.
