# Intermac-Fernwartung: Änderungen gegenüber RustDesk

Dieses Repository ist ein Fork von [rustdesk/rustdesk](https://github.com/rustdesk/rustdesk) (Tag `1.5.0`) und steht wie
das Original unter der **GNU Affero General Public License v3** (siehe `LICENCE`). Es ist der Quelltext der Clients, die unter
dem Namen „intermac-fernwartung“ weitergegeben werden.

## Änderungen (AGPL §5a)

Gegenüber dem Tag `1.5.0` sind folgende Änderungen gemacht:

- `.github/workflows/build-intermac.yml`: eigener, auf Windows x64 und macOS arm64 gekürzter Build-Workflow.
  Die übrigen Upstream-Workflows sind entfernt.
- `.github/scripts/apply-intermac-config.py`: wird beim Build ausgeführt und
  - belegt `OVERWRITE_SETTINGS` (`libs/hbb_common/src/config.rs`) mit ID-Server, öffentlichem Schlüssel und API-Server,
  - schaltet die Update-Prüfung ab (`check_software_update` in `src/common.rs`).
  Die Werte kommen aus den Variablen/Secrets `RUSTDESK_HOST`, `RUSTDESK_KEY`, `RUSTDESK_API` des GitHub-Environments
  und stehen nicht im Repository.
- Diese Datei.

Der Quelltext der Auslieferung ist der jeweilige Commit dieses Repositories; der Client selbst enthält darüber hinaus nur
die genannten Werte aus dem Environment.

RustDesk ist eine Marke ihrer Inhaber; dieses Projekt ist nicht mit RustDesk verbunden.
