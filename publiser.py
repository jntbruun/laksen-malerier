"""Bygger, pusher til GitHub, laster opp datapacken, oppdaterer server.properties og restarter.

Krever en API-nøkkel fra panelet (Account -> API Credentials) i fila .panel-nokkel.
Kjør:  .venv/bin/python publiser.py   (eller dobbeltklikk "Publiser malerier.command")
"""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

import build

PANEL = "https://panel.spillhosting.no"
SERVER_ID = "eb0d0174"
GITHUB_REPO = "jntbruun/laksen-malerier"
KEY_FILE = build.ROOT / ".panel-nokkel"


def panel(method: str, path: str, body: bytes | None = None, content_type: str = "application/json") -> bytes:
    request = urllib.request.Request(f"{PANEL}/api/client/servers/{SERVER_ID}/{path}", data=body, method=method)
    request.add_header("Authorization", f"Bearer {KEY_FILE.read_text().strip()}")
    request.add_header("Accept", "application/json")
    if body is not None:
        request.add_header("Content-Type", content_type)
    with urllib.request.urlopen(request) as response:
        return response.read()


def upload_datapack() -> None:
    upload_url = json.loads(panel("GET", "files/upload"))["attributes"]["url"]
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
            f"filename=\"{build.DATAPACK_ZIP.name}\"\r\nContent-Type: application/zip\r\n\r\n").encode()
    body += build.DATAPACK_ZIP.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(f"{upload_url}&directory=/world/datapacks", data=body, method="POST")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    urllib.request.urlopen(request).read()


def point_server_at(pack_url: str, pack_sha1: str) -> None:
    properties = panel("GET", "files/contents?file=%2Fserver.properties").decode()
    escaped_url = pack_url.replace(":", "\\:")
    lines = []
    for line in properties.split("\n"):
        if line.startswith("resource-pack="):
            line = f"resource-pack={escaped_url}"
        elif line.startswith("resource-pack-sha1="):
            line = f"resource-pack-sha1={pack_sha1}"
        lines.append(line)
    panel("POST", "files/write?file=%2Fserver.properties", "\n".join(lines).encode(), "text/plain")


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=build.ROOT, check=True, capture_output=True, text=True).stdout.strip()


def main() -> None:
    if not KEY_FILE.exists():
        sys.exit("Mangler .panel-nokkel. Lag en API-nøkkel i panelet (Account -> API Credentials) "
                 "og lim den inn i en fil som heter .panel-nokkel i denne mappen.")
    build.main()

    git("add", "-A", "malerier", "malerier.lock.json", "dist", "gamle-malerier.json", "base-resourcepack")
    if git("status", "--porcelain", "--", "malerier", "malerier.lock.json", "dist", "base-resourcepack"):
        git("commit", "-m", "Oppdater malerier")
    print("Pusher til GitHub ...")
    git("push", "-q")

    # A commit-pinned URL never changes content, so GitHub's 5-minute cache can't serve
    # a stale zip that fails the sha1 check and kicks players.
    commit = git("rev-parse", "HEAD")
    pack_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{commit}/dist/{build.RESOURCE_PACK_ZIP.name}"
    pack_sha1 = (build.DIST / "ressurspakke-sha1.txt").read_text().strip()

    print("Laster opp datapack ...")
    upload_datapack()
    print("Oppdaterer server.properties ...")
    point_server_at(pack_url, pack_sha1)
    print("Restarter serveren ...")
    panel("POST", "power", json.dumps({"signal": "restart"}).encode())
    print("\nPublisert. Serveren er oppe igjen om et halvt minutt.")


if __name__ == "__main__":
    main()
