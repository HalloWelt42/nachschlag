"""Darstellung eines Buchs (WIKI-45): aus dem Inhalt die Seiten als XHTML für das EPUB, ein Dokument für den Satz als
PDF und der Inhalt der Leseansicht in der App, dazu der Stil je Ziel aus der Gestaltung der Vorlage. Eine Quelle für alle
drei Ziele; sie unterscheiden sich nur in Fragen (EPUB und App zum Aufklappen, PDF mit Antworten hinten) und Seitenrand.

Reine Umformung: welche Adresse ein Bild im Buch hat, sagt der Aufrufer (`Bildname`; None lässt das Bild weg). Jeder Text
wird maskiert; Text wie im Buch kommt schon bereinigt aus `quelle.py`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from html import escape
from typing import Literal

from ..modell.alsbuch import (
    Absatz, Bild, Buchartikel, Buchinhalt, Buchkapitel, Gestaltung, Kasten, Randnotiz, Seitengroesse, Teil,
)
from .teile import JE_ART

Bildname = Callable[[Bild], str | None]
Ziel = Literal["epub", "pdf", "app"]

#: Farben der Gestaltung für Druck und Lesegerät (wie die Marken des Appkerns im hellen Bild)
FARBEN = {"petrol": "#08758b", "violett": "#8e2fe0", "honig": "#856700", "koralle": "#bc3e16", "stahl": "#4f6d93"}
#: Schriften im Satz (im Abbild über apt, siehe Dockerfile); das Lesegerät nimmt seine eigenen Schriften der Familie
SCHRIFTEN = {"serifen": '"Liberation Serif", "DejaVu Serif", serif', "ohne": '"Liberation Sans", "DejaVu Sans", sans-serif'}
UEBERSCHRIFT = '"Liberation Sans", "DejaVu Sans", sans-serif'
SEITE: dict[Seitengroesse, tuple[str, str, str]] = {    # Seitengröße, Ränder, Grundschrift
    "a5": ("A5", "16mm 14mm 18mm 16mm", "10pt"), "a4": ("A4", "22mm 22mm 24mm 24mm", "11pt"),
    "a4_zwei": ("A5", "16mm 14mm 18mm 16mm", "10pt")}
QUELLEN_TITEL = "Quellen und Lizenzen"


@dataclass
class Seite:
    """Eine Seite des EPUB: Datei, Titel und Inhalt des body."""
    datei: str
    titel: str
    inhalt: str


@dataclass
class Navpunkt:
    titel: str
    ziel: str
    unter: list[Navpunkt] = field(default_factory=list)


def e(text: str) -> str:
    return escape(text or "", quote=True)


def kapitel_id(nr: int) -> str:
    return f"k{nr}"


def artikel_id(kapitel: int, nr: int) -> str:
    return f"k{kapitel}-a{nr}"


def kapitel_titel(inhalt: Buchinhalt, k: Buchkapitel, nr: int) -> str:
    return k.titel if inhalt.vorlage.aufbau.gliederung == "abc" else f"{nr} {k.titel}"


# ----- Bausteine --------------------------------------------------------------------------------------------------------

def _bild(b: Bild, bildname: Bildname, klasse: str = "") -> str:
    src = bildname(b)
    if not src:
        return ""
    unterschrift = f"<figcaption>{e(b.unterschrift)}</figcaption>" if b.unterschrift else ""
    return f'<figure class="{klasse or "bild"}"><img src="{e(src)}" alt="{e(b.unterschrift[:120])}"/>{unterschrift}</figure>'


def _randnotiz(n: Randnotiz) -> str:
    zitat = f'<span class="zitat">"{e(n.zitat[:240])}"</span> ' if n.zitat else ""
    return f'<aside class="randnotiz"><b>Meine Notiz:</b> {zitat}{e(n.text)}</aside>'


def _kasten(k: Kasten, klasse: str) -> str:
    if not k.punkte:
        return ""
    punkte = "".join(f"<li>{e(p.text)}</li>" for p in k.punkte)
    return f'<div class="kasten {klasse}"><p class="kasten-kopf">{e(k.titel)}</p><ul>{punkte}</ul></div>'


def _absatz_inhalt(x: Absatz) -> tuple[str, bool]:
    """Inhalt eines Absatzes und ob er als Ganzes hervorgehoben wird."""
    if not x.html:
        return e(x.text), x.hervorgehoben
    html, ganz = x.html, x.hervorgehoben
    for zitat in x.markiert:
        stelle = e(" ".join(zitat.split())).replace("&quot;", '"').replace("&#x27;", "'")
        if stelle and stelle in html:
            html = html.replace(stelle, f"<mark>{stelle}</mark>", 1)
        else:
            ganz = True
    return html, ganz


def _absaetze(absaetze: list[Absatz], bildname: Bildname) -> str:
    teile: list[str] = []
    liste: tuple[int, bool] | None = None

    def liste_schliessen() -> None:
        nonlocal liste
        if liste:
            teile.append("</ol>" if liste[1] else "</ul>")
            liste = None

    for x in absaetze:
        if x.ueberschrift:
            liste_schliessen()
            teile.append(f"<h{x.ebene + 1}>{e(x.ueberschrift)}</h{x.ebene + 1}>")
        inhalt, ganz = _absatz_inhalt(x)
        klasse = ' class="hervorgehoben"' if ganz else ""
        if x.art == "punkt":
            if liste != (x.liste, x.geordnet):
                liste_schliessen()
                teile.append("<ol>" if x.geordnet else "<ul>")
                liste = (x.liste, x.geordnet)
            teile.append(f"<li{klasse}>{inhalt}</li>")
        else:
            liste_schliessen()
            if x.art == "tabelle":
                teile.append(f'<div class="tabelle">{x.html}</div>')
            elif x.art == "zitat":
                teile.append(f"<blockquote{klasse}><p>{inhalt}</p></blockquote>")
            elif x.art == "code":
                teile.append(f"<pre>{x.html}</pre>")
            elif inhalt:
                teile.append(f"<p{klasse}>{inhalt}</p>")
        nach = "".join(_randnotiz(n) for n in x.notizen) + "".join(_bild(b, bildname) for b in x.bilder)
        if nach:
            liste_schliessen()
            teile.append(nach)
    liste_schliessen()
    return "".join(teile)


def _fragen(k: Buchkapitel, ziel: Ziel, kapitelnr: int) -> str:
    if not k.fragen:
        return ""
    if ziel == "pdf":
        punkte = "".join(f"<li>{e(f.frage)}</li>" for f in k.fragen)
        hinweis = f'<p class="hinweis">Die Antworten stehen hinten im Heft unter <a href="#antworten-{kapitelnr}">Antworten</a>.</p>'
    else:
        punkte = "".join(f"<li><p>{e(f.frage)}</p><details><summary>Antwort</summary><p>{e(f.antwort)}</p></details></li>"
                         for f in k.fragen)
        hinweis = ""
    return f'<section class="fragen"><h3>Fragen zum Kapitel</h3><ol>{punkte}</ol>{hinweis}</section>'


def _einleitung(k: Buchkapitel) -> str:
    if not k.einleitung:
        return ""
    return f'<p class="einleitung">{e(" ".join(s.text for s in k.einleitung))}</p>'


def _teilstelle(innen: list[Teil]) -> int:
    """Stelle des ersten Teils je Artikel im Kapitel (davor: Kapitelanfang)."""
    return next((i for i, t in enumerate(innen) if JE_ART[t.art].ebene == "artikel"), len(innen))


def artikel_html(a: Buchartikel, kapitelnr: int, nr: int, innen: list[Teil], bildname: Bildname, g: Gestaltung) -> str:
    teile = [f'<article class="artikel" id="{artikel_id(kapitelnr, nr)}"><h2>{e(a.titel)}</h2>']
    if a.leitbild and g.bilder == "eins_gross":
        teile.append(_bild(a.leitbild, bildname, "leitbild"))
    if a.steckbrief:
        teile.append(f'<div class="steckbrief">{a.steckbrief}</div>')
    kasten_nr = 0
    for t in innen:
        if t.art == "blick" and a.blick:
            teile.append(_kasten(a.blick, "blick"))
        elif t.art in ("umgeformt", "originaltext"):
            teile.append(_absaetze(a.absaetze, bildname))
        elif t.art == "kasten":
            if kasten_nr < len(a.kaesten):
                teile.append(_kasten(a.kaesten[kasten_nr], "eigen"))
            kasten_nr += 1
        elif t.art == "notizen":
            teile.append("".join(_randnotiz(n) for n in a.notizen))
    teile.append("</article>")
    return "".join(teile)


def kapitel_html(inhalt: Buchinhalt, k: Buchkapitel, nr: int, ziel: Ziel, bildname: Bildname) -> str:
    innen = inhalt.vorlage.aufbau.innen
    stelle = _teilstelle(innen)

    def kapitelteile(teile: list[Teil]) -> str:
        aus = []
        for t in teile:
            if t.art == "kapiteleinleitung":
                aus.append(_einleitung(k))
            elif t.art == "fragen":
                aus.append(_fragen(k, ziel, nr))
        return "".join(aus)

    artikelteile = [t for t in innen if JE_ART[t.art].ebene == "artikel"]
    artikel = "".join(artikel_html(a, nr, i, artikelteile, bildname, inhalt.vorlage.gestaltung)
                      for i, a in enumerate(k.artikel, 1))
    return (f'<section class="kapitel" id="{kapitel_id(nr)}"><h1>{e(kapitel_titel(inhalt, k, nr))}</h1>'
            f"{kapitelteile(innen[:stelle])}{artikel}{kapitelteile(innen[stelle:])}</section>")


def titelseite_html(inhalt: Buchinhalt, bildname: Bildname) -> str:
    bild = _bild(inhalt.titelbild, bildname, "titelbild") if inhalt.titelbild else ""
    untertitel = f'<p class="untertitel">{e(inhalt.untertitel)}</p>' if inhalt.untertitel else ""
    beschreibung = f'<p class="beschreibung">{e(inhalt.beschreibung)}</p>' if inhalt.beschreibung else ""
    return f'<section class="titelseite">{bild}<h1 class="buchtitel">{e(inhalt.titel)}</h1>{untertitel}{beschreibung}</section>'


def navigation(inhalt: Buchinhalt, datei: Callable[[int], str]) -> list[Navpunkt]:
    """Kapitel mit ihren Artikeln; `datei(nr)` ist die Datei des Kapitels (im PDF leer: ein Dokument)."""
    return [Navpunkt(kapitel_titel(inhalt, k, nr), f"{datei(nr)}#{kapitel_id(nr)}",
                     [Navpunkt(a.titel, f"{datei(nr)}#{artikel_id(nr, i)}") for i, a in enumerate(k.artikel, 1)])
            for nr, k in enumerate(inhalt.kapitel, 1)]


def _navliste(punkte: list[Navpunkt]) -> str:
    if not punkte:
        return ""
    return "<ol>" + "".join(f'<li><a href="{e(p.ziel)}">{e(p.titel)}</a>{_navliste(p.unter)}</li>' for p in punkte) + "</ol>"


def inhalt_html(punkte: list[Navpunkt], epub: bool = False) -> str:
    art = ' epub:type="toc"' if epub else ""
    return f'<nav class="inhaltsverzeichnis"{art} id="inhalt"><h1>Inhalt</h1>{_navliste(punkte)}</nav>'


def glossar_html(inhalt: Buchinhalt) -> str:
    if not inhalt.glossar:
        return ""
    eintraege = "".join(f"<dt>{e(g.begriff)}</dt><dd>{e(g.erklaerung)}</dd>" for g in inhalt.glossar)
    return f'<section class="glossar" id="glossar"><h1>Glossar</h1><dl>{eintraege}</dl></section>'


def literatur_html(inhalt: Buchinhalt) -> str:
    if not inhalt.literatur:
        return ""
    teile, offen = ['<section class="literatur" id="literatur"><h1>Literatur</h1>'], False
    for zeile in inhalt.literatur:
        if zeile.startswith("## "):
            if offen:
                teile.append("</ul>")
                offen = False
            teile.append(f"<h3>{e(zeile[3:].strip())}</h3>")
        elif zeile.lstrip().startswith("- "):
            if not offen:
                teile.append("<ul>")
                offen = True
            klasse = ' class="beleg"' if zeile.startswith("  ") else ""
            teile.append(f"<li{klasse}>{e(zeile.lstrip()[2:].strip())}</li>")
    if offen:
        teile.append("</ul>")
    teile.append("</section>")
    return "".join(teile)


def antworten_html(inhalt: Buchinhalt) -> str:
    """Die Antworten aller Fragen (PDF: hinten im Heft)."""
    teile = []
    for nr, k in enumerate(inhalt.kapitel, 1):
        if k.fragen:
            punkte = "".join(f"<li><b>{e(f.frage)}</b> {e(f.antwort)}</li>" for f in k.fragen)
            teile.append(f'<h3 id="antworten-{nr}">{e(kapitel_titel(inhalt, k, nr))}</h3><ol>{punkte}</ol>')
    return f'<section class="antworten" id="antworten"><h1>Antworten</h1>{"".join(teile)}</section>' if teile else ""


def quellen_html(inhalt: Buchinhalt, bildname: Bildname) -> str:
    """Quellen und Lizenzen (immer am Ende): je Artikel Buch, Fassung, Adresse, Urheber und Lizenz, dazu die Bilder mit
    bekanntem Urheber."""
    umgeformt = any(t.art == "umgeformt" for t in inhalt.vorlage.aufbau.innen)
    vorspann = ("Die Texte stammen aus diesen Artikeln; ihre Urheber und Lizenzen gelten auch hier. "
                + (f"Sie wurden nach der Vorlage {inhalt.vorlage.titel} von einem Sprachmodell umgeformt, nur aus dem, was in "
                   "den Artikeln steht, und danach gegen das Original geprüft." if umgeformt else "Sie stehen hier wie im Buch."))
    zeilen = []
    for k in inhalt.kapitel:
        for a in k.artikel:
            q = a.quelle
            teile = [f"<b>{e(a.titel)}</b>.", f"{e(q.buch)}" + (f", Fassung {e(q.fassung)}" if q.fassung else "") + "."]
            if q.adresse:
                teile.append(f'<a href="{e(q.adresse)}">{e(q.adresse)}</a>.')
            teile.append(f"Urheber: {e(q.urheber)}. Lizenz: {e(q.lizenz)}.")
            zeilen.append(f"<li>{' '.join(teile)}</li>")
    bilder = [b for b in alle_bilder(inhalt) if b.urheber or b.lizenz]
    bildzeilen = "".join(f"<li>{e(b.unterschrift[:80] or 'Bild')}: {e(b.urheber or 'unbekannt')}"
                         + (f", {e(b.lizenz)}" if b.lizenz else "") + "</li>" for b in bilder if bildname(b))
    bildteil = f"<h3>Bilder</h3><ul>{bildzeilen}</ul>" if bildzeilen else ""
    return (f'<section class="quellen" id="quellen"><h1>{QUELLEN_TITEL}</h1><p>{e(vorspann)}</p><ol>{"".join(zeilen)}</ol>'
            f"{bildteil}</section>")


def alle_bilder(inhalt: Buchinhalt) -> list[Bild]:
    """Jedes Bild des Buchs einmal (Titelbild, Leitbilder, Bilder im Text), in der Reihenfolge des Buchs."""
    gesehen: dict[str, Bild] = {}
    reihe = [inhalt.titelbild] if inhalt.titelbild else []
    for k in inhalt.kapitel:
        for a in k.artikel:
            reihe += [a.leitbild] if a.leitbild else []
            reihe += [b for x in a.absaetze for b in x.bilder]
    for b in reihe:
        gesehen.setdefault(b.adresse, b)
    return list(gesehen.values())


def _buchteil(t: Teil, inhalt: Buchinhalt) -> str:
    return glossar_html(inhalt) if t.art == "glossar" else literatur_html(inhalt) if t.art == "literatur" else ""


# ----- Ziele ------------------------------------------------------------------------------------------------------------

def epub_seiten(inhalt: Buchinhalt, bildname: Bildname) -> tuple[list[Seite], list[Navpunkt], bool]:
    """Seiten des EPUB, die Navigation und ob das Inhaltsverzeichnis als Seite im Buch steht."""
    aufbau = inhalt.vorlage.aufbau
    datei = lambda nr: f"kapitel-{nr:02d}.xhtml"  # noqa: E731
    seiten: list[Seite] = []
    for t in aufbau.vorn:
        if t.art == "titelseite":
            seiten.append(Seite("titel.xhtml", inhalt.titel, titelseite_html(inhalt, bildname)))
        elif (html := _buchteil(t, inhalt)):
            seiten.append(Seite(f"{t.art}.xhtml", JE_ART[t.art].titel, html))
    vor_kapiteln = len(seiten)
    for nr, k in enumerate(inhalt.kapitel, 1):
        seiten.append(Seite(datei(nr), kapitel_titel(inhalt, k, nr), kapitel_html(inhalt, k, nr, "epub", bildname)))
    for t in aufbau.hinten:
        if (html := _buchteil(t, inhalt)):
            seiten.append(Seite(f"{t.art}.xhtml", JE_ART[t.art].titel, html))
    seiten.append(Seite("quellen.xhtml", QUELLEN_TITEL, quellen_html(inhalt, bildname)))
    nav = navigation(inhalt, datei)
    nav += [Navpunkt(s.titel, s.datei) for s in seiten[len(inhalt.kapitel) + vor_kapiteln:]]
    nav[:0] = [Navpunkt(s.titel, s.datei) for s in seiten[:vor_kapiteln] if s.datei != "titel.xhtml"]
    return seiten, nav, any(t.art == "inhalt" for t in aufbau.vorn)


def _koerper(inhalt: Buchinhalt, bildname: Bildname, ziel: Ziel) -> str:
    aufbau = inhalt.vorlage.aufbau
    teile = []
    for t in aufbau.vorn:
        if t.art == "titelseite":
            teile.append(titelseite_html(inhalt, bildname))
        elif t.art == "inhalt" and ziel == "pdf":
            nav = navigation(inhalt, lambda nr: "")
            nav += [Navpunkt(JE_ART[x.art].titel, f"#{x.art}") for x in aufbau.hinten if _buchteil(x, inhalt)]
            if any(k.fragen for k in inhalt.kapitel):
                nav.append(Navpunkt("Antworten", "#antworten"))
            nav.append(Navpunkt(QUELLEN_TITEL, "#quellen"))
            teile.append(inhalt_html(nav))
        else:
            teile.append(_buchteil(t, inhalt))
    teile += [kapitel_html(inhalt, k, nr, ziel, bildname) for nr, k in enumerate(inhalt.kapitel, 1)]
    teile += [_buchteil(t, inhalt) for t in aufbau.hinten]
    if ziel == "pdf":
        teile.append(antworten_html(inhalt))
    teile.append(quellen_html(inhalt, bildname))
    return "".join(teile)


def pdf_dokument(inhalt: Buchinhalt, bildname: Bildname, seiten: Seitengroesse) -> str:
    """Ein HTML-Dokument für den Satz als PDF (Stil eingebettet)."""
    return dokument(inhalt.titel, _koerper(inhalt, bildname, "pdf"), stil=stil(inhalt.vorlage.gestaltung, "pdf", seiten))


def lesen_html(inhalt: Buchinhalt, bildname: Bildname) -> str:
    """Der Inhalt für die Leseansicht in der App (ohne Stil: den gibt die App)."""
    return f'<div class="buch-text farbe-{inhalt.vorlage.gestaltung.farbe} schrift-{inhalt.vorlage.gestaltung.schrift}">' \
           f"{_koerper(inhalt, bildname, 'app')}</div>"


def dokument(titel: str, koerper: str, *, stil: str = "", stil_datei: str = "", epub: bool = False) -> str:
    """Ein vollständiges XHTML-Dokument."""
    ns = ' xmlns:epub="http://www.idpf.org/2007/ops"' if epub else ""
    kopf = f'<link rel="stylesheet" type="text/css" href="{e(stil_datei)}"/>' if stil_datei else f"<style>{stil}</style>" if stil else ""
    return ('<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
            f'<html xmlns="http://www.w3.org/1999/xhtml"{ns} lang="de" xml:lang="de"><head><meta charset="utf-8"/>'
            f"<title>{e(titel)}</title>{kopf}</head><body>{koerper}</body></html>")


def hell(farbe: str, anteil: float) -> str:
    """Eine Farbe aufgehellt (Anteil der Farbe auf Weiß), als feste Angabe: Lesegeräte und der Satz kennen keine
    Farbmischung."""
    rgb = [int(farbe[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(255 - (255 - c) * anteil):02x}" for c in rgb)


def stil(g: Gestaltung, ziel: Ziel, seiten: Seitengroesse = "a5") -> str:
    """Stil des Buchs aus der Gestaltung: Schrift, Farbe der Kästen und Überschriften; im PDF dazu Seite, Seitenzahlen,
    Kopfzeile mit dem Kapitel und Seitenzahlen im Inhaltsverzeichnis."""
    farbe = FARBEN[g.farbe]
    grund = f"""
