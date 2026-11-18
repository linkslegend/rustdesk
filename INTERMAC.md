# Intermac-Fernwartung: Änderungen gegenüber RustDesk

Dieses Repository ist ein Fork von [rustdesk/rustdesk](https://github.com/rustdesk/rustdesk) (Tag `1.5.3`) und steht wie
das Original unter der **GNU Affero General Public License v3** (siehe `LICENCE`). Es ist der Quelltext der Clients, die unter
dem Namen „Intermac Fernwartung“ weitergegeben werden.

## Änderungen (AGPL §5a)

Der Upstream-Quelltext ist im Repository unverändert; alle Änderungen werden beim Build von Skripten eingespielt:

- `.github/workflows/build-intermac.yml`: eigener, auf Windows x64 und macOS (arm64, x64) gekürzter Build-Workflow. Im macOS-Job wird die App nach dem Bauen ad-hoc signiert
  (`codesign --force --deep --sign -`) und die Signatur in der fertigen DMG geprüft.
  Die übrigen Upstream-Workflows sind entfernt.
- `.github/scripts/apply-intermac-config.py`: wird beim Build ausgeführt und
  - belegt `OVERWRITE_SETTINGS` (`libs/hbb_common/src/config.rs`) mit ID-Server, öffentlichem Schlüssel und API-Server,
  - schaltet die Update-Prüfung gegen rustdesk.com ab (`check_software_update` in `src/common.rs`).
  Die Werte kommen aus den Variablen/Secrets `RUSTDESK_HOST`, `RUSTDESK_KEY`, `RUSTDESK_API` des GitHub-Environments
  und stehen nicht im Repository.
- `.github/scripts/apply-intermac-branding.py`: wird beim Build ausgeführt und
  - setzt den sichtbaren Namen „Intermac Fernwartung“ (Fenstertitel, Windows-Dateieigenschaften, macOS-Menüleiste/Dock,
    Tray-Tooltip, Über-Dialog) und im Über-Dialog den Hinweis auf diesen Quelltext,
  - ersetzt App-Icon, Tray-Icon, Logo im Hauptfenster und den Schriftzug des portablen Windows-Starters
    (Bilder aus `assets/intermac/generated/`),
  - kopiert `intermac/flutter/intermac_update.dart` nach `flutter/lib/intermac/` und zeigt dessen Hinweis
    „Neue Version verfügbar“ im Hauptfenster an. Die Prüfung fragt `<API-Server>/api/version` beim Start und alle 24 Stunden ab;
    heruntergeladen und gestartet (Windows) bzw. geöffnet (macOS) wird nur nach Klick.
  Interne Kennungen (Config-Ordner, Dienstname, Bundle-ID, `RustDesk.app`, URL-Schema `rustdesk://`) bleiben unverändert.
- `.github/scripts/make-intermac-assets.py`: erzeugt aus den Vorlagen in `assets/intermac/` die Icon- und Logo-Dateien
  in `assets/intermac/generated/` (lokal auf macOS ausführen, Ergebnis wird committet).
- Diese Datei.

Der Quelltext der Auslieferung ist der jeweilige Commit dieses Repositories; der Client selbst enthält darüber hinaus nur
die genannten Werte aus dem Environment.

RustDesk ist eine Marke ihrer Inhaber; dieses Projekt ist nicht mit RustDesk verbunden.
