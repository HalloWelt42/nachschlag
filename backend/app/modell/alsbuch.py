"""Als Buch (WIKI-45): ein Thema wird ein Buch (EPUB und PDF), in der Form, die eine Vorlage bestimmt. Die Modelle an den
Grenzen: Vorlage (Aufbau aus Teilen, Anweisung an die KI, Gestaltung), Bestellung (was ins Buch kommt und wie), Schätzung
der Dauer, Probekapitel mit Prüfung, der Inhalt eines gebauten Buchs und das Regal der eigenen Bücher."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, computed_field, model_validator

# ----- Vorlage ----------------------------------------------------------------------------------------------------------

#: Teile, aus denen eine Vorlage ein Buch baut (Katalog mit Titel und Herkunft in alsbuch/teile.py)
Teilart = Literal["titelseite", "inhalt", "kapitel", "abc", "kapiteleinleitung", "blick", "umgeformt", "originaltext",
                  "kasten", "notizen", "fragen", "glossar", "literatur"]
#: Woher ein Teil kommt: aus dem Thema, von selbst gesetzt, von der KI, aus Meins, aus den Büchern
Herkunft = Literal["thema", "selbst", "ki", "meins", "buch"]
#: Wo ein Teil steht: im Buch vor oder nach den Kapiteln, im Kapitel, je Artikel; "gliederung" ist der Platz der Kapitel
Ebene = Literal["buch", "gliederung", "kapitel", "artikel"]
Ton = Literal["sachlich", "erzaehlend", "locker"]
FuerWen = Literal["erwachsene", "jugendliche", "kinder"]
Laenge = Literal["original", "haelfte", "wichtigste"]
Schrift = Literal["serifen", "ohne"]
Farbe = Literal["petrol", "violett", "honig", "koralle", "stahl"]
Bilder = Literal["im_text", "eins_gross", "ohne"]
Gliederung = Literal["kapitel", "abc"]

#: Teile, die nur einmal in einer Vorlage stehen dürfen (der eigene Kasten darf mehrfach)
EINMALIG = {"titelseite", "inhalt", "kapiteleinleitung", "blick", "umgeformt", "originaltext", "notizen", "fragen",
            "glossar", "literatur"}
#: höchstens so viele eigene Kästen je Vorlage
KAESTEN_HOECHSTENS = 4


class Teil(BaseModel):
    """Ein Teil im Aufbau einer Vorlage."""
    art: Teilart = Field(description="Welcher Teil (Katalog unter GET /api/v1/buchvorlagen/teile)")
    titel: str = Field("", max_length=80, description="Nur beim eigenen Kasten: seine Überschrift (etwa So beobachtest du es)")
    anweisung: str = Field("", max_length=1000, description="Nur beim eigenen Kasten: was die KI hineinschreibt, in eigenen Worten")


class Teilangabe(BaseModel):
    """Ein Eintrag im Katalog der Teile: wie er heißt, woher er kommt, wo er stehen darf."""
    art: Teilart = Field(description="Kennung des Teils")
    titel: str = Field(description="Beschriftung im Aufbau")
    herkunft: Herkunft = Field(description="thema, selbst, ki, meins oder buch")
    ebene: Ebene = Field(description="buch (vor oder nach den Kapiteln), gliederung (der Platz der Kapitel), kapitel oder artikel")
    wechsel: Teilart | None = Field(None, description="Die andere Art am selben Platz (Text umgeformt oder wie im Buch, "
                                                      "Kapitel nach Bereichen oder von A bis Z); leer: keine")
    beschreibung: str = Field(description="Was der Teil ins Buch bringt")


class Aufbau(BaseModel):
    """Welche Teile in welcher Reihenfolge: vor den Kapiteln, die Gliederung in Kapitel, im Kapitel (je Kapitel und je
    Artikel), nach den Kapiteln. Quellen und Lizenzen stehen immer am Ende und gehören nicht in den Aufbau."""
    vorn: list[Teil] = Field(default_factory=list, description="Teile vor den Kapiteln (Ebene buch)")
    gliederung: Gliederung = Field("kapitel", description="kapitel: je Bereich des Themas ein Kapitel; abc: alle Artikel "
                                                          "von A bis Z, je Anfangsbuchstabe ein Kapitel")
    innen: list[Teil] = Field(default_factory=list, description="Teile im Kapitel: je Kapitel (Einleitung, Fragen) und je "
                                                               "Artikel; Kapitelteile vor dem ersten Artikelteil stehen am "
                                                               "Anfang des Kapitels, die übrigen am Ende")
    hinten: list[Teil] = Field(default_factory=list, description="Teile nach den Kapiteln (Ebene buch), vor Quellen und Lizenzen")

    @model_validator(mode="after")
    def _stimmig(self) -> Aufbau:
        from ..alsbuch.teile import aufbau_pruefen   # der Katalog weiß, welcher Teil wohin darf
        aufbau_pruefen(self)
        return self


class Anweisung(BaseModel):
    """Was die KI beim Umformen beachtet; für wen, Länge und Fragen sind Vorgaben, beim Bestellen änderbar."""
    ton: Ton = Field("sachlich", description="sachlich, erzaehlend oder locker")
    fuer_wen: FuerWen = Field("erwachsene", description="Vorgabe: erwachsene, jugendliche oder kinder (ab 10)")
    laenge: Laenge = Field("haelfte", description="Vorgabe: original (alles), haelfte (etwa die Hälfte), wichtigste (etwa ein Viertel)")
    fragen: int = Field(5, ge=0, le=10, description="Vorgabe: so viele Fragen je Kapitel (Teil Fragen zum Kapitel)")
    zusatz: str = Field("", max_length=2000, description="Zusatz in eigenen Worten; geht so an das Modell, nach den festen Regeln")


class Gestaltung(BaseModel):
    """Wie das Buch aussieht (EPUB und PDF)."""
    schrift: Schrift = Field("serifen", description="Schrift im Text: serifen oder ohne")
    farbe: Farbe = Field("petrol", description="Farbe der Kästen und Überschriften: petrol, violett, honig, koralle, stahl")
    bilder: Bilder = Field("eins_gross", description="im_text (an ihrer Stelle), eins_gross (das Leitbild je Artikel) oder ohne")


class Vorlage(BaseModel):
    """Eine Vorlage: mitgeliefert (fest) oder eigene (eine Datei im Ordner Vorlagen der Ablage, Kellerwolke oder
    Datenordner)."""
    kennung: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{0,59}$", description="Name der Datei ohne .toml (klein, ASCII)")
    titel: str = Field(min_length=1, max_length=60, description="Name der Vorlage")
    symbol: str = Field("fa-book", pattern=r"^fa-[a-z0-9-]+$", description="Symbol (Name der Symbolschrift)")
    beschreibung: str = Field("", max_length=200, description="Ein Satz: was das Buch ausmacht")
    untertitel: str = Field("", max_length=60, description="Steht auf der Titelseite unter dem Titel (etwa Ein Lernheft)")
    mitgeliefert: bool = Field(False, description="Mitgeliefert und fest; ändern nur als Kopie")
    kopiert_aus: str = Field("", max_length=60, description="Titel der Vorlage, aus der diese kopiert ist")
    kopiert_am: str = Field("", max_length=10, description="Wann kopiert (JJJJ-MM-TT)")
    aufbau: Aufbau = Field(description="Teile in ihrer Reihenfolge")
    anweisung: Anweisung = Field(default_factory=Anweisung, description="Anweisung an die KI")
    gestaltung: Gestaltung = Field(default_factory=Gestaltung, description="Aussehen des Buchs")

    @computed_field(description="Braucht die KI (über die Leitstelle): mindestens ein Teil kommt von ihr")
    @property
    def ki(self) -> bool:
        from ..alsbuch.teile import braucht_ki
        return braucht_ki(self.aufbau)


class VorlageNeu(BaseModel):
    """Eine eigene Vorlage als Kopie einer vorhandenen."""
    titel: str = Field(min_length=1, max_length=60, description="Name der neuen Vorlage")


# ----- Bestellung --------------------------------------------------------------------------------------------------------

Seitengroesse = Literal["a5", "a4", "a4_zwei"]
Wann = Literal["jetzt", "nachts"]


class Kapitelwahl(BaseModel):
    """Ein Bereich des Themas im Buch: an oder aus, in der Reihenfolge der Liste."""
    bereich: str = Field(description="Kennung des Bereichs; leer: die Artikel ohne Bereich")
    an: bool = Field(True, description="Kommt ins Buch")


class Bestellung(BaseModel):
    """Was ins Buch kommt und wie (Seite Als Buch)."""
    thema: str = Field(description="Kennung des Themas")
    vorlage: str = Field(description="Kennung der Vorlage")
    kapitel: list[Kapitelwahl] = Field(default_factory=list, max_length=200,
                                       description="Bereiche in der Reihenfolge des Buchs; leer: alle Bereiche wie im Thema")
    notizen: bool = Field(True, description="Notizen als Randnotiz an ihrer Stelle")
    markierungen: bool = Field(True, description="Gemerkte Stellen (Markierungen ohne Text) als Hervorhebung")
    bilder: bool = Field(True, description="Bilder der Artikel (wie, sagt die Vorlage)")
    steckbriefe: bool = Field(False, description="Steckbriefe der Artikel als Tabelle am Anfang")
    uebersetzung: bool = Field(True, description="Bei Artikeln in anderer Sprache die abgelegte Übersetzung nehmen")
    fuer_wen: FuerWen = Field("erwachsene", description="Für wen (Vorgabe aus der Vorlage)")
    laenge: Laenge = Field("haelfte", description="Länge (Vorgabe aus der Vorlage)")
    fragen: int = Field(5, ge=0, le=10, description="Fragen je Kapitel (Vorgabe aus der Vorlage)")
    epub: bool = Field(True, description="Als EPUB (Lesegerät und Telefon)")
    pdf: bool = Field(True, description="Als PDF (zum Drucken)")
    seiten: Seitengroesse = Field("a5", description="Seitengröße des PDF: a5, a4 oder a4_zwei (zwei Seiten A5 je Blatt A4)")
    titelbild: str = Field("", max_length=2000, description="Adresse eines Bilds der Artikel; leer: das erste")
    wann: Wann = Field("nachts", description="jetzt oder nachts (im Fenster aus den Einstellungen)")

    @model_validator(mode="after")
    def _ein_format(self) -> Bestellung:
        if not (self.epub or self.pdf):
            raise ValueError("Mindestens ein Format wählen (EPUB oder PDF)")
        return self


# ----- Seite Als Buch: was das Thema hergibt -----------------------------------------------------------------------------

class Kapitelangabe(BaseModel):
    """Ein Bereich des Themas als mögliches Kapitel."""
    bereich: str = Field(description="Kennung des Bereichs; leer: ohne Bereich")
    titel: str = Field(description="Überschrift des Bereichs")
    artikel: int = Field(description="So viele Artikel stehen darin")
    lesbar: int = Field(description="So viele davon aus Büchern, die es in der Bibliothek gibt")
    bilder: list[str] = Field(default_factory=list, description="Bis zu drei Bilder der Artikel")


class Fremdartikel(BaseModel):
    """Ein Artikel aus einem Buch in anderer Sprache."""
    titel: str = Field(description="Titel des Artikels")
    sprache: str = Field(description="Sprache des Buchs (ISO 639-3)")
    uebersetzt: bool = Field(description="Eine Übersetzung ist abgelegt")


class Buchwahl(BaseModel):
    """Was ein Thema für ein Buch hergibt, mit den Zahlen für die Seite Als Buch."""
    thema: str = Field(description="Kennung des Themas")
    titel: str = Field(description="Titel des Themas, zugleich Titel des Buchs")
    artikel: int = Field(description="Artikel im Thema")
    kapitel: list[Kapitelangabe] = Field(description="Bereiche in der Reihenfolge des Themas, Artikel ohne Bereich zuletzt")
    notizen: int = Field(description="Notizen mit Text an den Artikeln des Themas")
    markierungen: int = Field(description="Gemerkte Stellen (Markierungen ohne Text)")
    bilder: int = Field(description="Bilder in den Artikeln")
    steckbriefe: int = Field(description="Artikel mit Steckbrief")
    fremd: list[Fremdartikel] = Field(default_factory=list, description="Artikel in anderer Sprache")
    titelbilder: list[str] = Field(default_factory=list, description="Mögliche Titelbilder (Leitbilder der Artikel)")
    auszug_titel: str = Field("", description="Titel des ersten Artikels (Vorschau einer Seite)")
    auszug: str = Field("", description="Anfang seines ersten Absatzes (Vorschau einer Seite)")
    modell: str = Field(description="Modell der Umformung (Einstellung Modell für Bücher)")
    leitstelle: bool = Field(description="Die Leitstelle ist eingerichtet (ohne sie gehen nur Vorlagen ohne KI)")
    pdf: str = Field("", description="Leer: PDF geht; sonst der Grund, warum der Satz als PDF hier nicht geht")
    ablage: str = Field(description="Ordner des Buchs in der Ablage (Kellerwolke oder Datenordner)")
    letzte: Bestellung | None = Field(None, description="Die zuletzt gebaute Bestellung dieses Themas (zum Vorbelegen)")


# ----- Schätzung ---------------------------------------------------------------------------------------------------------

class Schaetzschritt(BaseModel):
    """Ein Schritt der Dauer."""
    titel: str = Field(description="Was geschieht")
    sekunden: float = Field(description="Geschätzte Dauer")


class Schaetzung(BaseModel):
    """Dauer und Umfang aus der Hausmessung (Zeichen je Sekunde des Modells), vor dem Bauen."""
    artikel: int = Field(description="Artikel im Buch")
    kapitel: int = Field(description="Kapitel im Buch")
    zeichen: int = Field(description="Text der Artikel in Zeichen")
    seiten: int = Field(description="Seiten im Buch, geschätzt (bei PDF in der gewählten Größe, sonst A5)")
    schritte: list[Schaetzschritt] = Field(description="Die Schritte mit ihrer Dauer")
    sekunden: float = Field(description="Zusammen")
    tempo: float = Field(description="Zeichen je Sekunde, mit denen gerechnet wird")
    gemessen: bool = Field(description="Das Tempo ist gemessen (nach einem Auftrag); sonst die Hausmessung")
    modell: str = Field(description="Modell der Umformung")
    beginn: str = Field("", description="Bei nachts: Beginn (ISO, Ortszeit); sonst leer")
    ende: str = Field("", description="Voraussichtlich fertig (ISO, Ortszeit)")
    nacht_reicht: bool = Field(True, description="Falsch, wenn das Buch nicht in einer Nacht fertig wird (läuft dann weiter)")
    probe_titel: str = Field("", description="Artikel des Probekapitels")
    probe_sekunden: float = Field(0, description="Dauer des Probekapitels")


# ----- Inhalt eines Buchs ------------------------------------------------------------------------------------------------

class Bild(BaseModel):
    """Ein Bild im Buch."""
    adresse: str = Field(description="Adresse des Bilds in der App (Medien eines Buchs)")
    unterschrift: str = Field("", description="Bildunterschrift als Text")
    urheber: str = Field("", description="Urheber, soweit bekannt (große Bilder)")
    lizenz: str = Field("", description="Lizenz, soweit bekannt (große Bilder)")


class Belegt(BaseModel):
    """Ein Punkt oder Satz mit Belegen."""
    text: str = Field(description="Text")
    belege: list[int] = Field(default_factory=list, description="Nummern der Absätze im Original")


class Kasten(BaseModel):
    """Ein Kasten je Artikel (Auf einen Blick oder ein eigener)."""
    titel: str = Field(description="Überschrift")
    punkte: list[Belegt] = Field(default_factory=list, description="Die Punkte mit Belegen")


class Randnotiz(BaseModel):
    """Eine eigene Notiz im Buch."""
    text: str = Field(description="Text der Notiz")
    zitat: str = Field("", description="Die markierte Stelle, an der sie steht; leer: zum ganzen Artikel")


class Absatz(BaseModel):
    """Ein Absatz des Buchtexts."""
    text: str = Field(description="Text (umgeformt) oder leer, wenn html gesetzt ist")
    html: str = Field("", description="Nur beim Text wie im Buch: der Block als bereinigtes XHTML")
    art: Literal["absatz", "punkt", "tabelle", "zitat", "code"] = Field("absatz", description="Art des Blocks")
    liste: int = Field(0, description="Bei Punkten: Kennung der Liste, zu der sie gehören")
    geordnet: bool = Field(False, description="Bei Punkten: nummerierte Liste")
    ueberschrift: str = Field("", description="Zwischenüberschrift vor dem Absatz")
    ebene: int = Field(2, ge=2, le=4, description="Ebene der Zwischenüberschrift (2 wie ein Abschnitt des Artikels)")
    belege: list[int] = Field(default_factory=list, description="Nummern der Absätze im Original")
    ohne_beleg: list[str] = Field(default_factory=list, description="Sätze, die so nicht im Original stehen (Prüfung)")
    hervorgehoben: bool = Field(False, description="Trägt eine gemerkte Stelle")
    markiert: list[str] = Field(default_factory=list, description="Gemerkte Stellen, die wörtlich darin stehen")
    notizen: list[Randnotiz] = Field(default_factory=list, description="Notizen zu Stellen in diesem Absatz")
    bilder: list[Bild] = Field(default_factory=list, description="Bilder, die nach diesem Absatz stehen")


class Quellangabe(BaseModel):
    """Woher ein Artikel kommt (Quellen und Lizenzen)."""
    buch: str = Field(description="Titel des Buchs")
    fassung: str = Field("", description="Stand des Buchs (JJJJ-MM-TT)")
    adresse: str = Field("", description="Der Artikel im Netz, soweit bekannt")
    urheber: str = Field(description="Urheber des Texts")
    lizenz: str = Field(description="Lizenz des Texts")


class Buchartikel(BaseModel):
    """Ein Artikel im Buch."""
    eintrag: str = Field(description="Kennung des Eintrags im Thema")
    titel: str = Field(description="Titel")
    buch: str = Field(description="Kennung des Buchs, aus dem er stammt")
    pfad: str = Field(description="Pfad im Buch")
    quelle: Quellangabe = Field(description="Quelle und Lizenz")
    sprache: str = Field("de", description="Sprache der Vorlage des Texts (ISO 639-1)")
    leitbild: Bild | None = Field(None, description="Das Leitbild (Gestaltung eins groß)")
    steckbrief: str = Field("", description="Steckbrief als bereinigtes XHTML; leer: keiner")
    blick: Kasten | None = Field(None, description="Auf einen Blick")
    kaesten: list[Kasten] = Field(default_factory=list, description="Eigene Kästen, in der Reihenfolge der Vorlage")
    absaetze: list[Absatz] = Field(default_factory=list, description="Der Text")
    notizen: list[Randnotiz] = Field(default_factory=list, description="Notizen zum ganzen Artikel")
    zeichen_original: int = Field(0, description="Länge des Originals in Zeichen")


class Frage(BaseModel):
    """Eine Frage zum Kapitel."""
    frage: str = Field(description="Frage")
    antwort: str = Field(description="Kurze Antwort")
    belege: list[int] = Field(default_factory=list, description="Nummern der Artikel im Kapitel (ab 1), aus denen die Antwort stammt")


class Glossareintrag(BaseModel):
    """Ein Begriff im Glossar."""
    begriff: str = Field(description="Der Begriff")
    erklaerung: str = Field(description="Erklärung in einem Satz")


class Buchkapitel(BaseModel):
    """Ein Kapitel."""
    titel: str = Field(description="Überschrift")
    einleitung: list[Belegt] = Field(default_factory=list, description="Einleitung in Sätzen; Belege sind hier die Nummern "
                                                                       "der Artikel im Kapitel (ab 1)")
    artikel: list[Buchartikel] = Field(default_factory=list, description="Die Artikel")
    fragen: list[Frage] = Field(default_factory=list, description="Fragen zum Kapitel")


class Buchinhalt(BaseModel):
    """Der ganze Inhalt eines Buchs, aus dem EPUB, PDF und die Leseansicht entstehen."""
    titel: str = Field(description="Titel (des Themas)")
    untertitel: str = Field("", description="Untertitel (aus der Vorlage)")
    beschreibung: str = Field("", description="Beschreibung des Themas")
    vorlage: Vorlage = Field(description="Die Vorlage, mit der das Buch gebaut wurde (Stand beim Bauen)")
    titelbild: Bild | None = Field(None, description="Titelbild")
    kapitel: list[Buchkapitel] = Field(default_factory=list, description="Kapitel")
    glossar: list[Glossareintrag] = Field(default_factory=list, description="Glossar, alphabetisch")
    literatur: list[str] = Field(default_factory=list, description="Literaturliste, je Eintrag eine Zeile")
    erstellt: str = Field(description="Wann gebaut (JJJJ-MM-TT)")


# ----- Prüfung und Probekapitel -----------------------------------------------------------------------------------------

class Satzhinweis(BaseModel):
    """Ein Satz, der so nicht im Original steht, oder eine Zahl, die dort fehlt."""
    artikel: str = Field(description="Titel des Artikels")
    absatz: int = Field(description="Stelle des Absatzes im Buchtext (ab 0); -1: in einem Kasten")
    text: str = Field(description="Der Satz oder die Zahl")
    art: Literal["satz", "zahl", "beleg"] = Field(description="satz: steht so nicht im Original; zahl: Zahl fehlt im "
                                                             "Original; beleg: Absatz ohne gültigen Beleg")


class Pruefung(BaseModel):
    """Ergebnis der Prüfung gegen das Original."""
    zahlen: int = Field(description="Zahlen im Ergebnis")
    zahlen_gefunden: int = Field(description="Davon in den belegten Absätzen des Originals")
    absaetze: int = Field(description="Absätze und Punkte im Ergebnis")
    belegt: int = Field(description="Davon mit gültigem Beleg")
    hinweise: list[Satzhinweis] = Field(default_factory=list, description="Was nicht passt")


class Quellabsatz(BaseModel):
    """Ein Absatz des Originals, wie er ans Modell ging."""
    nr: int = Field(description="Nummer (Beleg)")
    text: str = Field(description="Text")
    ueberschrift: str = Field("", description="Überschrift des Abschnitts, der hier beginnt")


class Neuschreiben(BaseModel):
    """Ein Absatz des Probekapitels, den die KI neu schreiben soll."""
    absatz: int = Field(ge=0, description="Stelle des Absatzes im Ergebnis (ab 0)")


class Probewunsch(BaseModel):
    """Ein Probekapitel anstoßen: ein Artikel nach der Vorlage, mit den Angaben der Seite Als Buch."""
    bestellung: Bestellung = Field(description="Die Angaben der Seite Als Buch")
    eintrag: str = Field("", description="Kennung des Eintrags im Thema; leer: der erste Artikel des Buchs")
    neu: list[Neuschreiben] = Field(default_factory=list, max_length=50,
                                    description="Nur diese Absätze der letzten Probe neu schreiben lassen")


class Probe(BaseModel):
    """Ein Probekapitel: Original (der Anfang des Artikels) und Ergebnis nebeneinander, mit Prüfung."""
    thema: str = Field(description="Kennung des Themas")
    eintrag: str = Field(description="Kennung des Eintrags")
    vorlage: str = Field(description="Kennung der Vorlage")
    vorlage_titel: str = Field(description="Titel der Vorlage")
    fuer_wen: FuerWen = Field(description="Für wen")
    laenge: Laenge = Field(description="Länge")
    quelle: str = Field(description="Titel des Buchs, aus dem der Artikel stammt")
    zeichen_original: int = Field(description="Länge des ganzen Artikels in Zeichen")
    original: list[Quellabsatz] = Field(description="Die Absätze des Originals, die umgeformt wurden (der Anfang)")
    artikel: Buchartikel = Field(description="Das Ergebnis nach der Vorlage")
    kapitel: Buchkapitel = Field(description="Das Kapitel mit diesem einen Artikel (Einleitung und Fragen)")
    pruefung: Pruefung = Field(description="Prüfung gegen das Original")
    sekunden: float = Field(description="So lange hat die Umformung gedauert")
    seiten: int = Field(description="Seiten des Ergebnisses, geschätzt (A5)")
    wann: str = Field(description="Wann (ISO)")


# ----- Eigene Bücher -----------------------------------------------------------------------------------------------------

Bauzustand = Literal["wartet", "laeuft", "fehler", "abgebrochen", "unterbrochen"]


class Baustufe(BaseModel):
    """Eine Stufe des Baus: ein Kapitel, Glossar und Fragen, der Satz."""
    titel: str = Field(description="Beschriftung")
    zustand: Literal["offen", "jetzt", "fertig"] = Field(description="offen, jetzt oder fertig")
    anteil: float = Field(0, description="Wie weit (0 bis 1)")
    text: str = Field("", description="Etwa 4 von 4 Artikeln oder der Artikel, der gerade dran ist")


class Baustand(BaseModel):
    """Ein Buch, das gerade entsteht (ein Auftrag)."""
    auftrag: str = Field(description="Kennung des Auftrags")
    zustand: Bauzustand = Field(description="Zustand des Auftrags")
    grund: str = Field("", description="Warum er wartet oder woran er scheiterte")
    titel: str = Field(description="Etwa Sternenhimmel als Lernheft")
    beschreibung: str = Field(description="Formate, Umfang und Modell in Worten")
    thema: str = Field(description="Kennung des Themas")
    titelbild: str = Field("", description="Titelbild")
    vorlage_titel: str = Field(description="Titel der Vorlage")
    begonnen: str = Field("", description="Wann er begann (ISO); leer: wartet noch")
    anteil: float = Field(0, description="Umgeformt (0 bis 1)")
    tempo: float = Field(0, description="Gemessene Zeichen je Sekunde in diesem Auftrag; 0: noch keine Messung")
    fertig_gegen: str = Field("", description="Voraussichtlich fertig (ISO)")
    hinweise: int = Field(0, description="Hinweise der Prüfung bisher")
    stufen: list[Baustufe] = Field(default_factory=list, description="Die Stufen in ihrer Reihenfolge")


class Buchformat(BaseModel):
    """Eine Datei des Buchs in der Ablage."""
    format: Literal["epub", "pdf"] = Field(description="epub oder pdf")
    titel: str = Field(description="Beschriftung, etwa PDF A5")
    pfad: str = Field(description="Pfad in der Ablage")
    groesse: int = Field(description="Größe in Bytes")


class Veraltet(BaseModel):
    """Das Thema hat sich seit dem Bau geändert."""
    neu: int = Field(description="Neue Artikel")
    weg: int = Field(description="Herausgenommene Artikel")
    text: str = Field(description="In Worten")
    sekunden: float = Field(description="Dauer des Nachbaus (nur das Neue wird umgeformt)")


class Eigenbuch(BaseModel):
    """Ein fertiges Buch im Regal."""
    id: str = Field(description="Kennung des Buchs")
    thema: str = Field(description="Kennung des Themas")
    titel: str = Field(description="Titel")
    vorlage: str = Field(description="Kennung der Vorlage")
    vorlage_titel: str = Field(description="Titel der Vorlage")
    artikel: int = Field(description="Artikel im Buch")
    seiten: int = Field(description="Seiten (PDF gezählt, sonst geschätzt)")
    gebaut: str = Field(description="Wann gebaut (ISO)")
    titelbild: str = Field("", description="Titelbild (Adresse in der App)")
    formate: list[Buchformat] = Field(description="Die Dateien")
    hinweise: list[Satzhinweis] = Field(default_factory=list, description="Hinweise der Prüfung")
    veraltet: Veraltet | None = Field(None, description="Das Thema hat sich geändert; leer: passt")


class Regal(BaseModel):
    """Eigene Bücher: was gerade entsteht und was fertig ist."""
    laufend: list[Baustand] = Field(description="Bücher, die entstehen, warten oder angehalten sind")
    fertig: list[Eigenbuch] = Field(description="Fertige Bücher, neueste zuerst")
    ablage: str = Field(description="Ordner der Bücher in der Ablage (Kellerwolke oder Datenordner)")


class Leseansicht(BaseModel):
    """Ein fertiges Buch zum Lesen in der App."""
    titel: str = Field(description="Titel")
    untertitel: str = Field(description="Untertitel")
    html: str = Field(description="Der Inhalt als XHTML (Bilder mit Adressen der App)")


class Vorlagenliste(BaseModel):
    """Alle Vorlagen: mitgelieferte zuerst, dann die eigenen aus der Ablage."""
    vorlagen: list[Vorlage] = Field(description="Die Vorlagen")
    ordner: str = Field(description="Ordner der eigenen Vorlagen in der Ablage")
    hinweis: str = Field("", description="Was sich nicht lesen ließ (Ablage nicht erreichbar, Datei kaputt); leer: alles gut")


class Teilkatalog(BaseModel):
    """Was eine Vorlage enthalten kann und welche Regeln immer gelten."""
    teile: list[Teilangabe] = Field(description="Alle Teile mit Beschriftung, Herkunft und Ebene")
    regeln: list[str] = Field(description="Die festen Regeln in Worten (gelten für jede Vorlage)")


class Nachbau(BaseModel):
    """Ein Buch nach Änderungen am Thema neu bauen (nur Neues wird umgeformt)."""
    wann: Wann = Field("jetzt", description="jetzt oder nachts")
