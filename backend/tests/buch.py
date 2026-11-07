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
        # Sprungseite mit Text (wie Vulpes_vulpes in der Wikipedia): der Volltext findet sie, die Suche zeigt ihr Ziel
        c.add_item(_Seite("Vulpes_vulpes", "Vulpes vulpes", "<html><head><meta http-equiv=\"refresh\" content=\"0;URL='./Rotfuchs'\" /></head>"
                                                            "<body>Rotfuchs: Füchse leben auch in Städten.</body></html>"))
        c.add_item(_Seite("_assets_/a/fuchs.png", "", PNG, "image/png", vorne=False))
        # ein Name mit wörtlichem %2C (so heißen Bilder in der Quelle); im HTML steht er verschlüsselt als %252C
        c.add_item(_Seite("_assets_/a/Köln%2C_Ufer.png", "", PNG, "image/png", vorne=False))
    return datei


# ----- Probebuch Dokumentation (Aufbau devdocs2zim, Handbuch von PHP) ---------------------------------------------------

def _doku_seite(titel: str, rumpf: str) -> str:
    return (f'<html class="_theme-default"><head><meta charset="utf-8"><title>{titel}</title>'
            '<link rel="stylesheet" href="application.css"></head><body><div class="_app">'
            '<devdocs-navbar current="x" listing-src="navbar.json"></devdocs-navbar><div class="_container"><main class="_content">'
            f'<div class="_page _php">{rumpf}<div class="_attribution"><p class="_attribution-p">&copy; PHP Documentation Group'
            '<br><a href="https://www.php.net/manual/en/" class="_attribution-link">php.net</a></p></div></div>'
            '</main></div></div><script src="assets/index.js"></script></body></html>')


ARRAY_MAP = _doku_seite("array_map", """<div id="function.array-map" class="refentry"> <div class="refnamediv">
<h1 class="refname">array_map</h1> <p class="verinfo">(PHP 4 &gt;= 4.0.6, PHP 5, PHP 7, PHP 8)</p>
<p class="refpurpose"><span class="refname">array_map</span> - <span class="dc-title">Applies the callback to the elements</span></p></div>
<div class="refsect1 description" id="d"><h3 class="title">Description</h3>
<pre class="methodsynopsis dc-description" data-language="php">array_map(?callable $callback, array $array, array ...$arrays): array</pre>
<p class="para">Returns an <span class="type"><a href="language.types.array" class="type array">array</a></span>.</p></div>
<div class="refsect1 parameters" id="p"><h3 class="title">Parameters</h3><dl><dt><code class="parameter">callback</code></dt>
<dd><p class="para">A callable.</p></dd><dt><code class="parameter">arrays</code></dt><dd><p class="para">More arrays.</p></dd></dl></div>
<div class="refsect1 changelog" id="c"><h3 class="title">Changelog</h3><table class="doctable informaltable"><thead><tr><th>Version</th>
<th>Description</th></tr></thead><tbody class="tbody"><tr><td>8.0.0</td><td>Emits a warning.</td></tr></tbody></table></div>
<div class="refsect1 examples" id="e"><h3 class="title">Examples</h3><div class="example" id="example-1">
<p><strong>Example #1 <span class="function"><strong>array_map()</strong></span> example</strong></p>
<div class="example-contents"><pre class="annotation-interactive phpcode" data-language="php">&lt;?php
$b = array_map('cube', [1, 2]);
?&gt;</pre></div><div class="example-contents"><p>The above example will output:</p></div>
<div class="example-contents screen"><div class="annotation-interactive examplescode"><pre class="examplescode">Array
(
)</pre></div></div></div></div>
<div class="refsect1 seealso" id="s"><h3 class="title">See Also</h3><ul class="simplelist"><li><span class="function">
<a href="function.array-filter" class="function">array_filter()</a> - Filters elements of an array</span></li></ul></div></div>""")

ARRAY_FILTER = _doku_seite("array_filter", '<div class="refentry"><h1 class="refname">array_filter</h1>'
                                           '<p class="para">Filters elements of an array using a callback function.</p></div>')

GLIEDERUNG = ('{"name": "PHP", "landingHref": "index", "children": [{"name": "Array", "children": ['
              '{"name": "array_filter", "href": "function.array-filter"}, {"name": "array_map", "href": "function.array-map"}]}]}')


