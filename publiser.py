"""Bygger, pusher til GitHub, laster opp datapacken, oppdaterer server.properties og restarter.

Krever en API-nøkkel fra panelet (Account -> API Credentials) i fila .panel-nokkel.
Kjør:  .venv/bin/python publiser.py   (eller dobbeltklikk "Publiser malerier.command")
"""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

import certifi

import build

PANEL = "https://panel.spillhosting.no"
SERVER_ID = "eb0d0174"
GITHUB_REPO = "jntbruun/laksen-malerier"
KEY_FILE = build.ROOT / ".panel-nokkel"


def panel_key() -> str | None:
    # GitHub Actions passes the key as a secret; locally it lives in .panel-nokkel.
    if os.environ.get("PANEL_NOKKEL"):
        return os.environ["PANEL_NOKKEL"].strip()
    return KEY_FILE.read_text().strip() if KEY_FILE.exists() else None


# python.org builds on macOS ship without root certificates; certifi brings its own.
TLS = ssl.create_default_context(cafile=certifi.where())
# Cloudflare in front of the panel blocks the default "Python-urllib" user agent (error 1010).
USER_AGENT = "laksen-malerier/1.0"


def panel(method: str, path: str, body: bytes | None = None, content_type: str = "application/json") -> bytes:
    request = urllib.request.Request(f"{PANEL}/api/client/servers/{SERVER_ID}/{path}", data=body, method=method)
    request.add_header("Authorization", f"Bearer {panel_key()}")
    request.add_header("Accept", "application/json")
    request.add_header("User-Agent", USER_AGENT)
    if body is not None:
        request.add_header("Content-Type", content_type)
    with urllib.request.urlopen(request, context=TLS) as response:
        return response.read()


def remove_unzipped_copies() -> None:
    """Someone unzipping the pack in the panel leaves a folder that Minecraft loads next to the zip,
    and the stale folder can win. GitHub is the source of truth, so the folder is moved out of the way
    (into a backup folder, not deleted: the panel account has no delete permission, and edits survive)."""
    listing = json.loads(panel("GET", "files/list?directory=%2Fworld%2Fdatapacks"))["data"]
    stray = [f["attributes"]["name"] for f in listing
             if not f["attributes"]["is_file"] and f["attributes"]["name"].startswith(build.DATAPACK_ZIP.stem)]
    if stray:
        backup = f"datapack-backup-utpakket-{datetime.now():%Y-%m-%d-%H%M%S}"
        print(f"Flytter utpakket kopi på serveren til /{backup}: {', '.join(stray)}")
        panel("POST", "files/create-folder", json.dumps({"root": "/", "name": backup}).encode())
        moves = [{"from": f"world/datapacks/{name}", "to": f"{backup}/{name}"} for name in stray]
        panel("PUT", "files/rename", json.dumps({"root": "/", "files": moves}).encode())


def upload_datapack() -> None:
    upload_url = json.loads(panel("GET", "files/upload"))["attributes"]["url"]
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"files\"; "
            f"filename=\"{build.DATAPACK_ZIP.name}\"\r\nContent-Type: application/zip\r\n\r\n").encode()
    body += build.DATAPACK_ZIP.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(f"{upload_url}&directory=/world/datapacks", data=body, method="POST")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    request.add_header("User-Agent", USER_AGENT)
    urllib.request.urlopen(request, context=TLS).read()


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


GENERATED = ["malerier.lock.json", "dist"]
IN_GITHUB_ACTIONS = bool(os.environ.get("GITHUB_ACTIONS"))


def build_and_push() -> None:
    """Build from the newest sources and push. If someone pushed while we built, the generated
    files (lock, zips) conflict; in GitHub Actions we throw our build away and rebuild on top."""
    for attempt in range(3):
        git("pull", "--rebase", "--autostash", "-q")
        build.main()
        git("add", "-A", "malerier", "gamle-malerier.json", "base-resourcepack", "ressurspakker", *GENERATED)
        if git("status", "--porcelain", "--", "malerier", "base-resourcepack", "ressurspakker", *GENERATED):
            git("commit", "-m", "Oppdater malerier")
        print("Pusher til GitHub ...")
        try:
            git("push", "-q")
            return
        except subprocess.CalledProcessError:
            if not IN_GITHUB_ACTIONS:
                sys.exit("Noen pushet samtidig. Kjør publiseringen på nytt.")
            print("Noen pushet samtidig, bygger på nytt ...")
            git("fetch", "-q")
            git("reset", "--hard", "-q", "origin/main")
    sys.exit("Fikk ikke pushet etter tre forsøk.")


RESTART_WARNING_SECONDS = 60


def console(command: str) -> None:
    panel("POST", "command", json.dumps({"command": command}).encode())


def warn_players_and_wait() -> None:
    """Give everyone online a minute to get somewhere safe before the restart kicks them."""
    print(f"Varsler spillerne, restart om {RESTART_WARNING_SECONDS} sekunder ...")
    try:
        console('title @a times 10 80 20')
        console('title @a subtitle {"text":"Nye malerier! Kom deg i trygghet.","color":"gray"}')
        console(f'title @a title {{"text":"Restart om {RESTART_WARNING_SECONDS} sek","color":"gold"}}')
        console(f"say Serveren restarter om {RESTART_WARNING_SECONDS} sekunder for nye malerier.")
        time.sleep(RESTART_WARNING_SECONDS - 10)
        console("say Restart om 10 sekunder.")
        time.sleep(10)
    except urllib.error.HTTPError:
        print("  Fikk ikke sendt varsel (serveren er kanskje av). Restarter uansett.")


def main() -> None:
    if not panel_key():
        sys.exit("Mangler .panel-nokkel. Lag en API-nøkkel i panelet (Account -> API Credentials) "
                 "og lim den inn i en fil som heter .panel-nokkel i denne mappen.")
    build_and_push()

    # A commit-pinned URL never changes content, so GitHub's 5-minute cache can't serve
    # a stale zip that fails the sha1 check and kicks players.
    commit = git("rev-parse", "HEAD")
    pack_url = f"https://raw.githubusercontent.com/{GITHUB_REPO}/{commit}/dist/{build.RESOURCE_PACK_ZIP.name}"
    pack_sha1 = (build.DIST / "ressurspakke-sha1.txt").read_text().strip()

    print("Laster opp datapack ...")
    remove_unzipped_copies()
    upload_datapack()
    print("Oppdaterer server.properties ...")
    point_server_at(pack_url, pack_sha1)
    warn_players_and_wait()
    print("Restarter serveren ...")
    panel("POST", "power", json.dumps({"signal": "restart"}).encode())
    print("\nPublisert. Serveren er oppe igjen om et halvt minutt.")


if __name__ == "__main__":
    main()
