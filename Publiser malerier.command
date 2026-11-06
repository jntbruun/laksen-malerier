#!/bin/bash
# Dobbeltklikk: bygger, pusher og legger alt inn på serveren.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Første gang: setter opp Python ..."
  python3 -m venv .venv && .venv/bin/pip install -q pillow certifi || { echo "Fikk ikke installert Pillow."; read -r; exit 1; }
fi
.venv/bin/python publiser.py
echo; read -r -p "Trykk Enter for å lukke."
