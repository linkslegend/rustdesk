// Intermac: Update-Prüfung gegen den eigenen API-Server (<API-Server>/api/version) statt rustdesk.com.
//
// Wird von .github/scripts/apply-intermac-branding.py nach flutter/lib/intermac/ kopiert und am Anfang von
// buildHelpCards() in desktop_home_page.dart eingehängt. Erwartete Antwort:
//   { "version": "1.5.4", "windows_url": "https://…exe", "mac_arm64_url": "https://…dmg",
//     "mac_x64_url": "https://…dmg", "notes": "…" }
// Geprüft wird beim Start und danach alle 24 Stunden; jeder Fehler bleibt still. Installiert wird nur nach Klick.
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_hbb/common.dart';
import 'package:flutter_hbb/models/platform_model.dart';
import 'package:flutter_hbb/utils/multi_window_manager.dart';
import 'package:get/get.dart';

typedef IntermacCardBuilder = Widget Function(
    String title, String content, String btnText, GestureTapCallback onPressed);

const _kCheckInterval = Duration(hours: 24);
const _kTimeout = Duration(seconds: 30);
const _kMaxResponseBytes = 64 * 1024;
final _kVersion = RegExp(r'^\d+(\.\d+){0,3}(-\d+)?$');

class _Release {
  final String version;
  final Uri url;
  final String notes;
  const _Release(this.version, this.url, this.notes);
}

final _release = Rxn<_Release>();
// null: kein Download; -1: läuft, Größe unbekannt; sonst Prozent.
final _progress = RxnInt();
final _failed = false.obs;
Timer? _timer;

/// Hinweis "Neue Version verfügbar" für das Hauptfenster, sonst null. Startet beim ersten Aufruf die Prüfung.
Widget? intermacUpdateCard(IntermacCardBuilder buildCard) {
  _ensureStarted();
  final release = _release.value;
  final progress = _progress.value;
  final failed = _failed.value;
  if (release == null) {
    return null;
  }
  final lines = ['Version ${release.version}'];
  if (release.notes.isNotEmpty) {
    lines.add(release.notes);
  }
  if (isWindows) {
    lines.add('Das Programm wird dafür beendet und neu gestartet.');
  }
  if (failed) {
    lines.add('Der Download ist fehlgeschlagen.');
  }
  final String btnText;
  if (progress == null) {
    btnText = isWindows ? 'Herunterladen und starten' : 'Herunterladen und öffnen';
  } else {
    btnText = progress < 0 ? 'Wird geladen …' : 'Wird geladen … $progress %';
  }
  return buildCard('Neue Version verfügbar', lines.join('\n'), btnText, () {
    if (_progress.value == null) {
      _download(release);
    }
  });
}

void _ensureStarted() {
  if (_timer != null || !(isWindows || isMacOS)) {
    return;
  }
  _timer = Timer.periodic(_kCheckInterval, (_) => _check());
  _check();
}

String _urlKey() {
  if (isWindows) {
    return 'windows_url';
  }
  return Platform.version.contains('macos_arm64') ? 'mac_arm64_url' : 'mac_x64_url';
}

Future<void> _check() async {
  try {
    final api = (await bind.mainGetApiServer()).trim().replaceAll(RegExp(r'/+$'), '');
    final base = Uri.tryParse(api);
    if (base == null || !(base.scheme == 'https' || base.scheme == 'http') || base.host.isEmpty) {
      return;
    }
    final text = await _getText(Uri.parse('$api/api/version'));
    if (text == null) {
      return;
    }
    final json = jsonDecode(text);
    if (json is! Map) {
      return;
    }
    final version = json['version'];
    final url = json[_urlKey()];
    final notes = json['notes'];
    if (version is! String || url is! String || !_kVersion.hasMatch(version.trim())) {
      return;
    }
    final uri = Uri.tryParse(url.trim());
    // Nur https: die Datei wird nach dem Klick ausgeführt bzw. geöffnet.
    if (uri == null || uri.scheme != 'https' || uri.host.isEmpty) {
      return;
    }
    if (versionCmp(version.trim(), await bind.mainGetVersion()) <= 0) {
      _release.value = null;
      return;
    }
    // translate() wertet {…} als Platzhalter aus.
    final cleanNotes = notes is String ? notes.replaceAll(RegExp(r'[{}]'), '').trim() : '';
    _release.value = _Release(version.trim(), uri, cleanNotes);
  } catch (e) {
    debugPrint('Intermac update check failed: $e');
  }
}

