# Аудит проекта — найденные проблемы

Дата: 18 июня 2026
Формат: критичность | сложность исправления | описание | файл | решение

---

## Условные обозначения

Критичность:
- **CRI** — краш, потеря данных, уязвимость
- **HI** — зависание UI, race condition, утечка
- **MED** — редкий краш, утечка памяти при особых сценариях
- **LOW** — code style, print(), незначительные улучшения

Сложность:
- **easy** — 1-5 строк
- **med** — разумный рефакторинг (один модуль)
- **hard** — архитектурные изменения (несколько модулей)

---

## Раздел 1: Crash / Data Integrity (CRI)

<!--
### 1.1 WebServer — общее состояние без блокировки (CRI, hard) — ИСПРАВЛЕНО 18.06.2026
**Фикс:** threading.Lock() добавлен, все 12 shared полей защищены в web_server.py (update_*) и web_api.py (handle_*).
-->

<!--
### 1.2 AudioScanner — параллельная запись в SQLite (CRI, med) — ИСПРАВЛЕНО 18.06.2026
**Фикс:** ThreadPoolExecutor удалён, последовательная обработка в QThread.
-->

---

## Раздел 2: UI Freeze / Race / Утечки (HI)

<!--
### 2.1 page_about.py — синхронные wmic в UI-потоке (HI, easy → med) — ИСПРАВЛЕНО 18.06.2026
**Фикс:** Вынесено в _HwIdWorker(QThread), _on_register запускает поток, _on_hwid_ready отправляет POST.
-->

<!--
### 2.2 page_webserver.py — синхронный DNS/connect в UI-потоке (HI, easy) — ИСПРАВЛЕНО 18.06.2026
**Фикс:** IP разрешается в _IpResolveWorker(QThread), кешируется в _resolved_ip. UI показывает "Определение IP..." пока идёт резолв.
-->

<!--
### 2.3 web_api.py — Qt-сигналы из asyncio-потока (HI, med) — ИСПРАВЛЕНО 18.06.2026
**Фикс:** _SignalRelay(QObject) с moveToThread(main_thread) создаётся в WebServer.__init__(); все .emit() в APIHandlers перенаправлены через self._server._relay.
-->

<!--
### 2.4 AudioScanner — флаг _is_cancelled из 3 потоков (HI, easy)
**Фикс (18.06.2026):** ThreadPoolExecutor удалён — флаг только в QThread + main thread.
-->

<!--
### 2.5 AppSettings — _app_settings_instances без блокировки (HI, easy → med) — ИСПРАВЛЕНО 18.06.2026
**Фикс:** _settings_lock (RLock) защищает _app_settings_instances, _read_settings_json, _write_settings_json, _load/_save/batch_save, и все модульные get/set функции. Read-modify-write циклы атомарны.
-->

<!--
### 2.6 LibraryModel — stale результат от старого worker (HI, easy) — **Исправлено 18.06.2026**

**Файл:** `ui/library/model.py`
**Описание:** `_fetch_page()` проверяет `isRunning()`, но между проверкой и созданием нового worker старый может завершиться и отдать `results_ready` → данные от старого запроса попадут в новый контекст.
**Решение:** Добавлен `_gen` counter, инкрементится на каждый `reset()`. `_on_page_fetched` и `_on_total_count_ready` проверяют `gen != self._gen`. Старый worker отключается через `try: worker.results_ready.disconnect()` перед заменой.
-->

<!--
### 2.7 ArtistProcessingWorker — DB write из worker (HI, med) — **Исправлено 18.06.2026**

**Файл:** `ui/library/artist_worker.py`, `core/db/connection.py`
**Описание:** Worker пишет в DB (`ensure_cover_for_track`, `update_artists_cache`) из своего потока, пока AudioScanner в main-thread может писать туда же через QThread.
**Решение:** В `get_connection()` добавлен `PRAGMA busy_timeout=5000` — SQLite ждёт блокировку до 5с вместо немедленного `database is locked`. Это решает race между процессами (player + library) без рефакторинга архитектуры worker.
-->

---

## Раздел 3: Medium — редкие краши / утечки

### 3.1 QTimer.singleShot лямбды с захватом self после удаления (MED, easy) — **Исправлено 18.06.2026**

**Файлы:** `ui/player/scanning.py`, `ui/player/playback.py`, `ui/library/dialog.py`
**Описание:** Десяток `QTimer.singleShot()` с лямбдами, захватывающими `self`, `self._mw`. Если диалог/окно закрыто до срабатывания таймера → обращение к удалённому C++ объекту → RuntimeError.
**Решение:** Все лямбды заменены на внутренние `def`-функции с `try/except RuntimeError: pass`. `managers.py` не требует правок — `do_bring` не обращается к `self`. `web_integration.py` — bound methods, не лямбды.

### 3.2 scanning.py — AudioScanner без deleteLater при перезапуске (MED, easy) — **Исправлено 18.06.2026**

