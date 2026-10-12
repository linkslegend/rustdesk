#!/usr/bin/env python3
"""Belegt den RustDesk-Client mit unseren Servern vor und schaltet die Update-Prüfung ab.

Liest RUSTDESK_HOST, RUSTDESK_KEY und RUSTDESK_API aus der Umgebung (im Workflow aus dem GitHub-Environment).
Die Werte stehen weder im Code noch im Workflow und werden nie ausgegeben.

  apply-intermac-config.py          Quelltext patchen (im Wurzelverzeichnis des Repos aufrufen)
  apply-intermac-config.py --check  nur die Werte prüfen, nichts ändern

Jede Ersetzung muss genau einmal greifen; ändert sich der Upstream-Code, bricht das Skript ab, statt still
einen Client ohne unsere Einstellungen zu bauen.
"""
import os
import re
import sys
from pathlib import Path

# Nur Zeichen, die in einem Rust-String-Literal unkritisch sind (kein Anführungszeichen, kein Backslash).
HOST = re.compile(r"[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?(:[0-9]{1,5})?")
KEY = re.compile(r"[A-Za-z0-9+/_-]{30,100}={0,2}")
API = re.compile(r"https?://[A-Za-z0-9]([A-Za-z0-9.-]{0,251}[A-Za-z0-9])?(:[0-9]{1,5})?(/[A-Za-z0-9._~/-]{0,200})?")

CONFIG_RS = Path("libs/hbb_common/src/config.rs")
COMMON_RS = Path("src/common.rs")

OVERWRITE_OLD = "pub static ref OVERWRITE_SETTINGS: RwLock<HashMap<String, String>> = Default::default();"
UPDATE_OLD = "pub fn check_software_update() {\n    if is_custom_client() {"
UPDATE_NEW = "pub fn check_software_update() {\n    if true {"


def fail(message: str) -> None:
    print(f"Fehler: {message}", file=sys.stderr)
    sys.exit(1)


def read_values() -> tuple[str, str, str]:
    values = []
    for name, pattern in (("RUSTDESK_HOST", HOST), ("RUSTDESK_KEY", KEY), ("RUSTDESK_API", API)):
        value = os.environ.get(name, "").strip()
        if not value:
            fail(f"{name} ist nicht gesetzt (Variable bzw. Secret im GitHub-Environment anlegen).")
        if not pattern.fullmatch(value):
            fail(f"{name} hat ein ungültiges Format.")
        values.append(value)
    return values[0], values[1], values[2]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        fail(f"{path}: erwartete Stelle kommt {count}-mal vor (erwartet: 1). Upstream-Code hat sich geändert.")
    path.write_text(text.replace(old, new), encoding="utf-8")


def main() -> None:
    host, key, api = read_values()
    if "--check" in sys.argv[1:]:
        print("Werte sind vorhanden und gültig.")
        return
    overwrite_new = (
        "pub static ref OVERWRITE_SETTINGS: RwLock<HashMap<String, String>> = RwLock::new(HashMap::from([\n"
        f'        ("custom-rendezvous-server".to_owned(), "{host}".to_owned()),\n'
        f'        ("key".to_owned(), "{key}".to_owned()),\n'
        f'        ("api-server".to_owned(), "{api}".to_owned()),\n'
        "    ]));"
    )
    replace_once(CONFIG_RS, OVERWRITE_OLD, overwrite_new)
    replace_once(COMMON_RS, UPDATE_OLD, UPDATE_NEW)
    print("Server-Voreinstellung gesetzt, Update-Prüfung abgeschaltet.")


if __name__ == "__main__":
    main()