def bauen_doku(ordner: Path, name: str = "probedoku_en_php_2026-08") -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / f"{name}.zim"
    with Creator(str(datei)).config_indexing(True, "eng") as c:
        c.set_mainpath("index")
        for schluessel, wert in (("Name", name.rsplit("_", 1)[0]), ("Title", "PHP Probe"), ("Language", "eng"),
                                 ("Description", "Handbuch für die Tests"), ("Date", "2026-08-18"),
                                 ("Scraper", "devdocs2zim v0.2.1"), ("Creator", "Tests"), ("Publisher", "Tests")):
            c.add_metadata(schluessel, wert)
        c.add_item(_Seite("index", "PHP Probe", _doku_seite("PHP", "<h1>PHP: Hypertext Preprocessor</h1>")))
        c.add_item(_Seite("function.array-map", "array_map", ARRAY_MAP))
        c.add_item(_Seite("function.array-filter", "array_filter", ARRAY_FILTER))
        c.add_item(_Seite("navbar.json", "", GLIEDERUNG, "application/json", vorne=False))
    return datei


# ----- Probebuch Spiegel von php.net (warc2zim): dasselbe Handbuch in der Seite von php.net ------------------------------

SPIEGEL_SEITE = """<html><head><title>PHP: array_map - Manual</title><script src="/_zim_static/wombat.js"></script></head><body>
<div id="breadcrumbs"><ul><li><a href="index.php">PHP Manual</a></li><li><a href="book.array.php">Arrays</a></li>
<li><a href="ref.array.php">Array Functions</a></li></ul></div>
<section id="layout-content"><div class="page-tools"><form><select onchange="x()"><option>English</option></select></form></div>
<div id="function.array-map" class="refentry"><div class="refnamediv"><h1 class="refname">array_map</h1>
<p class="verinfo">(PHP 4 &gt;= 4.0.6, PHP 8)</p><p class="refpurpose"><span class="dc-title">Applies the callback</span></p></div>
<div class="refsect1 examples"><h3 class="title">Examples</h3><div class="example" id="example-5040">
<p><strong>Example #1 array_map() example</strong></p><div class="example-contents"><div class="phpcode"><code><span style="color: #000000">
<span style="color: #0000BB">&lt;?php<br /></span><span style="color: #0000BB">$b&nbsp;</span>=&nbsp;<span style="color: #0000BB">array_map</span>(<span style="color: #DD0000">'cube'</span>);<br /><span style="color: #0000BB">?&gt;</span>
</span></code></div></div></div></div></div>
<section id="usernotes"><h3 class="title">User Contributed Notes <span class="count">2 notes</span></h3>
<div id="allnotes"><div class="note" id="1"><div class="text">first</div></div><div class="note" id="2"><div class="text">second</div></div></div></section>
</section><aside class="layout-menu"><ul class="parent-menu-list"><li><a href="ref.array.php">Array Functions</a>
<ul class="child-menu-list"><li><a href="function.array-keys.php" title="array_keys">array_&#8203;keys</a></li>
<li class="current"><a href="function.array-map.php" title="array_map">array_&#8203;map</a></li></ul></li></ul></aside></body></html>"""


SPIEGEL_INHALT = """<html><body><section id="layout-content"><h1>PHP Manual</h1><ul class="chunklist chunklist_set">
<li><a href="copyright.php">Copyright</a></li><li><a href="funcref.php">Function Reference</a>
<ul class="chunklist chunklist_set chunklist_children"><li><a href="function.array-map.php">array_map</a></li>
<li><a href="function.array-keys.php">array_keys</a></li></ul></li></ul></section></body></html>"""


def bauen_spiegel(ordner: Path, name: str = "probespiegel_en_all_2024-08") -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / f"{name}.zim"
    with Creator(str(datei)).config_indexing(True, "eng") as c:
        c.set_mainpath("www.php.net/manual/en/function.array-map.php")
        for schluessel, wert in (("Name", name.rsplit("_", 1)[0]), ("Title", "PHP Manual Probe"), ("Language", "eng"),
                                 ("Description", "Spiegel für die Tests"), ("Date", "2024-08-13"),
                                 ("Scraper", "warc2zim 2.1.0,zimit 2.1.0"), ("Source", "https://www.php.net/manual"),
                                 ("Creator", "Tests"), ("Publisher", "Tests")):
            c.add_metadata(schluessel, wert)
        c.add_item(_Seite("www.php.net/manual/en/function.array-map.php", "array_map", SPIEGEL_SEITE))
        c.add_item(_Seite("www.php.net/manual/en/function.array-keys.php", "array_keys", "<html><body><p>keys</p></body></html>"))
        c.add_item(_Seite("www.php.net/manual/en/index.php", "PHP Manual", SPIEGEL_INHALT))
    return datei


