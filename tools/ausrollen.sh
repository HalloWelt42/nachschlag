#!/usr/bin/env bash
# Ausrollen auf den Pi (vom Mac aus) nach deploy/ausrollen.toml. Ablauf und Prüfungen stehen für alle Apps gleich im
# Appkern (appkern.werkzeuge.ausrollen): nur gepushte Stände, Tests grün, Appkern gleich in Oberfläche und Backend,
# mit Ton der Tondienst in der Leitstelle, Zertifikat, bauen, Datenbank sichern nach der Regel der Sicherung, neu
# starten, Fassungen, HTTP/2 und Symbole, danach Docker aufräumen. Rechner, Ordner, Adresse, Namen und Leitstelle kommen aus der privaten Wahrheit (handbuch ziel).
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
ergaenzung="$(mktemp)"
trap 'rm -f "$ergaenzung"' EXIT
handbuch ziel "$(pwd)" --toml > "$ergaenzung" || { echo "Abbruch: kein Ziel in der privaten Wahrheit (handbuch ziel)" >&2; exit 1; }
# Werte der .env auf dem Gerät aus der privaten Wahrheit (handbuch ziel --env): ihre Schlüssel werden gesetzt, alle
# anderen Zeilen der .env (etwa Schlüssel, die nur dort stehen) bleiben unberührt
umgebung="$(handbuch ziel "$(pwd)" --env)"
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
