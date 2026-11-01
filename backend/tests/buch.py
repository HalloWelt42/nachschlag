"""Ein kleines Buch für die Tests, gebaut mit dem Schreiber von libzim im Aufbau der Enzyklopädie (mwoffliner):
Artikel mit Steckbrief, Bild, Abschnitten und Belegen, eine Weiterleitung auf einen Abschnitt, ein Verweis ohne Ziel,
Koordinaten und ein Online-Verweis."""

from __future__ import annotations

from pathlib import Path

from libzim.writer import Creator, Hint, Item, StringProvider

# kleinstes gültiges PNG (1 x 1 Pixel)
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


def seite(titel: str, rumpf: str) -> str:
    return (f'<!DOCTYPE html><html><head><title>{titel}</title><script src="./_mw_/x.js"></script></head><body>'
            f'<div class="mw-page-container"><main id="content"><header><h1 class="firstHeading">{titel}</h1></header>'
            f'<div id="mw-content-text" class="mw-body-content"><div class="mw-content-ltr">{rumpf}</div></div></main></div></body></html>')


#: typografische Anführungszeichen wie in echten Artikeln (als Codepunkt, damit die Quelle gerade bleibt)
AUF, ZU = chr(0x201E), chr(0x201C)

ROTFUCHS = seite("Rotfuchs", f"""
<table class="float-right taxobox infobox"><tbody>
<tr><th>Rotfuchs</th></tr>
<tr><td><img src="./_assets_/a/fuchs.png" width="300" height="200" alt="Fuchs"><br>Rotfuchs (<i>Vulpes vulpes</i>)
<span class="ext-phonos">Bellender Fuchs&#9432;</span></td></tr>
<tr><th>Systematik</th></tr>
<tr><td>Ordnung:</td><td><a href="Raubtiere">Raubtiere</a></td></tr>
<tr><td>Familie:</td><td>Hunde</td></tr>
</tbody></table>
<p>Der <b>Rotfuchs</b> ist der einzige mitteleuropäische Vertreter der <a href="Echte_F%C3%BCchse">Füchse</a> und
wird daher meistens als {AUF}der Fuchs{ZU} bezeichnet<sup class="reference"><a href="#cite-1">[1]</a></sup>.</p>
<div class="mw-heading mw-heading2"><h2 id="Merkmale">Merkmale</h2><span class="mw-editsection">bearbeiten</span></div>
<p>Das Fell ist rötlich; der <a href="Kreuzfuchs">Kreuzfuchs</a> trägt einen Streifen. Siehe <a href="Gibt_es_nicht">dies</a>.</p>
<figure><img src="./_assets_/a/fuchs.png" width="250" height="160"><figcaption>Ein Fuchs</figcaption></figure>
<div class="mw-heading mw-heading2"><h2 id="Lebensraum">Lebensraum</h2></div>
<p>Stadtfüchse leben in Städten wie <a href="geo:52.5,13.4">Berlin</a> und suchen Futter in Gärten und Parks der Städte.</p>
<table class="userboxes" style="float: right; width: 248px"><tbody><tr><td><table class="klade" style="border-collapse:collapse">
<tr><td style="min-width:1em; border-bottom:2px solid;"> <i>Vulpes</i> </td><td rowspan="2"><p><a href="Kreuzfuchs">Kreuzfuchs</a></p></td></tr>
<tr><td style="border-left:2px solid; border-bottom:2px solid;"></td></tr>
<tr><td valign="top"><br><span style="display:none;">Vorlage:Klade/Wartung/3</span></td></tr></table></td></tr></tbody></table>
<div class="mw-heading mw-heading2"><h2 id="Einzelnachweise">Einzelnachweise</h2></div>
<ol class="references"><li id="cite-1"><a href="https://example.org/beleg">Beleg</a></li></ol>
<div class="mw-heading mw-heading2"><h2 id="Weblinks">Weblinks</h2></div>
<ul><li><a href="https://example.org/weblink">Weblink</a></li><li><a href="https://archive.invalid/x">tot</a></li></ul>
""")


#: Aufbau heutiger Seiten: jeder Abschnitt in einem eigenen <section>, die Überschrift vorn
ARRHENIUS = seite("Svante Arrhenius", """
<section><p>Svante Arrhenius war ein schwedischer Physiker und Chemiker.</p></section>
<section><div class="mw-heading mw-heading2"><h2 id="Leben">Leben</h2></div><p>Er wurde 1859 geboren.</p>
<figure><img src="./_assets_/a/K%C3%B6ln%252C_Ufer.png" width="200" height="120"><figcaption>Köln</figcaption></figure></section>
<section><div class="mw-heading mw-heading2"><h2 id="Literatur">Literatur</h2></div><ul><li>Ein Buch</li></ul></section>
<section><div class="mw-heading mw-heading2"><h2 id="Weblinks">Weblinks</h2></div><ul><li><a href="https://example.org/arrhenius">Seite</a></li></ul></section>
<section><div class="mw-heading mw-heading2"><h2 id="Einzelnachweise">Einzelnachweise</h2></div><ol class="references"><li>Beleg</li></ol></section>
""")