# ----- Probebuch Frage und Antwort (sotoki) ------------------------------------------------------------------------------

def _qa_beitrag(art: str, kennung: str, punkte: str, text: str, wer: str, wann: str, kommentare: str = "") -> str:
    klasse = {"frage": 'id="question" class="question" data-questionid="84"',
              "antwort": f'id="answer-{kennung}" class="answer" data-answerid="{kennung}"',
              "akzeptiert": f'id="answer-{kennung}" class="answer accepted-answer" data-answerid="{kennung}"'}[art]
    return (f'<div {klasse} data-score="{punkte}"><div class="post-layout"><div class="votecell"><div class="js-vote-count">{punkte}</div></div>'
            f'<div class="postcell"><div class="s-prose js-post-body">{text}</div>'
            + ('<div class="post-taglist"><a href="../../questions/tagged/os-clipboard" class="post-tag">os-clipboard</a></div>'
               if art == "frage" else "")
            + f'<div class="post-signature"><div class="s-user-card"><time class="s-user-card--time" datetime="{wann}">{wann}</time>'
            f'<div class="s-user-card--info"><a href="../../users/{len(wer)}/{wer.lower().replace(" ", "-")}" class="s-user-card--link">{wer}</a>'
            '</div></div></div></div>'
            f'<div class="comments"><ul class="comments-list">{kommentare}</ul></div></div></div>')


FRAGE = ('<html><head><title>Clipboard</title></head><body><div id="question-header"><h1><a href="../../questions/84/clipboard"'
         ' class="question-hyperlink">How can I copy text to the clipboard?</a></h1></div>'
         + _qa_beitrag("frage", "84", "520", "<p>Is there a way to copy a block of text?</p>", "thameera", "asked Feb 03 '15 at 18:16",
                       '<li class="comment js-comment" data-comment-score="15"><span class="comment-copy">Asked on SO.</span>'
                       ' - <a class="comment-user" href="../../users/2/b">bsmith89</a></li>')
         + _qa_beitrag("antwort", "97", "53", "<pre><code>set clipboard=unnamedplus\n</code></pre>", "Quincy Bowers", "answered Feb 03 '15 at 19:00")
         + _qa_beitrag("akzeptiert", "96", "40", "<p>Use the <code>+</code> register.</p>", "Martin Tournoij", "answered Feb 03 '15 at 18:30")
         + '<div id="sidebar"><a href="../../questions/332/registers" class="question-hyperlink">Define registers</a></div></body></html>')


FRAGENLISTE = ('<html><body><h1>Most Popular</h1><div class="question-summary" id="question-summary-84"><div class="statscontainer">'
               '<div class="votes"><span class="vote-count-post"><strong>1,520</strong></span></div>'
               '<div class="status answered-accepted"><strong>2</strong> answers</div></div><div class="summary"><h3>'
               '<a href="./questions/84/clipboard" class="question-hyperlink">How can I copy text to the clipboard?</a></h3>'
               '<div class="excerpt">Is there a way?</div><a href="./questions/tagged/os-clipboard" class="post-tag">os-clipboard</a>'
               '<time class="s-user-card--time" datetime="asked Feb 03 \'15 at 18:16">x</time></div></div>'
               '<div class="s-pagination"><a class="s-pagination--item" href="./questions_page=2" rel="next">Next</a></div></body></html>')


def bauen_qa(ordner: Path, name: str = "probeqa_en_all_2026-10") -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / f"{name}.zim"
    with Creator(str(datei)).config_indexing(True, "eng") as c:
        c.set_mainpath("questions")
        for schluessel, wert in (("Name", name.rsplit("_", 1)[0]), ("Title", "Vi Probe"), ("Language", "eng"),
                                 ("Description", "Fragen für die Tests"), ("Date", "2026-10-01"), ("Scraper", "sotoki 2.2.0"),
                                 ("Creator", "Tests"), ("Publisher", "Tests")):
            c.add_metadata(schluessel, wert)
        c.add_item(_Seite("questions/84/clipboard", "How can I copy text to the clipboard?", FRAGE))
        c.add_item(_Seite("questions/332/registers", "Define registers", "<html><body><p>registers</p></body></html>"))
        c.add_item(_Seite("questions", "Most Popular", FRAGENLISTE))
        c.add_item(_Seite("questions_page=2", "Most Popular", "<html><body><h1>Most Popular</h1></body></html>"))
    return datei


