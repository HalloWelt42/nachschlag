# Nachschlag

Nachschlag liest Bücher im ZIM-Format aus einem Ordner: Wikis und Lexika, Handbücher und Dokumentationen, Sammlungen
von Fragen und Antworten, Anleitungen und Kurse. Alles offline, durchsuchbar und angenehm zu lesen, im Browser am
Rechner und am Telefon. Dazu eigene Merkzettel, Notizen, Themen und ein Verlauf.

Nachschlag läuft allein: ein Dienst und ein Ordner mit Büchern genügen. Weitere Dienste (Konten und Ablage, KI,
Bedeutungssuche, Vorlesen) sind Anbindungen, die man zuschaltet; fehlt eine, blendet die Oberfläche aus, was sie
braucht, statt Fehler zu zeigen. Gebaut auf dem [Appkern](https://github.com/HalloWelt42/appkern).

## Was es kann

- **Lesen** je nach Art des Buchs: Lexikonartikel im eigenen Lesedesign mit Steckbrief, Inhalt und Lesestand,
  Dokumentationen mit Fassungsfilter und eigenen Beispielen, Fragen und Antworten mit Stimmen und Schlagwörtern,
  Anleitungen mit Werkzeugen und Schritten, Kurse mit Übungen; jedes andere Buch in seiner Originalansicht. Dazu
  Medien, Kategorien, Register, Stöbern und Rückverweise.
- **Suche** über den Index der Bücher (Volltext und Titel), im geöffneten Buch zuerst, mit Vorschlägen beim Tippen,
  Tippfehlerkorrektur und Treffern direkt an der Stelle; wahlweise übersetzt und nach Bedeutung (Anbindungen).
- **Bibliothek**: jede ZIM-Datei im Ordner ist ein Buch, neue erscheinen von selbst. Der Bücherlader sieht das
  öffentliche Verzeichnis der Bücher durch, meldet Neues, lädt abonnierte Bücher mit Prüfsumme und schaltet zwischen
  Fassungen um.
- **Meins**: Merkzettel, Notizen an Stellen oder ganzen Artikeln (mit Bildern, auf Wunsch als Markdown abgelegt),
  Themen mit Bereichen und Literaturliste, Verlauf von Gelesenem und Gesuchtem nach Tagen.
- **Als Buch**: ein Thema wird ein Buch als EPUB und PDF nach einer Vorlage; ohne KI aus den Artikeln, mit Leitstelle
  auch umgeformt und gegen das Original geprüft ([docs/ALS_BUCH.md](docs/ALS_BUCH.md)).
- **Schnittstelle**: alle Wege unter `/api/v1`, beschrieben in der App (Bereich Schnittstelle), dazu MCP für
  KI-Werkzeuge (`POST /api/v1/mcp`).

## Voraussetzungen

- Docker mit Compose, auf amd64 oder arm64 (auch kleine Rechner im eigenen Netz).
- Bücher im ZIM-Format in einem Ordner. Viele gibt es frei zum Herunterladen; der Bücherlader in der App kann sie aus
  dem öffentlichen Verzeichnis laden. Die Inhalte stehen unter ihren eigenen Lizenzen und gehören nicht zu diesem Repo.
- Platz für die Bücher (von wenigen MB bis weit über 100 GB je Buch) und etwas für die Daten der App.

## Start

```bash
git clone https://github.com/HalloWelt42/nachschlag.git
cd nachschlag
BUECHER=/pfad/zu/den/zim-dateien docker compose up -d --build
```

Dann im Browser `http://<rechner>:8711` öffnen. Ohne `BUECHER` nimmt Nachschlag den Ordner `buecher` neben
`compose.yml`; einen anderen Port wählt `PORT=8800`. Die Originalseiten der Bücher laufen auf einem eigenen Port
(`ORIGINAL_PORT`, Vorgabe 8712), damit ihre Skripte nicht an die App kommen; er muss ebenso erreichbar sein. Daten und
Einstellungen liegen in `daten/`, Sicherungen der Datenbank in `sicherungen/` (wöchentlich, höchstens drei). Alles
Weitere steht in der App unter Einstellungen.

Neue Fassung holen: `git pull && docker compose up -d --build`.

## Ohne Anmeldung: nur im eigenen Netz

> **Achtung:** Nachschlag beginnt ohne Anmeldung. Wer die App erreicht, darf alles: lesen, Notizen schreiben und löschen,
> Bücher laden, Einstellungen und Schlüssel der Anbindungen ändern. Betreibe sie nur im eigenen Netz und stelle sie nie
> offen ins Internet (keine Portfreigabe am Router, kein öffentlicher Vorschaltdienst). Für den Zugriff von unterwegs
> eignet sich ein privates Netz zwischen deinen Geräten.

Ohne Anmeldung gibt es einen Nutzer: Merkzettel, Notizen, Themen und Verlauf gehören ihm, auf allen Geräten gemeinsam.
Mit Anmeldung meldet sich jeder mit seinem Konto der Kellerwolke an, und alles Persönliche ist je Konto getrennt: erst
die Kellerwolke unter Einstellungen, Verbindungen eintragen (Adresse und App-Schlüssel, auch per QR-Code), dann unter
Einstellungen, Zugang auf "Mit dem Konto der Kellerwolke" umstellen. Fest beim Start geht es mit
`NACHSCHLAG_FEST_ANMELDUNG=kellerwolke` in der Umgebung. Beim Umstellen bleiben die Daten bei ihrem bisherigen Konto.

## Anbindungen (wahlweise)

Jede Anbindung ist ein eigener Dienst und wird nur über seine Schnittstelle im Netz angesprochen. Eingetragen wird sie
in den Einstellungen; ohne sie fehlt nur, was sie bringt.

| Anbindung | bringt | Einstellungen | ohne sie |
|---|---|---|---|
| [Kellerwolke](https://github.com/HalloWelt42/kellerwolke) | Konten (Anmeldung), Ablage der Dateien | Verbindungen, Zugang | ein Nutzer; Notizen als Markdown, Bilder an Notizen, Bücher und Vorlagen im Datenordner (`daten/ablage`) |
| [Leitstelle](https://github.com/HalloWelt42/leitstelle) | KI: Übersetzen, Themen ordnen, Als Buch umformen, Spracheingabe, Vorlesen | Verbindungen, Suche, Vorlesen | ausgeblendet; Bücher nur mit Vorlagen ohne KI |
| Fundus | Bedeutungssuche neben dem Index | Suche | Suche nur im Index |
| Vertonung | eigene Stimmen fürs Vorlesen | Vorlesen | Stimmen des Sprechdienstes |
| Bildholer | große Bilder der Wikis mit Urheber und Lizenz (`compose.pi.yml`) | Bilder | Bilder aus den Büchern |
| Index-Dienst | eigene Indizes und Kategorien, auf einem eigenen Rechner gebaut ([docs/SUCHE.md](docs/SUCHE.md)) | Suche | Index der Datei |
| Codeschmiede | Beispiele aus Handbüchern ausprobieren ([docs/AUSPROBIEREN.md](docs/AUSPROBIEREN.md)) | Verbindungen | kein Ausprobieren |

Mit Vorschaltdienst (HTTPS mit eigener Zertifizierungsstelle, HTTP/2) und Bildholer läuft Nachschlag nach
`compose.pi.yml`; Werte, die nur dem Betreiber gehören, stehen dort in einer `.env` neben der Datei (etwa
`BUECHER_ORDNER`). `tools/ausrollen.sh` rollt so auf einen Server im eigenen Netz aus; es braucht einen privaten Teil
`privat/` mit den Angaben des Betreibers (nicht in diesem Repo).

## Entwickeln

```bash
./einrichten.sh
```

Legt die Python-Umgebung an, holt die Pakete der Oberfläche, baut sie und richtet die Git-Haken ein.

| Teil | Befehl |
|---|---|
| Backend | `cd backend && .venv/bin/uvicorn app.main:app --port 8711 --reload` (Originalseiten nur hinter einem Vorschaltdienst, der auch Port 8712 an die App reicht) |
| Probebetrieb | `cd backend && .venv/bin/uvicorn probebetrieb:app --port 8711 --reload` (nachgestellte Kellerwolke, Daten in `daten-probe/`, Originalseiten auf 8712 im selben Prozess) |
| Oberfläche | `cd frontend && npm run dev` (Port 9711, leitet `/api` ans Backend) |
| Tests | `cd backend && .venv/bin/python -m pytest` |
| Symbole | `python3 tools/symbole.py` nach einer Änderung an `frontend/public/symbol.svg` |
| Fassung | `tools/version.sh minor` für eine neue Fähigkeit; jeder Commit zählt sonst selbst hoch |
| Appkern | `tools/appkern.sh` hebt Oberfläche und Backend auf denselben neuesten Commit |
| Ausrollen | `tools/ausrollen.sh` (Angaben in `deploy/ausrollen.toml` und im privaten Teil) |

Der Satz als PDF braucht Pango (im Abbild über apt; am Mac aus Homebrew mit
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`). Der Verbundtest (`backend/tests/test_verbund.py`) spricht mit einer
echten Kellerwolke und braucht `backend/.env.test` (nicht im Repo) mit `KELLERWOLKE_ADRESSE`, `KELLERWOLKE_SCHLUESSEL`,
`KELLERWOLKE_KENNUNG`, `KELLERWOLKE_PASSWORT`: ein eigener Zugang nur für Tests; ohne die Datei wird er übersprungen.

## Prüfungen

Vor jedem Commit (Hook in `tools/git-hooks`, eingerichtet von `einrichten.sh`): Fassung hochzählen, nur gerade
Zeichen, Stil ohne `!important`, ohne einseitige Streifen und ohne Regeln auf Klassen der Schale, nur Marken der
Gestaltung. Beim Ausrollen: Tests, gleicher Appkern in Oberfläche und Backend, Fassungen, HTTP/2, Symbole. Von Hand vor
dem Vorzeigen: [docs/ABNAHME.md](docs/ABNAHME.md); die Ansichtsprüfung `tools/ansicht.sh <adresse> --rahmen`.

## Aufbau

| Ort | Inhalt |
|---|---|
| `backend/app/main.py` | baut die App auf dem Gerüst des Appkerns und verdrahtet die Dienste |
| `backend/app/einstellungen.py` | eigene Einstellungen (dazu kommen Kellerwolke, Leitstelle, Anmeldung, Sicherung aus dem Appkern) |
| `backend/app/api.py` | Bücher, Artikel und Suche; jeder weitere Bereich hat seine eigene `api.py` |
| `backend/bildholer/` | der Bildholer, ein eigenes Programm im eigenen Container |
| `frontend/src/App.svelte` | Bereiche der App in der gemeinsamen Schale |
| `frontend/src/seiten/`, `frontend/src/teile/` | Seiten der Bereiche und ihre Teile |
| `mockups/` | die freigegebenen Entwürfe der Oberfläche (sie erwarten den Appkern als Nachbarordner) |
| `docs/` | Aufbau ([AUFBAU.md](docs/AUFBAU.md)), Suche, Bücherlader, Bildholer, Als Buch, Ausprobieren, Abnahme |

## Unterstützen

Nachschlag ist ein privates Hobby-Projekt. Kein Tracking, keine Werbung, keine Kompromisse.

Wenn dir das Projekt gefällt, kannst du ihm einen Stern geben - oder direkt hier:

[![Ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/HalloWelt42)

**Crypto:**

| Coin | Adresse |
|------|---------|
| BTC | `bc1qnd599khdkv3v3npmj9ufxzf6h4fzanny2acwqr` |
| DOGE | `DL7tuiYCqm3xQjMDXChdxeQxqUGMACn1ZV` |
| ETH | `0x8A28fc47bFFFA03C8f685fa0836E2dBe1CA14F27` |

## Lizenz

Nicht-kommerzielle Lizenz (`LicenseRef-Nachschlag-NC-1.0`), siehe [LICENSE](LICENSE). Die Inhalte der ZIM-Dateien
stehen unter ihren eigenen Lizenzen und sind nicht Teil dieses Repos.

Copyright (c) 2026 HalloWelt42