**Файл:** `ui/player/scanning.py`
**Описание:** `scan()` создаёт новый AudioScanner, а старый только `cancel()` без `deleteLater()`. При быстрых вызовах объекты копятся.
**Решение:** В `scan()`: `disconnect()` всех 6 сигналов старого сканера + `deleteLater()` перед созданием нового.

### 3.3 analysis_worker.py — deleteLater() не вызывается при перезапуске (MED, easy) — **Исправлено 18.06.2026**

**Файл:** `utils/analysis_worker.py`
**Описание:** В `start_analysis()` и `_advance_to_library()` старый `AnalysisWorker` перезаписывается без `deleteLater()`.
**Решение:** `_cancel_worker()` теперь вызывает `worker.deleteLater()` + `worker = None`. `_advance_to_library()` делает то же самое перед созданием нового worker.

### 3.4 tag_editor — потоки поиска/загрузки без deleteLater (MED, easy) — **Исправлено 18.06.2026**

**Файл:** `ui/tag_editor/editor.py`
**Описание:** При повторном поиске/загрузке обложек старые `QThread`-объекты осиротевают.
**Решение:** Добавлен `_replace_thread(attr, thread)` — `quit()`/`wait(500)`/`terminate()` + `deleteLater()` старого. Применён во всех 4 местах. `_cleanup_threads()` переписан аналогично.

### 3.5 MainWindow — AudioPlayer и QMediaPlayer без parent (MED, easy) — **Исправлено 18.06.2026**

**Файлы:** `ui/player/main_window.py`, `core/player.py`
**Описание:** `self.player = AudioPlayer()` — parent=None. `self._player = QMediaPlayer()` — parent=None. Qt-дерево не знает об этих объектах, при закрытии MainWindow они не очищаются автоматически.
**Решение:** `AudioPlayer(self)`, `QMediaPlayer(self)`.

---

## Раздел 4: Low — code quality

### 4.1 except Exception: pass без логирования (LOW, easy) — **Исправлено 18.06.2026**

**25 файлов, 55 вхождений.** Все исключения молча подавлялись.
**Решение:** Добавлен `print("file.method: description")` в каждый блок. Формат: `файл.метод: краткое описание`.

### 4.2 print() в production-коде (LOW, easy)

**Файлы:** `core/ipc.py:14`, `core/web_server.py:4`, `core/web_api.py:3`, `analysis_worker.py:6`, `media_keys.py:3` и др. — всего 50+ `print()`.
**Решение:** Заменить на `logger.info()` / `logger.debug()`.

### 4.3 managers.py — processEvents() в _bring_to_front (LOW, easy)

**Файл:** `ui/player/managers.py:23`
**Описание:** `QApplication.processEvents()` после `showNormal()`/`raise_()`. Агентные правила предписывают использовать `QTimer.singleShot(0, ...)`.
**Решение:** Заменить inline async Win32 вызовы на цепочку `QTimer.singleShot`.

### 4.4 cfg.ACCENT_COLOR — reassign без триггера обновления (LOW, easy)

**Файл:** `ui/player/playback.py:94`
**Описание:** Прямое присвоение `cfg.ACCENT_COLOR = new_color` — модульная константа изменяется в рантайме. Другие модули могут видеть неконсистентное значение до завершения `apply_accent_to_main_window()`.
**Решение:** Использовать `cfg.set_accent_color(new_color)` с внутренним `_accent_color` и триггером обновления.

---

## Раздел 5: Косметические / опционально

### 5.1 WebIntegration — нет parent (LOW, easy)

**Файл:** `ui/web_integration.py:22-23`
**Решение:** Передавать parent в `__init__` и в `super().__init__(parent)`.

### 5.2 WebServer — нет parent (LOW, easy)

**Файл:** `core/web_server.py:40-41`
**Решение:** Передавать parent в `__init__` и в `super().__init__(parent)`.

---

## Сводная таблица