# ----- Probebuch Anleitung (Aufbau iFixit, WIKI-64): kein Scraper, Kategorie in den Schlagworten -------------------------

def _anleitung(titel: str, schritte: list[list[tuple[str, str]]], einleitung: str, schwierigkeit: int = 3,
               zeit: str = "15 - 30 Minuten", werkzeuge: tuple[str, ...] = ("Spudger", "Pinzette"), zerlegung: bool = False) -> str:
    """Eine Seite wie die Anleitungen der Quelle; jede Zeile ist (Klassen, Text)."""
    zeilen = lambda z: "".join(f'<li class="{k}"><div class="bullet"></div><p>{t}</p></li>' for k, t in z)  # noqa: E731
    teile = "".join(
        f'<li class="step step-wrapper"><div class="row step-container"><div class="stepMedia">'
        f'<img class="js-step-main-image" src="../../images/s{nr}a.png"></div><div class="step-content">'
        f'<div class="row step-thumbnails"><img src="../../images/s{nr}a.png"><img src="../../images/s{nr}b.png"></div>'
        f'<ul class="step-lines">{zeilen(z)}</ul></div></div></li>' for nr, z in enumerate(schritte, 1))
    werkzeugliste = "".join(f'<li><div class="row attachment-container"><img src="../../images/w.png"><p itemprop="name" class="title">{w}</p></div></li>'
                            for w in werkzeuge)
    return (f'<html lang="fr"><body class="user-guide">{"<div class=teardown-image-overlay></div>" if zerlegung else ""}'
            f'<h1 class="guide-intro-title guide-title">{titel}</h1><div class="guide-author">Geschrieben von: <a href="../../User/1/x">Tester</a></div>'
            f'<div class="guide-main-image-container"><img src="../../images/haupt.png"></div>'
            f'<div class="details-item difficulty row difficulty-{schwierigkeit}"><p class="item-title">Schwierigkeitsgrad</p><p class="item-value">Mittel</p></div>'
            f'<div id="guide-time-required"><div class="details-item row"><p class="item-title">Zeitaufwand</p><p class="item-value">{zeit}</p></div></div>'
            f'<div class="introduction-container"><h2>Einleitung</h2><div itemprop="description"><p>{einleitung}</p></div></div>'
            f'<div class="tools-and-parts"><div class="item-list-tools"><ul>{werkzeugliste}</ul></div>'
            f'<div class="item-list-parts"><ul><li><p itemprop="name">Akku</p></li></ul></div></div>'
            f'<ol class="steps-container"><section>{teile}</section></ol>'
            f'<div class="conclusionText"><p>Baue das Gerät in umgekehrter Reihenfolge wieder zusammen.</p></div></body></html>')


AKKU = _anleitung("Probephone Akku tauschen", [
    [("level-0 bullet-line-icon-caution", "Entlade den Akku vor dem Beginn auf unter 25 Prozent, damit er nicht brennt."),
     ("level-0", "Löse die zwei Schrauben an der Unterseite und hebe die Rückseite mit dem Spudger an.")],
    [("level-0", "Achte auf die drei Stellen, an denen du nicht hebeln darfst:"),
     ("level-1", '<span class="bullet_red"></span>Kamera'), ("level-1", '<span class="bullet_yellow"></span>Antenne'),
     ("level-0 bullet-line-icon-note", "Wenn der Kleber nicht nachgibt, erwärme ihn noch einmal mit dem iOpener.")]],
    "Diese Anleitung zeigt, wie du den Akku im Probephone tauschst. Du brauchst dafür nur wenig Werkzeug und etwas Geduld.",
    schwierigkeit=2, zeit="30 Minuten - 1 Stunde")
