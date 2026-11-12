"""WIKI-97: gespeicherte Bildadressen zeigen beim Lesen auf die heutige Fassung des Buchs, sonst kein Bild (nie 404)."""

from app.medienweg import bild_heute


def test_bild_auf_heutige_fassung():
    alt = "/api/v1/inhalt/medien/wikipedia_de_all_maxi_2026-01/_assets_/a/Vulpes_(x).jpg"
    assert bild_heute(alt, "wikipedia_de_all_maxi_2026-10") == "/api/v1/inhalt/medien/wikipedia_de_all_maxi_2026-10/_assets_/a/Vulpes_(x).jpg"
    assert bild_heute(alt, "") == ""                                   # Buch nicht mehr da: kein Bild statt 404
    assert bild_heute("https://example.org/x.png", "") == "https://example.org/x.png"   # fremde Adressen bleiben
    assert bild_heute("", "buch") == ""