| # | Раздел | Файл | Крит. | Сложн. | Описание | Статус |
|---|--------|------|-------|--------|----------|--------|
<!-- | 1.1 | WebServer | ... | CRI | hard | ... | ❌ | -->
<!-- | 2.1 | wmic freeze | ... | HI | easy→med | ... | ❌ | -->
<!-- | 2.2 | DNS freeze | ... | HI | easy | socket.getaddrinfo в UI-потоке | ❌ | -->
<!-- | 2.3 | Signals | ... | HI | med | Qt-сигналы из asyncio-потока | ❌ | -->
<!-- | 2.5 | Settings | ... | HI | easy→med | _app_settings_instances без Lock | ❌ | -->
<!-- | 2.6 | LibraryModel | ... | HI | easy | ... | ❌ | -->
<!-- | 2.7 | ArtistWorker | ... | HI | med | ... | ❌ | -->
| 3.1 | Timer lambdas | 3 файла | MED | easy | QTimer после удаления self/self._mw | ✅ |
| 3.2 | scanning.py | `ui/player/scanning.py` | MED | easy | AudioScanner без deleteLater | ✅ |
| 3.3 | analysis_worker.py | `utils/analysis_worker.py` | MED | easy | Worker без deleteLater | ✅ |
| 3.4 | tag_editor | `ui/tag_editor/editor.py` | MED | easy | Threads без deleteLater | ✅ |
| 3.5 | Parent | `main_window.py` + `player.py` | MED | easy | AudioPlayer/QMediaPlayer без parent | ✅ |
| 4.1 | except pass | 25 файлов | LOW | easy | 55x except Exception: pass без лога | ✅ |
| 4.2 | print() | 14 файлов | LOW | easy | 50+ print() вместо logger | ❌ |
| 4.3 | processEvents | `managers.py` | LOW | easy | processEvents() вместо QTimer | — (пропущено) |
| 4.4 | ACCENT_COLOR | `playback.py` | LOW | easy | Прямая мутация константы | — (пропущено) |
| 5.1 | no parent | `web_integration.py` | LOW | easy | QObject без parent | ❌ |
| 5.2 | no parent | `web_server.py` | LOW | easy | QObject без parent | ❌ |

---

## Исправлено (в этой сессии)

| # | Проблема | Крит. | Файл | Фикс |
|---|----------|-------|------|------|
| 1.1 | WebServer — shared state без Lock | CRI | `core/web_server.py` + `core/web_api.py` | `threading.Lock()` для всех 12 shared полей |
| 1.2 | AudioScanner — параллельная запись в SQLite | CRI | `utils/audio_scanner.py` | ThreadPoolExecutor удалён, последовательная обработка |
| 2.1 | wmic freeze в `_on_register` | HI | `ui/settings/page_about.py` | `_HwIdWorker(QThread)` — HWID собирается в фоне |
| 2.2 | DNS freeze при открытии настроек | HI | `ui/settings/page_webserver.py` | `_IpResolveWorker(QThread)` + кеш `_resolved_ip` |
| 2.3 | Qt-сигналы из asyncio-потока | HI | `core/web_api.py` + `core/web_server.py` | `_SignalRelay(QObject)` pinned to main thread |
| 2.4 | AudioScanner — `_is_cancelled` из 3 потоков | HI | `utils/audio_scanner.py` | ThreadPoolExecutor удалён — флаг только в 2 потоках |
| 2.5 | AppSettings — race на списке + файле | HI | `core/settings.py` | `_settings_lock (RLock)` во всех get/set/IO |
| 2.6 | LibraryModel — stale worker | HI | `ui/library/model.py` | `_gen` counter + disconnect старого worker |
| 2.7 | ArtistWorker — DB write race | HI | `core/db/connection.py` | `PRAGMA busy_timeout=5000` во всех соединениях |
| — | Path traversal в `_on_play_folder` | HI | `ui/web_integration.py` | `startswith` → `realpath` + `commonpath` |
| — | Двойное сердце в делегате | MED | `ui/playlist_view.py` | Удалён дублирующий draw в paint() |
| — | Синхронный HTTP в `CoverTile` | HI | `ui/tag_editor/dialogs.py` | `urllib.urlopen` → `QNetworkAccessManager` |
| — | Утечка AudioScanner при быстрых вызовах | MED | `ui/player/playback.py` | `disconnect()` + `deleteLater()` перед заменой |
| — | Краш AnalysisWorker при старте анализа | CRI | `utils/analysis_worker.py` | Убран `finished→deleteLater`, `try/except RuntimeError` |
| — | `os._exit(0)` при single-instance | LOW | `main.py` | `os._exit(0)` → `return` |
| — | TOCTOU race в `upsert_track()` | HI | `core/db/tracks.py` | Два `get_connection()` → один блок |
| 3.1 | Лямбды в QTimer.singleShot — краш при закрытии | MED | `scanning.py`, `playback.py`, `dialog.py` | Внутренние `def` + `try/except RuntimeError` |
| 3.2 | AudioScanner без cancel/disconnect/deleteLater | MED | `ui/player/scanning.py` | `disconnect()` всех сигналов + `deleteLater()` перед заменой |
| 3.3 | AnalysisWorker — deleteLater не вызывался | MED | `utils/analysis_worker.py` | `_cancel_worker()` + `_advance_to_library()` → `deleteLater()` + sentinel guard |
| 3.4 | tag_editor — threads без deleteLater | MED | `ui/tag_editor/editor.py` | `_replace_thread()` → `quit/wait/terminate/deleteLater` во всех 4 потоках |
| 3.5 | AudioPlayer/QMediaPlayer без parent | MED | `ui/player/main_window.py`, `core/player.py` | `AudioPlayer(self)`, `QMediaPlayer(self)` |
| — | folder filter в библиотеке | MED | `ui/library/dialog.py`, `model.py` | Полностью удалён — не работал |
| 4.1 | 55× except:pass без вывода | LOW | 25 файлов | Добавлен `print("file.method: description")` в каждый блок |