DISPLAY_EN = _anleitung("Probephone Display Replacement", [
    [("level-0", "Remove the two screws at the bottom of the phone and lift the screen with a suction cup.")]],
    "This guide shows you how to replace the display of the Probephone. It is easy if you have the right tools for it.",
    schwierigkeit=4, zeit="1 - 2 Stunden", werkzeuge=("Spudger", "Suction Cup", "Heat Gun"))
ZERLEGUNG = _anleitung("Probephone Teardown", [[("level-0", "Wir öffnen das Gerät und sehen uns das Innere an, Schicht für Schicht.")]],
                       "Wir zerlegen das Probephone und zeigen, was darin steckt und wie es gebaut ist.", zerlegung=True)
GERAET = ('<html lang="fr"><body><div id="banner"><div class="banner-content"><img class="banner-small-photo" src="../images/g.png">'
          '<h1 class="banner-title">Probephone</h1><p class="banner-blurb">Ein Telefon für die Tests, gebaut 2026.</p></div></div>'
          '<div class="highlight-guides"><div class="entry-container"><a href="../Anleitung/Probephone+Akku+tauschen/1" class="entry">'
          '<img src="../images/s1a.png"><div class="entry-text"><h4>Probephone Akku tauschen</h4><p>Den Akku tauschen</p></div></a></div></div>'
          '<div class="js-guide-section"><a href="../Anleitung/Probephone+Akku+tauschen/1"><h4>Akku</h4></a>'
          '<a href="../Anleitung/Probephone+Display+Replacement/2"><h4>Display</h4></a>'
          '<a href="../Teardown/Probephone+Teardown/3"><h4>Zerlegung</h4></a></div>'
          '<div class="deviceToolsList"><p class="title">Spudger</p><p class="title">Pinzette</p></div>'
          '<div class="wikiRenderedText"><p>Das Probephone ist ein Telefon, das es nur in den Tests gibt.</p></div></body></html>')
KATEGORIE = ('<html lang="fr"><body><div id="banner"><div class="banner-content"><h1 class="banner-title">Smartphones</h1>'
             '<p class="banner-blurb">Alle Telefone.</p></div></div><div class="categoryListCell"><a href="../Device/Probephone" class="categoryAnchor">'
             '<img src="../images/g.png" class="category-image"><h5 class="title"> Probephone</h5></a></div></body></html>')
START = ('<html lang="fr"><body><div class="featured-categories"><a class="featured-category-item" href="../Device/Phone">'
         '<p class="featured-category-title">Smartphones</p><img src="../images/g.png"></a></div>'
         '<div class="sub-categories"><a class="sub-category" href="../Device/Phone"><span class="sub-category-title-text">Smartphones</span></a></div></body></html>')


def bauen_anleitungen(ordner: Path, name: str = "probefix_de_all_2026-03") -> Path:
    ordner.mkdir(parents=True, exist_ok=True)
    datei = ordner / f"{name}.zim"
    with Creator(str(datei)).config_indexing(True, "deu") as c:
        c.set_mainpath("home/home")
        for schluessel, wert in (("Name", name.rsplit("_", 1)[0]), ("Title", "Probefix"), ("Language", "deu"),
                                 ("Description", "Anleitungen für die Tests"), ("Date", "2026-03-19"), ("Creator", "iFixit"),
                                 ("Publisher", "openZIM"), ("Tags", "iFixit;_pictures:yes;_category:iFixit;_videos:yes")):
            c.add_metadata(schluessel, wert)
        c.add_item(_Seite("home/home", "Probefix", START))
        c.add_item(_Seite("Anleitung/Probephone+Akku+tauschen/1", "Probephone Akku tauschen", AKKU))
        c.add_item(_Seite("Anleitung/Probephone+Display+Replacement/2", "Probephone Display Replacement", DISPLAY_EN))
        c.add_item(_Seite("Teardown/Probephone+Teardown/3", "Probephone Teardown", ZERLEGUNG))
        c.add_item(_Seite("Device/Probephone", "Probephone", GERAET))
        c.add_item(_Seite("Device/Phone", "Smartphones", KATEGORIE))
        c.add_item(_Seite("User/1/x", "Tester", "<html><body><div class='aboutBox'>Tester</div></body></html>"))
        for bild in ("haupt", "w", "g", "s1a", "s1b", "s2a", "s2b"):
            c.add_item(_Seite(f"images/{bild}.png", "", PNG, "image/png", vorne=False))
    return datei
