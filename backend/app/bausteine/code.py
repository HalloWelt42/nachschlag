"""Code einfärben wie im Editor der Codeschmiede (Entwurf doku-php.html): Schlüsselwörter, Funktionen, Variablen,
Zeichenketten, Zahlen, Kommentare und PHP-Marken als Spans mit eigenen Klassen (c-kw, c-fn, c-var, c-str, c-num,
c-kom, c-tag); die Farben setzt das Lesedesign. Eine Sprache, die hier keine Regeln hat, bleibt ungefärbt."""

from __future__ import annotations

import re

from lxml import html as lhtml
from lxml.etree import SubElement

PHP_SCHLUESSELWOERTER = frozenset("""
abstract and array as bool break callable case catch class clone const continue declare default do echo else elseif
empty enddeclare endfor endforeach endif endswitch endwhile enum extends false final finally float fn for foreach function
global goto if implements include include_once instanceof insteadof int interface isset iterable list match mixed
namespace never new null object or parent print private protected public readonly require require_once return self
static string switch throw trait true try unset use var void while xor yield
""".split())

#: Bausteine eines PHP-Quelltexts in der Reihenfolge, in der sie zu erkennen sind
PHP = re.compile(r"""
    (?P<tag><\?php|<\?=|\?>)
  | (?P<kom>/\*.*?\*/|//[^\n]*|\#(?!\[)[^\n]*)
  | (?P<str>'(?:\\.|[^'\\])*'|"(?:\\.|[^"\\])*")
  | (?P<var>\$[A-Za-z_]\w*)
  | (?P<num>\b\d[\d_]*(?:\.\d+)?(?:[eE][+-]?\d+)?\b|\b0[xX][0-9a-fA-F]+\b)
  | (?P<wort>\b[A-Za-z_]\w*\b)(?P<aufruf>\s*\()?
""", re.S | re.X)

KLASSE = {"tag": "c-tag", "kom": "c-kom", "str": "c-str", "var": "c-var", "num": "c-num"}


def einfaerben(code: str, sprache: str):
    """Ein `<pre>` mit dem eingefärbten Code (Text maskiert über den Elementbaum, nie als Zeichenkette gebaut)."""
    pre = lhtml.Element("pre")
    if sprache != "php":
        pre.text = code
        return pre
    letztes = None
    rest = 0

    def text(t: str) -> None:
        if not t:
            return
        if letztes is None:
            pre.text = (pre.text or "") + t
        else:
            letztes.tail = (letztes.tail or "") + t

    for m in PHP.finditer(code):
        art = m.lastgroup if m.lastgroup != "aufruf" else "wort"
        klasse = KLASSE.get(art)
        wort = m.group("wort")
        if wort is not None:
            if wort.lower() in PHP_SCHLUESSELWOERTER:
                klasse = "c-kw"
            elif m.group("aufruf"):
                klasse = "c-fn"
            else:
                klasse = None
        if klasse is None:
            continue
        stueck = wort if wort is not None else m.group(0)
        text(code[rest:m.start()])
        span = SubElement(pre, "span")
        span.set("class", klasse)
        span.text = stueck
        letztes = span
        rest = m.start() + len(stueck)
    text(code[rest:])
    return pre
