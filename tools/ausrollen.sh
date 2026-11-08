#!/usr/bin/env bash
# Ausrollen auf den Server (etwa einen Pi, vom Entwicklungsrechner aus) nach deploy/ausrollen.toml. Ablauf und Prüfungen
# stehen für alle Apps gleich im Appkern (appkern.werkzeuge.ausrollen): nur gepushte Stände, Tests grün, Appkern gleich
# in Oberfläche und Backend, mit Ton der Tondienst in der Leitstelle, Zertifikat, bauen, Datenbank sichern nach der Regel
# der Sicherung, neu starten, Fassungen, HTTP/2 und Symbole, danach Docker aufräumen.
#
# Was dem Betreiber gehört, steht nie im Repo: Rechner, Ordner, Adresse, Namen und Leitstelle kommen aus der privaten
# Wahrheit des Hauses (Werkzeug handbuch, handbuch ziel), dazu aus dem privaten Teil privat/ (eigenes Repo, von Git
# ausgeschlossen): privat/ausrollen.toml ergänzt die Angaben (etwa das Konto der Kellerwolke in [zugaenge]),
# privat/umgebung.env setzt Werte der .env auf dem Server (etwa die feste Anmeldung über die Kellerwolke).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
[ -d privat ] || { echo "Abbruch: der private Teil privat/ fehlt (Angaben des Hauses zum Ausrollen)" >&2; exit 1; }
ergaenzung="$(mktemp)"
trap 'rm -f "$ergaenzung"' EXIT
handbuch ziel "$(pwd)" --toml > "$ergaenzung" || { echo "Abbruch: kein Ziel in der privaten Wahrheit (handbuch ziel)" >&2; exit 1; }
# die Abschnitte aus privat/ kommen nach den Werten des Handbuchs (TOML: Abschnitte stehen nach den einfachen Werten)
if [ -f privat/ausrollen.toml ]; then
  printf '\n' >> "$ergaenzung"
  cat privat/ausrollen.toml >> "$ergaenzung"
fi
# Werte der .env auf dem Gerät aus der privaten Wahrheit (handbuch ziel --env) und aus privat/umgebung.env: ihre
# Schlüssel werden gesetzt, alle anderen Zeilen der .env (etwa Schlüssel, die nur dort stehen) bleiben unberührt
umgebung="$(handbuch ziel "$(pwd)" --env)"
if [ -f privat/umgebung.env ]; then
  umgebung="$(printf '%s\n' "$umgebung"; grep -E '^[A-Z][A-Z0-9_]*=' privat/umgebung.env || true)"
fi
umgebung="$(printf '%s\n' "$umgebung" | grep -v '^$' || true)"
if [ -n "$umgebung" ]; then
  rechner="$(handbuch ziel "$(pwd)" rechner)"
  wurzel="$(handbuch ziel "$(pwd)" wurzel)"
  printf '%s\n' "$umgebung" | ssh "$rechner" "mkdir -p '$wurzel' && cd '$wurzel' && touch .env && chmod 600 .env && python3 -c '
import sys
neu = dict(z.split(\"=\", 1) for z in sys.stdin.read().splitlines() if \"=\" in z)
alt = [z for z in open(\".env\").read().splitlines() if z.split(\"=\", 1)[0] not in neu]
open(\".env\", \"w\").write(\"\".join(z + chr(10) for z in alt + [k + \"=\" + w for k, w in neu.items()]))
'"
  echo "Umgebung aus der privaten Wahrheit: $(printf '%s\n' "$umgebung" | cut -d= -f1 | paste -sd ' ' -)"
fi
backend/.venv/bin/python -m appkern.werkzeuge ausrollen --ergaenzung "$ergaenzung" "$@"
