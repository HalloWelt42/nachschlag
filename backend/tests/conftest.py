"""Gemeinsam für alle Proben: Nachschlag beginnt frisch ohne Anmeldung (WIKI-11). Die meisten Proben laufen wie der
Betrieb mit Anmeldung über die nachgestellte Kellerwolke; Proben mit der Marke `ohne_anmeldung` prüfen die Vorgabe
eines frischen Starts."""

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "ohne_anmeldung: Nachschlag wie frisch gestartet, ohne Anmeldung")


@pytest.fixture(autouse=True)
def betriebsart(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    if request.node.get_closest_marker("ohne_anmeldung") is None:
        monkeypatch.setenv("NACHSCHLAG_ANMELDUNG", "kellerwolke")
    else:
        monkeypatch.delenv("NACHSCHLAG_ANMELDUNG", raising=False)
