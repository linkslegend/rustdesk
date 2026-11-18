#!/usr/bin/env python3
"""Baut das Intermac-Branding und die eigene Update-Prüfung in den RustDesk-Quelltext ein (im Wurzelverzeichnis aufrufen).

  apply-intermac-branding.py          Quelltext patchen
  apply-intermac-branding.py --check  nur prüfen, ob alle Stellen genau einmal vorkommen, nichts ändern

Ändert nur den sichtbaren Namen, Icons und Logo. Interne Kennungen bleiben: APP_NAME (Config-Ordner, Dienstname,
Druckername), Bundle-ID, RustDesk.app (macOS-Pfade in src/platform/macos.rs) und das URL-Schema rustdesk://.
Die Bilder erzeugt make-intermac-assets.py nach assets/intermac/generated/.

Jede Ersetzung muss genau einmal greifen; ändert sich der Upstream-Code, bricht das Skript ab.
"""
import shutil
import sys
from pathlib import Path

NAME = "Intermac Fernwartung"
SOURCE_URL = "https://github.com/linkslegend/rustdesk"
SOURCE_TEXT = "Basiert auf RustDesk, Quelltext: github.com/linkslegend/rustdesk"
GEN = Path("assets/intermac/generated")

# (Quelle, Ziel, Ziel muss schon existieren)
FILES = [
    (GEN / "windows/app_icon.ico", "flutter/windows/runner/resources/app_icon.ico", True),
    (GEN / "windows/app_icon.ico", "res/icon.ico", True),  # portabler Packer (libs/portable/build.rs)
    (GEN / "windows/tray-icon.ico", "res/tray-icon.ico", True),
    (GEN / "macos/AppIcon.icns", "flutter/macos/Runner/AppIcon.icns", True),
    (GEN / "macos/mac-tray-x2.png", "res/mac-tray-dark-x2.png", True),
    (GEN / "macos/mac-tray-x2.png", "res/mac-tray-light-x2.png", True),
    (GEN / "res/32x32.png", "res/32x32.png", True),
    (GEN / "res/64x64.png", "res/64x64.png", True),
    (GEN / "res/128x128.png", "res/128x128.png", True),
    (GEN / "res/128x128@2x.png", "res/128x128@2x.png", True),
    (GEN / "res/icon.png", "res/icon.png", True),
    (GEN / "res/mac-icon.png", "res/mac-icon.png", True),
    (GEN / "flutter/icon.svg", "flutter/assets/icon.svg", True),
    # loadLogo() in flutter/lib/common.dart nimmt diese Dateien je nach Theme, ohne Codeänderung.
    (GEN / "flutter/logo_light.png", "flutter/assets/logo_light.png", False),
    (GEN / "flutter/logo_dark.png", "flutter/assets/logo_dark.png", False),
    (GEN / "portable/label.png", "libs/portable/src/res/label.png", True),
    (Path("intermac/flutter/intermac_update.dart"), "flutter/lib/intermac/intermac_update.dart", False),
]

