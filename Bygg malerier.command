#!/bin/bash
# Dobbeltklikk i Finder for å bygge datapack + resource pack.
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  echo "Første gang: setter opp Python ..."
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt || { echo "Fikk ikke installert Pillow."; read -r; exit 1; }
fi
.venv/bin/python build.py
open dist
echo; read -r -p "Trykk Enter for å lukke."