html {{ hyphens: auto; }}
body {{ font-family: {SCHRIFTEN[g.schrift]}; line-height: 1.5; color: #1d1d1d; margin: 0; }}
h1, h2, h3, h4, h5, .kasten-kopf, .buchtitel, .untertitel, nav {{ font-family: {UEBERSCHRIFT}; }}
h1, h2, h3, h4, h5 {{ color: {farbe}; line-height: 1.2; hyphens: manual; }}
h1 {{ font-size: 1.7em; margin: 0 0 .8em; }}
h2 {{ font-size: 1.3em; margin: 1.6em 0 .6em; }}
h3 {{ font-size: 1.1em; margin: 1.2em 0 .4em; }}
h4, h5 {{ font-size: 1em; margin: 1em 0 .3em; }}
p {{ margin: 0 0 .6em; text-align: justify; }}
.kasten {{ background: {hell(farbe, 0.1)}; padding: .6em .9em; border-radius: 4px; margin: .8em 0; }}
.kasten-kopf {{ font-weight: bold; color: {farbe}; margin: 0 0 .3em; text-align: left; }}
.kasten ul {{ margin: 0; padding-left: 1.2em; }}
.randnotiz {{ display: block; background: #fbf3d5; padding: .5em .8em; margin: .6em 0; font-size: .9em; border-radius: 3px; }}
.randnotiz .zitat {{ font-style: italic; }}
.hervorgehoben, mark {{ background: #fff0a6; }}
.einleitung {{ font-size: 1.05em; font-style: italic; }}
figure {{ margin: 1em 0; text-align: center; }}
figure img {{ max-width: 100%; max-height: 14em; }}
figure.leitbild img {{ max-height: 18em; }}
figcaption {{ font-size: .82em; color: #555; margin-top: .3em; }}
.tabelle {{ margin: .8em 0; }}
table {{ border-collapse: collapse; font-size: .88em; }}
td, th {{ border: 1px solid #c8c8c8; padding: .2em .4em; vertical-align: top; text-align: left; }}
.steckbrief {{ background: #f3f4f6; padding: .5em .8em; margin: .8em 0; font-size: .88em; border-radius: 4px; }}
.steckbrief dt {{ font-weight: bold; }}
.steckbrief dd {{ margin: 0 0 .3em; }}
blockquote {{ margin: .8em 1.2em; font-style: italic; }}
pre {{ font-size: .82em; white-space: pre-wrap; background: #f3f4f6; padding: .5em; }}
.fragen ol {{ padding-left: 1.4em; }}
.fragen li {{ margin-bottom: .5em; }}
.fragen summary {{ color: {farbe}; cursor: pointer; }}
.titelseite {{ text-align: center; }}
.titelseite .titelbild img {{ max-height: 22em; }}
.buchtitel {{ color: {farbe}; font-size: 2.2em; margin: .6em 0 .2em; }}
.untertitel {{ font-size: 1.2em; color: #444; margin: 0 0 1em; text-align: center; }}
.beschreibung {{ text-align: center; color: #555; }}
nav ol {{ list-style: none; padding-left: 0; }}
nav ol ol {{ padding-left: 1.2em; font-size: .92em; }}
nav a {{ color: inherit; text-decoration: none; }}
.glossar dt {{ font-weight: bold; color: {farbe}; }}
.glossar dd {{ margin: 0 0 .5em; }}
.literatur li.beleg {{ font-size: .9em; color: #555; list-style: circle; margin-left: 1.2em; }}
.quellen {{ font-size: .88em; }}
.quellen a {{ color: inherit; word-break: break-all; }}
.hinweis {{ font-size: .88em; color: #555; }}
"""
    if ziel != "pdf":
        return grund
    groesse, raender, schrift = SEITE[seiten]
    return grund + f"""
@page {{ size: {groesse}; margin: {raender};
  @bottom-center {{ content: counter(page); font-family: {UEBERSCHRIFT}; font-size: 8pt; color: #666; }}
  @top-center {{ content: string(kapitel); font-family: {UEBERSCHRIFT}; font-size: 7.5pt; color: #888; }} }}
@page titel {{ @bottom-center {{ content: none; }} @top-center {{ content: none; }} }}
html {{ font-size: {schrift}; }}
.titelseite {{ page: titel; break-after: page; padding-top: 2em; }}
nav.inhaltsverzeichnis {{ break-after: page; }}
nav.inhaltsverzeichnis a::after {{ content: leader('.') target-counter(attr(href), page); }}
section.kapitel, section.glossar, section.literatur, section.antworten, section.quellen {{ break-before: page; }}
section > h1 {{ string-set: kapitel content(); }}
h1, h2, h3 {{ break-after: avoid; }}
figure, .kasten, .randnotiz, tr {{ break-inside: avoid; }}
p {{ orphans: 2; widows: 2; }}
"""