Future<String?> _getText(Uri uri) async {
  final client = HttpClient()..connectionTimeout = _kTimeout;
  try {
    final request = await client.getUrl(uri).timeout(_kTimeout);
    final response = await request.close().timeout(_kTimeout);
    if (response.statusCode != HttpStatus.ok) {
      return null;
    }
    final bytes = <int>[];
    await for (final chunk in response.timeout(_kTimeout)) {
      bytes.addAll(chunk);
      if (bytes.length > _kMaxResponseBytes) {
        return null;
      }
    }
    return utf8.decode(bytes);
  } finally {
    client.close(force: true);
  }
}

String _fileName(_Release release) {
  final ext = isWindows ? '.exe' : '.dmg';
  final segments = release.url.pathSegments;
  var name = segments.isEmpty ? '' : segments.last.replaceAll(RegExp(r'[^A-Za-z0-9._-]'), '_');
  if (name.isEmpty || name.startsWith('.')) {
    name = 'intermac-fernwartung-${release.version}';
  }
  if (!name.toLowerCase().endsWith(ext)) {
    name += ext;
  }
  return name;
}

Future<void> _download(_Release release) async {
  _failed.value = false;
  _progress.value = -1;
  final client = HttpClient()..connectionTimeout = _kTimeout;
  try {
    final request = await client.getUrl(release.url).timeout(_kTimeout);
    final response = await request.close().timeout(_kTimeout);
    if (response.statusCode != HttpStatus.ok) {
      throw HttpException('HTTP ${response.statusCode}', uri: release.url);
    }
    final dir = await Directory.systemTemp.createTemp('intermac-update-');
    final file = File('${dir.path}${Platform.pathSeparator}${_fileName(release)}');
    final sink = file.openWrite();
    final total = response.contentLength;
    var received = 0;
    try {
      await for (final chunk in response.timeout(const Duration(minutes: 2))) {
        sink.add(chunk);
        received += chunk.length;
        if (total > 0) {
          final percent = received * 100 ~/ total;
          if (percent != _progress.value) {
            _progress.value = percent;
          }
        }
      }
    } finally {
      await sink.close();
    }
    if (total > 0 && received != total) {
      throw HttpException('unvollständig ($received von $total Bytes)', uri: release.url);
    }
    await _open(file);
  } catch (e) {
    debugPrint('Intermac update download failed: $e');
    _failed.value = true;
  } finally {
    client.close(force: true);
    _progress.value = null;
  }
}

Future<void> _open(File file) async {
  if (isMacOS) {
    final result = await Process.run('open', [file.path]);
    if (result.exitCode != 0) {
      throw ProcessException('open', [file.path], '${result.stderr}', result.exitCode);
    }
    return;
  }
  // Windows: main.cpp lässt nur eine Instanz zu (sucht das Hauptfenster); die neue Version darf erst starten,
  // wenn dieser Prozess (im portablen Modus auch der Server) beendet ist und die Dateien frei sind.
  final path = file.path.replaceAll("'", "''");
  await Process.start(
    'powershell.exe',
    [
      '-NoProfile',
      '-NonInteractive',
      '-WindowStyle',
      'Hidden',
      '-Command',
      "Wait-Process -Id $pid -Timeout 120 -ErrorAction SilentlyContinue; "
          "Start-Sleep -Seconds 2; Start-Process -FilePath '$path'",
    ],
    mode: ProcessStartMode.detached,
  );
  await rustDeskWinManager.closeAllSubWindows();
  exit(0);
}