# (Datei, alt, neu)
PATCHES = [
    # Fenstertitel (und damit Taskleiste) aller Fenster.
    (
        "flutter/lib/common.dart",
        "String getWindowName({WindowType? overrideType}) {\n  final name = bind.mainGetAppNameSync();\n",
        f"String getWindowName({{WindowType? overrideType}}) {{\n  final name = '{NAME}';\n",
    ),
    # Windows findet das laufende Hauptfenster über seinen Titel (Single-Instance, rustdesk://-Links);
    # Fenstertitel und beide Suchstellen müssen gleich lauten.
    (
        "flutter/windows/runner/main.cpp",
        "  // Uri links dispatch\n  HWND hwnd = ::FindWindowW(getWindowClassName(), app_name.c_str());\n",
        f'  app_name = L"{NAME}";\n  // Uri links dispatch\n  HWND hwnd = ::FindWindowW(getWindowClassName(), app_name.c_str());\n',
    ),
    (
        "src/core_main.rs",
        "            &crate::platform::FLUTTER_RUNNER_WIN32_WINDOW_CLASS,\n            &crate::get_app_name(),\n",
        f'            &crate::platform::FLUTTER_RUNNER_WIN32_WINDOW_CLASS,\n            "{NAME}",\n',
    ),
    # Dateieigenschaften / Task-Manager der rustdesk.exe und des portablen Packers.
    (
        "flutter/windows/runner/Runner.rc",
        'VALUE "FileDescription", "RustDesk Remote Desktop" "\\0"',
        f'VALUE "FileDescription", "{NAME}" "\\0"',
    ),
    (
        "flutter/windows/runner/Runner.rc",
        'VALUE "ProductName", "RustDesk" "\\0"',
        f'VALUE "ProductName", "{NAME}" "\\0"',
    ),
    ("libs/portable/Cargo.toml", 'ProductName = "RustDesk"\n', f'ProductName = "{NAME}"\n'),
    ("libs/portable/Cargo.toml", 'FileDescription = "RustDesk Remote Desktop"\n', f'FileDescription = "{NAME}"\n'),
    # macOS: Name in Menüleiste und Dock; Bundle-ID und RustDesk.app bleiben.
    (
        "flutter/macos/Runner/Info.plist",
        "\t<key>CFBundleName</key>\n\t<string>$(PRODUCT_NAME)</string>\n",
        f"\t<key>CFBundleName</key>\n\t<string>{NAME}</string>\n"
        f"\t<key>CFBundleDisplayName</key>\n\t<string>{NAME}</string>\n",
    ),
    # Tray-Tooltip (nur bei installiertem Dienst sichtbar).
    ("src/tray.rs", '"{} {}",\n                crate::get_app_name(),\n', f'"{{}} {{}}",\n                "{NAME}",\n'),
    (
        "src/tray.rs",
        '"{} - {}\\n{}",\n                crate::get_app_name(),\n',
        f'"{{}} - {{}}\\n{{}}",\n                "{NAME}",\n',
    ),
    # Über-Dialog: Titel und AGPL-Hinweis auf den Quelltext.
    (
        "flutter/lib/desktop/pages/desktop_setting_page.dart",
        "child: _Card(title: translate('About RustDesk'), children: [\n",
        f"child: _Card(title: translate('About RustDesk').replaceAll('RustDesk', '{NAME}'), children: [\n",
    ),
    (
        "flutter/lib/desktop/pages/desktop_setting_page.dart",
        "              Container(\n                decoration: const BoxDecoration(color: Color(0xFF2c8cff)),\n",
        "              InkWell(\n"
        "                  onTap: () {\n"
        f"                    launchUrlString('{SOURCE_URL}');\n"
        "                  },\n"
        "                  child: const Text(\n"
        f"                    '{SOURCE_TEXT}',\n"
        "                    style: linkStyle,\n"
        "                  ).marginSymmetric(vertical: 4.0)),\n"
        "              Container(\n                decoration: const BoxDecoration(color: Color(0xFF2c8cff)),\n",
    ),
    # Eigene Update-Prüfung: Hinweis im Hauptfenster an der Stelle der Upstream-Hinweise.
    (
        "flutter/lib/desktop/pages/desktop_home_page.dart",
        "import 'package:flutter_hbb/desktop/widgets/update_progress.dart';\n",
        "import 'package:flutter_hbb/desktop/widgets/update_progress.dart';\n"
        "import 'package:flutter_hbb/intermac/intermac_update.dart';\n",
    ),
    (
        "flutter/lib/desktop/pages/desktop_home_page.dart",
        "  Widget buildHelpCards(String updateUrl) {\n",
        "  Widget buildHelpCards(String updateUrl) {\n"
        "    final intermacCard = intermacUpdateCard(buildInstallCard);\n"
        "    if (intermacCard != null) {\n"
        "      return intermacCard;\n"
        "    }\n",
    ),
]


def fail(message: str) -> None:
    print(f"Fehler: {message}", file=sys.stderr)
    sys.exit(1)


def read(path: Path) -> tuple[str, str]:
    """Inhalt mit \\n und das ursprüngliche Zeilenende (Windows-Checkout liefert CRLF)."""
    raw = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in raw else "\n"
    return raw.replace("\r\n", "\n"), newline


def check() -> dict[Path, str]:
    for src, dst, must_exist in FILES:
        if not src.is_file():
            fail(f"{src} fehlt (make-intermac-assets.py ausführen).")
        if Path(dst).exists() != must_exist:
            state = "fehlt" if must_exist else "existiert schon"
            fail(f"{dst} {state}. Upstream-Code hat sich geändert.")
    texts: dict[Path, str] = {}
    for file, old, new in PATCHES:
        path = Path(file)
        if path not in texts:
            texts[path] = read(path)[0]
        count = texts[path].count(old)
        if count != 1:
            fail(f"{file}: erwartete Stelle kommt {count}-mal vor (erwartet: 1). Upstream-Code hat sich geändert.")
        texts[path] = texts[path].replace(old, new)
    return texts


def main() -> None:
    texts = check()
    if "--check" in sys.argv[1:]:
        print("Alle Stellen gefunden.")
        return
    for path, text in texts.items():
        newline = read(path)[1]
        path.write_bytes(text.replace("\n", newline).encode("utf-8"))
    for src, dst, _ in FILES:
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)
    print(f"Branding „{NAME}“ und Update-Prüfung eingebaut.")


if __name__ == "__main__":
    main()