#: Infobox wie in der englischen Ausgabe: Zellen mit Klassen, Bild mit Unterschrift, Verweis und spitze Klammern im Wert
AEGYPTEN = seite("Ancient Egypt", """
<table class="infobox vcard"><tbody>
<tr><th colspan="2" class="infobox-above">Ancient Egypt</th></tr>
<tr><td colspan="2" class="infobox-image"><img src="./_assets_/a/fuchs.png" width="250" height="160"><div class="infobox-caption">Map of the Nile</div></td></tr>
<tr><th scope="row" class="infobox-label">Capital</th><td class="infobox-data" style="color:red"><i>See</i> <a href="Raubtiere">List of capitals</a> &lt;x&gt;</td></tr>
<tr><th scope="row" class="infobox-label">Religion</th><td class="infobox-data">Egyptian religion</td></tr>
</tbody></table>
<p>Ancient Egypt was a civilization of ancient Northeast Africa.</p>
""")


#: Startseite wie bei mwoffliner: eigene Kachelseite ohne Artikelaufbau, Anordnung per Skript; eine Kachel zeigt auf
#: einen Artikel, den es im Buch nicht gibt
STARTSEITE = ('<html><head><title>Probelexikon</title><script src="./_res_/masonry.min.js"></script></head>'
              '<body class="article-list-home mw-body-content nojs"><div id="container"><div id="content">'
              '<a class="item" href="Rotfuchs"><figure><img loading="lazy" src="./_assets_/a/fuchs.png"><figcaption>Rotfuchs</figcaption></figure></a>'
              '<a class="item" href="Kreuzfuchs"><figure><figcaption>Kreuzfuchs</figcaption></figure></a>'
              '<a class="item" href="Gibt_es_nicht"><figure><figcaption>Fehlt</figcaption></figure></a>'
              '</div></div></body></html>')


def artikel(titel: str, text: str) -> str:
    return seite(titel, f"<p>{text}</p>")


class _Seite(Item):
    def __init__(self, pfad: str, titel: str, inhalt: str | bytes, mime: str = "text/html", vorne: bool = True) -> None:
        super().__init__()
        self._pfad, self._titel, self._inhalt, self._mime, self._vorne = pfad, titel, inhalt, mime, vorne

    def get_path(self): return self._pfad
    def get_title(self): return self._titel
    def get_mimetype(self): return self._mime
    def get_contentprovider(self): return StringProvider(self._inhalt)
    def get_hints(self): return {Hint.FRONT_ARTICLE: self._vorne}


def bauen(ordner: Path, name: str = "probe_de_all_2026-01", erzeuger: str = "mwoffliner 1.17.4") -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / f"{name}.zim"
    with Creator(str(datei)).config_indexing(True, "deu") as c:
        c.set_mainpath("index")
        for schluessel, wert in (("Name", name.rsplit("_", 1)[0]), ("Title", "Probelexikon"), ("Language", "deu"),
                                 ("Description", "Buch für die Tests"), ("Date", "2026-01-15"), ("Scraper", erzeuger),
                                 ("Creator", "Tests"), ("Publisher", "Tests")):
            c.add_metadata(schluessel, wert)
        c.add_item(_Seite("index", "Probelexikon", STARTSEITE))
        c.add_item(_Seite("Rotfuchs", "Rotfuchs", ROTFUCHS))
        c.add_item(_Seite("Ancient_Egypt", "Ancient Egypt", AEGYPTEN))
        c.add_item(_Seite("Svante_Arrhenius", "Svante Arrhenius", ARRHENIUS))
        c.add_item(_Seite("Raubtiere", "Raubtiere", artikel("Raubtiere", "Raubtiere sind eine Ordnung der Säugetiere.")))
        c.add_item(_Seite("Echte_Füchse", "Echte Füchse", artikel("Echte Füchse", "Die echten Füchse bilden eine Gattungsgruppe.")))
        c.add_item(_Seite("Kreuzfuchs", "Kreuzfuchs", artikel("Kreuzfuchs", "Der Kreuzfuchs ist eine Farbform des Rotfuchses.")))
        c.add_item(_Seite("Stadtfuchs", "Stadtfuchs", "<html><head><meta http-equiv=\"refresh\" content=\"0;URL='./Rotfuchs#Lebensraum'\" /></head></html>"))
        c.add_item(_Seite("_assets_/a/fuchs.png", "", PNG, "image/png", vorne=False))
        # ein Name mit wörtlichem %2C (so heißen Bilder in der Quelle); im HTML steht er verschlüsselt als %252C
        c.add_item(_Seite("_assets_/a/Köln%2C_Ufer.png", "", PNG, "image/png", vorne=False))
    return datei
