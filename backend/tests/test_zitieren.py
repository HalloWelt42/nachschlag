"""Zitierformen (WIKI-31): einfach, APA, DIN ISO 690 und BibTeX aus denselben Angaben; ohne Autor steht der Titel
vorn, Frage und Antwort nennt, wer fragte und wann; BibTeX schützt seine Sonderzeichen."""

from datetime import date

from app.zitieren import Zitierangaben, schluessel, zitate

HEUTE = date(2026, 11, 1)
LEXIKON = Zitierangaben(titel="Rotfuchs", quelle="Wikipedia", stand="2026-01-15", url="https://de.wikipedia.org/wiki/Rotfuchs")
FRAGE = Zitierangaben(titel="How do I exit Vim?", quelle="Vi and Vim Q&A", stand="2026-10-01",
                      url="https://vi.stackexchange.com/questions/84", autor="Martin Tournoij", datum="2015-02-03")


def test_lexikon_ohne_autor():
    z = zitate(LEXIKON, HEUTE)
    assert z.einfach == "Rotfuchs. In: Wikipedia. https://de.wikipedia.org/wiki/Rotfuchs (abgerufen am 01.11.2026)"
    assert z.apa == ("Rotfuchs. (2026, 15. Januar). In Wikipedia. Abgerufen am 1. November 2026, von "
                     "https://de.wikipedia.org/wiki/Rotfuchs")
    assert z.din == ("Rotfuchs. In: Wikipedia. Stand: 15.01.2026. URL: https://de.wikipedia.org/wiki/Rotfuchs "
                     "(abgerufen am 01.11.2026)")
    assert z.bibtex.startswith("@misc{rotfuchs2026,\n  title = {{Rotfuchs}},\n  howpublished = {Wikipedia},")


def test_frage_mit_autor_und_datum():
    z = zitate(FRAGE, HEUTE)
    assert z.einfach.startswith("Martin Tournoij: How do I exit Vim? (03.02.2015). In: Vi and Vim Q&A.")
    assert z.apa.startswith("Martin Tournoij. (2015, 3. Februar). How do I exit Vim? [Forumsbeitrag]. In Vi and Vim Q&A.")
    assert "03.02.2015. Stand: 01.10.2026." in z.din
    assert "  author = {{Martin Tournoij}},\n  howpublished = {Vi and Vim Q\\&A},\n  year = {2015}," in z.bibtex


def test_bibtex_schuetzt_sonderzeichen_und_schluessel_in_ascii():
    a = Zitierangaben(titel="Über array_map & 100% {mehr}", quelle="PHP", stand="2026-08-18")
    assert "title = {{Über array\\_map \\& 100\\% \\{mehr\\}}}" in zitate(a, HEUTE).bibtex
    assert schluessel(a) == "uber2026"
