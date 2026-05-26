# SonicFlame Player — Техническое описание проекта

![SonicFlame Player](SonicFlame.png)

## Краткое описание

Современный десктопный аудиоплеер на Python с графическим интерфейсом PySide6. Поддерживает воспроизведение MP3, FLAC, M4A/MP4 аудиофайлов с извлечением метаданных, обложек, библиотекой на SQLite, мини-виджетом для системного трея и субпроцессом библиотеки.

## Структура проекта

```
MusicPlayer2\
├── main.py                             # Точка входа (плеер + библиотека через --library)
├── requirements.txt                    # Зависимости
├── Sonic-Flame.ico                     # Иконка приложения
├── SonicFlame.png                      # Изображение для splash screen
├── SonicFlamePlayer_vision.png         # Концепт-арт приложения
├── SonicFlame.manifest                 # Манифест Windows (DPI-aware, supportedOS)
├── SonicFlame.spec                     # Спецификация PyInstaller
├── build.bat                           # Скрипт сборки
├── TECHNICAL.md                        # Этот файл
├── README.md                           # Документация пользователя
├── LICENSE.txt                         # GPL v3
├── version_info.txt                    # Версия для PE-ресурсов (PyInstaller)
├── res/                                # Ресурсы
│   ├── covers/                         # Фоновые изображения обложек (1.jpg..14.jpg)
│   └── genres/
│       ├── genre_groups.json           # Группы жанров для фильтрации
│       └── genre_map.json              # Маппинг жанров (ID3 → группы)
├── musicplayer/
│   ├── __init__.py
│   ├── config.py                       # Глобальные константы: APP_VERSION, ACCENT_COLOR, CACHE_DIR, пути кэша
│   ├── core/
│   │   ├── __init__.py
│   │   ├── normalize.py                # Нормализация метаданных (mutagen)
│   │   ├── audio_device_manager.py     # Управление устройствами вывода + автофолбэк
│   │   ├── media_keys.py               # Глобальные медиа-клавиши (RegisterHotKey)
│   │   ├── player.py                   # Обёртка над QMediaPlayer
│   │   ├── playlist.py                 # Управление плейлистом
│   │   ├── db/                         # SQLite библиотека
│   │   │   ├── __init__.py             # Обратная совместимость — экспорт всех функций
│   │   │   ├── connection.py           # Подключение к БД (пути из config)
│   │   │   ├── tracks.py               # CRUD операции с треками, извлечение метаданных
│   │   │   ├── favorites.py            # Операции с избранным
│   │   │   ├── cache.py                # Кэширование обложек
│   │   │   ├── folders.py              # Операции с папками
│   │   │   └── queries.py              # Фильтрация, сортировка, сложные запросы
│   │   ├── db.py                       # Обратная совместимость (импорт из пакета db/)
│   │   ├── db_cleaner.py               # Очистка БД от отсутствующих файлов
│   │   ├── ipc.py                      # IPC сервер и клиент для связи плеер ↔ библиотека
│   │   ├── settings.py                 # Постоянные настройки (JSON, пути из config)
│   │   ├── web_server.py               # HTTP сервер (aiohttp)
│   │   ├── web_api.py                  # API обработчики с валидацией
│   │   ├── web_template.py             # HTML шаблон веб-интерфейса
│   │   ├── recommendations.py          # Алгоритм подбора похожих треков
│   │   ├── smtc_manager.py             # SMTC — интеграция с системным оверлеем Windows
│   │   └── windows_sleep_blocker.py    # Предотвращение спящего режима во время воспроизведения
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── web_integration.py          # Qt-мост к веб-серверу (QObject + сигналы)
│   │   ├── library/                    # Модули библиотеки
│   │   │   ├── __init__.py             # Экспорт: LibraryDialog, LibraryModel, DataWorker, ArtistViewWidget
│   │   │   ├── types.py                # Track dataclass, константы колонок (HEADERS, COL_*)
│   │   │   ├── settings.py             # Сохранение ширины колонок (пути из config)
│   │   │   ├── worker.py               # DataWorker (generic worker thread)
│   │   │   ├── model.py                # LibraryModel + MoodStarDelegate
│   │   │   ├── dialog.py               # LibraryDialog (основной диалог)
│   │   │   ├── artist_view.py          # ArtistViewWidget (виджет "Исполнители")
│   │   │   ├── artist_card.py          # ArtistCardWidget (карточка исполнителя)
│   │   │   └── artist_worker.py        # ArtistProcessingWorker (пути из config)
│   │   ├── player/                     # Рефакторинг main_window.py — координатор и менеджеры
│   │   │   ├── __init__.py             # Реэкспорт MainWindow
│   │   │   ├── managers.py             # PlayerManagerBase — базовый класс (shared methods)
│   │   │   ├── main_window.py          # MainWindow — координатор (сборка UI, сигнальная маршрутизация)
│   │   │   ├── title_bar.py            # Кастомный заголовок окна (с кнопками и сортировкой)
│   │   │   ├── animation.py            # BlinkAnimation — мигание статуса при сканировании
│   │   │   ├── tray.py                 # TrayManager — системный трей и иконка
│   │   │   ├── scanning.py             # ScanningManager — логика сканирования папок
│   │   │   ├── playback.py             # PlaybackManager — воспроизведение, навигация, редактирование тегов
│   │   │   └── playlist_ops.py         # PlaylistManager — избранное, топ, артист, похожие треки
│   │   ├── controls.py                 # Контролы управления (transport, seek, volume)
│   │   ├── main_window.py              # Обратная совместимость (shim → ui.player.main_window)
│   │   ├── mini_widget.py              # Мини-плеер для системного трея
│   │   ├── playlist_view.py            # Плейлист с кастомным делегатом
│   │   ├── remove_track_dialog.py      # Диалог и функция удаления трека из библиотеки
│   │   ├── settings/                   # Диалог настроек (пакет)
│   │   │   ├── __init__.py             # Реэкспорт SettingsDialog
│   │   │   ├── dialog.py               # SettingsDialog — координатор (title bar, sidebar, status bar)
│   │   │   ├── constants.py            # ACCENT_PRESETS, FORBIDDEN_PORTS, format_size
│   │   │   ├── widgets.py              # ColorCircleButton, ClickableSlider, SpinnerWidget, TabButton
│   │   │   ├── page_main.py            # MainPage (папка + точность похожих)
│   │   │   ├── page_appearance.py      # AppearancePage (цвета, чекбоксы, opacity)
│   │   │   ├── page_webserver.py       # WebServerPage + PortValidator (сервер, порт, QR, удалённое закрытие)
│   │   │   ├── page_system.py          # SystemPage + CleanupWorker (сон, очистка БД)
│   │   │   └── page_about.py           # AboutPage (о программе, ссылки на GitHub/сайт)
│   │   ├── sidebar.py                  # Боковая панель (папки, избранное, топ, настройки)
│   │   ├── svg_icons.py                # SVG-иконки как строки
│   │   ├── accent_style.py             # Применение акцентного цвета к главному окну (findChildren)
│   │   ├── track_info.py               # Виджет обложки с градиентной тенью
│   │   ├── tag_editor/                 # Редактор тегов (разделённый на модули)
│   │   │   ├── __init__.py             # Реэкспорт для обратной совместимости
│   │   │   ├── base_dialog.py          # BaseFramelessDialog — базовый класс frameless-диалогов
│   │   │   ├── constants.py            # ID3_GENRES, COVER_SIZE, BRIGHT_COLORS
│   │   │   ├── api.py                  # iTunes/Deezer API функции (с логгированием)
│   │   │   ├── cover.py                # Генерация абстрактной обложки (RGBA, кросс-платформенные шрифты)
│   │   │   ├── cover_thread.py         # Поток поиска обложек (дедупликация через MD5)
│   │   │   ├── threads.py              # Потоки поиска треков, скачивания обложек и сохранения тегов (M4A/MP4)
│   │   │   ├── widgets.py              # LoadingBar, CoverDisplayLabel (с _is_generated_cover)
│   │   │   ├── dialogs.py              # TrackSearchResultsDialog, CoverSearchResultsDialog, CoverTile
│   │   │   ├── track_mover.py          # move_track_to_folder — перемещение трека в другую папку из редактора тегов
│   │   │   └── editor.py               # TagEditorDialog (наследует BaseFramelessDialog)
│   │   └── widgets/                    # Переиспользуемые виджеты
│   │       ├── __init__.py
│   │       ├── frameless_dialog.py     # FramelessDialog — базовый frameless-диалог с перетаскиванием
│   │       ├── folder_browse_dialog.py # FolderBrowseDialog — кастомный выбор папок (tree, quick filter, key folders)
│   │       └── styled_message_box.py   # StyledMessageBox — кастомный MessageBox (info/warning/error/question)
│   └── utils/
│       ├── __init__.py
│       ├── audio_scanner.py            # QThread сканер папок (sync с БД)
│       ├── analysis_worker.py          # Анализ аудио (librosa)
│       ├── color_extractor.py          # Извлечение доминантного цвета из обложки
│       └── helpers.py                  # Утилиты форматирования
└── .cache/                             # Данные приложения (создаются при первом запуске)
    ├── musicplayer.db                  # SQLite библиотека (WAL mode)
    ├── covers/                         # Обложки в формате WebP
    ├── artist_collages/                # Кеш коллажей Артистов для библиотеки
    ├── settings.json                   # Пользовательские настройки
    └── library_col_widths.json         # Ширина колонок библиотеки
```

## Requirements

**Python**: >=3.9 (для корректной работы многопоточного сканера)

| Пакет        | Версия   | Назначение                                    |
|--------------|----------|-----------------------------------------------|
| PySide6      | >=6.6    | GUI-фреймворк (Qt6 для Python)                |
| mutagen      | >=1.47   | Извлечение метаданных из аудиофайлов          |
| Pillow       | >=10.0   | Конвертация обложек в WebP                    |
| aiohttp      | >=3.9    | HTTP сервер для удалённого управления         |
| numpy        | >=1.24   | Численные расчёты (анализ аудио, цвет)        |
| librosa      | >=0.10.1 | Анализ аудио (BPM, energy, mood)              |
| qrcode[pil]  | >=7.4.2  | Генерация QR-кодов для веб-управления         |
| winrt-Windows.Media           | >=3.2.0  | SMTC — Media API                          |
| winrt-Windows.Media.Playback | >=3.2.0  | SMTC — Playback API                      |
| winrt-Windows.Storage.Streams | >=3.2.0  | SMTC — Streams API                       |
| winrt-Windows.Storage        | >=3.2.0  | SMTC — Storage API                       |
| winrt-Windows.Foundation     | >=3.2.0  | SMTC — Foundation API                    |
| winrt-Windows.UI.Core        | >=3.2.0  | SMTC — UI Core API                       |
| pyinstaller  | >=6.0    | Сборка в standalone .exe (опционально)        |

## Архитектура

### Core модули

#### `core/player.py` — AudioPlayer
Обёртка над `PySide6.QtMultimedia.QMediaPlayer`.

**Класс `AudioPlayer(QObject)`**:
- `_player: QMediaPlayer` — базовый медиаплеер
- `_audio_output: QAudioOutput` — аудиоустройство
- `_device_manager: AudioDeviceManager` — менеджер вывода звука
- **Сигналы**: `state_changed`, `position_changed`, `duration_changed`, `volume_changed`, `media_status_changed`, `error_occurred`
- **Методы**: `load_source()`, `play()`, `pause()`, `stop()`, `toggle_play_pause()`, `set_position()`, `set_volume()`, `get_position()`, `get_duration()`, `get_volume()`, `get_state()`, `is_playing()`, `set_audio_device()`, `get_audio_device_id()`

#### `core/audio_device_manager.py` — AudioDeviceManager
Управление выбором устройства вывода звука с автофолбэком.

**Класс `AudioDeviceManager(QObject)`**:
- `_requested_device_id: str | None` — выбранное пользователем устройство (не сбрасывается при отключении)
- `_current_device_id: str` — фактически активное устройство
- Таймер 1с: каждый тик проверяет доступность запрошенного устройства
- Если устройство отключено — фолбэк на системное `defaultAudioOutput()`
- При повторном подключении — автоматическое переключение обратно
- **Сигналы**: `device_changed(str)` — новое ID устройства
- **Методы**: `set_user_device(device_id)`, `get_user_device()`, `get_current_device_id()`, `create_audio_output(parent)`, `enumerate_devices()` (статический)

#### `core/playlist.py` — Playlist

### Управление треками

**Класс `Playlist`**:
- `_tracks: List[TrackInfo]` — текущий список треков (может быть отсортирован или перемешан)
- `_original_order: List[TrackInfo]` — исходный порядок треков
- `_current_index: int` — индекс текущего трека
- `_repeat_mode: str` — `"none"`, `"all"`, `"one"`
- `_sort_mode: str` — режим сортировки (`artist`, `title`, `newest`, `shuffle`)
- **Методы**: `set_tracks()`, `add_tracks()`, `clear()`, `get_tracks()`, `get_current_track()`, `get_current_index()`, `get_track_count()`, `play_track_at()`, `play_next()`, `play_previous()`, `set_repeat_mode()`, `set_sort_mode()`, `force_sort()`

**Сортировка**
- `set_sort_mode(mode)` — установка режима (`artist`/`title`/`newest`), вызывает `_apply_sort()`
- `_apply_sort()` — сортировка `_tracks` по текущему `_sort_mode`, сохраняя текущий трек
- `load_tracks_no_sort(tracks)` — загрузка без сортировки (для bulk-загрузки)
- `force_sort(mode)` — принудительная сортировка игнорирует флаги

#### `core/db/` — SQLite библиотека (рефакторинг пакета)

Модуль управляет базой данных SQLite, а также содержит всю логику для извлечения метаданных из аудиофайлов (`extract_metadata`) и структуру данных `TrackInfo`. После рефакторинга разделён на специализированные модули:

- `connection.py` — управление подключением, конфигурация, валидация путей
- `tracks.py` — CRUD операции, извлечение метаданных, TrackInfo
- `favorites.py` — работа с избранным
- `cache.py` — кэширование обложек и исполнителей
- `folders.py` — операции с папками
- `queries.py` — фильтрация, пагинация, сложные запросы
- `__init__.py` — обратная совместимость (все функции экспортируются)

Для обратной совместимости старый импорт `from musicplayer.core.db import ...` продолжает работать.

### Структура БД (`.cache/musicplayer.db`, WAL mode):

**Таблица `library`**:

| Колонка | Тип | Описание |
|---------|-----|----------|
| filepath | TEXT PK | Полный путь к файлу |
| mtime | REAL | Время изменения файла (для отслеживания изменений) |
| title | TEXT | Название трека |
| artist | TEXT | Исполнитель |
| album | TEXT | Альбом |
| duration | REAL | Длительность в секундах |
| has_cover | INTEGER | Есть ли обложка (0/1) |
| genre | TEXT | Жанр |
| is_lossless | INTEGER | Lossless формат (0/1) |
| play_count | INTEGER | Счётчик воспроизведений |
| bitrate | INTEGER | Битрейт в кбит/с |
| tempo | REAL | Темп (BPM) |
| energy | REAL | Энергичность (0-1) |
| mood | REAL | Настроение (0-1) |

**Таблица `favorites`**:

| Колонка | Тип | Описание |
|---------|-----|----------|
| filepath | TEXT PK | Путь к избранному треку |

**Таблица `folders`**:

| Колонка | Тип | Описание |
|---------|-----|----------|
| folder_path | TEXT PK | Нормализованный путь к папке (os.sep) |
| track_count | INTEGER | Количество треков в папке |

**Таблица `artists_cache`**:

| Колонка | Тип | Описание |
|---|---|---|
| artist_name | TEXT PK | Имя исполнителя |
| track_count | INTEGER | Количество треков |
| collage_path | TEXT | Путь к файлу коллажа |

**Обложки** хранятся отдельно в `.cache/covers/{md5_пути}.webp` (конвертация через Pillow, quality=85). 

**Ключевые функции**:
- `init_db()` — инициализация/миграция схемы
- `upsert_track(track, mtime)` — вставка/обновление трека (сохраняет play_count)
- `delete_track(filepath)` — удаление трека + избранного + файла обложки
- `get_track(filepath)` — получение трека с загрузкой обложки
- `get_all_library_tracks()` / `get_all_library_tracks_light()` — все треки
- `get_tracks_by_folder(folder_path)` — треки конкретной папки
- `get_tracks_by_artist(artist_name)` — все треки исполнителя
- `get_folder_filepaths(folder_path)` — множества путей папки (для sync)
- `delete_folder_tracks(folder_path)` — очистка папки
- `increment_play_count(filepath)` — инкремент счётчика
- `is_favorite()` / `toggle_favorite()` / `get_favorite_tracks()` / `get_favorite_filepaths()`
- `get_top_tracks(limit=100)` — топ по play_count
- `ensure_cover_for_track(filepath)` — гарантирует наличие обложки (извлекает если нет)
- `upsert_folder(folder_path, track_count)` — запись папки в `folders` (путь нормализуется через `normalize_path`)
- `get_all_folders()` — все папки с счётчиками треков
- `get_db_mtime()` — mtime файла БД (для умного обновления библиотеки)
- `normalize_path(path_str)` — нормализация разделителей пути к `os.sep`
- `update_artists_cache(artists_data)` — пакетное обновление кеша исполнителей
- `get_cached_artists()` — получение всех исполнителей из кеша
- `get_artists_cache_status()` — проверка актуальности кеша исполнителей (сравнение mtime БД и файла кеша)

**Безопасность БД**:
- Валидация параметров `offset`/`limit`: ограничение диапазона (1-500 для limit, 0-1000000 для offset)
- Валидация `ORDER BY`: whitelist для столбцов сортировки, защита от SQL-инъекций
- Экранирование SQL LIKE: функция `_escape_like_pattern()` экранирует `%`, `_`, `\`
- Валидация путей: `is_safe_filepath()` проверяет path traversal и containment в music_folder
- Применяется ко всем функциям: `extract_metadata`, `upsert_track`, `delete_track`, `is_favorite`, `toggle_favorite` и др.

**Умный sync при сканировании** (`audio_scanner.py` + `db/`):
1. Сканирует папку на `.mp3`, `.flac`, `.m4a`, `.mp4`
2. Сравнивает файлы на диске с записями в БД (`get_folder_filepaths`)
3. **Отсутствующие файлы** — удаляет из БД и кеша обложек
4. **Изменённые файлы** (mtime > db_mtime) — переизвлекает метаданные
5. **Неизменённые** — использует кеш из БД
6. **Новые файлы** — извлекает метаданные, добавляет в БД
7. После сканирования вызывается `upsert_folder()` — путь нормализуется, количество треков сохраняется в таблицу `folders`
8. Каждый трек эмитится через `track_scanned` для динамического добавления в UI

#### `core/settings.py` — AppSettings
Хранение настроек в `settings.json` (путь из `config.SETTINGS_FILE`).

**Функции сортировки** (строки 44-64):
- `ensure_default_playlist_sort_mode()` — создаёт `playlist_sort_mode: "artist"` при первом запуске
- `get_playlist_sort_mode()` — возвращает текущий режим из конфига
- `set_playlist_sort_mode(mode)` — сохраняет режим в конфиге

| Настройка | Тип | Описание |
|-----------|-----|----------|
| last_folder | str | Последняя открытая папка |
| last_track | str | Последний воспроизведённый трек |
| music_folder | str | Корневая папка с музыкой |
| accent_color | str | HEX акцентного цвета |
| favorites_mode | bool | Режим избранного активен |
| top_mode | bool | Режим топа активен |
| repeat_mode | str | none / all / one |
| volume | float | 0.0–1.0 |
| mini_widget_on_minimize | bool | Сворачивать в трей с мини-виджетом |
| mini_widget_opacity | int | Прозрачность фона мини-виджета (0–80, по умолч. 40) |
| dynamic_color | bool | Динамический цвет обложки |
| playlist_type | str | Тип плейлиста (Folder/Favorites/Top/Playlist) |
| web_server_enabled | bool | Веб-сервер включён |
| web_server_port | int | Порт веб-сервера (по умолчанию 8080) |
| playlist_sort_mode | str | Режим сортировки плейлиста (artist/title/newest/shuffle) |
| similarity_precision | int | Точность подбора похожих треков (0–20, по умолч. 10) |
| allow_remote_shutdown | bool   | Разрешить удалённое закрытие программы |
| prevent_sleep        | bool   | Блокировать спящий режим во время воспроизведения |
| audio_output_device  | str    | ID выбранного устройства вывода (None = по умолчанию) |

### Модуль для подбора похожих треков на основе различных критериев.
#### `core/db_cleaner.py` — Database Cleaner
Модуль для очистки базы данных от треков, файлы которых больше не существуют на диске.

**Функции**:
- `cleanup_missing_tracks()` — проверяет все записи в БД, удаляет отсутствующие файлы и их обложки
- Выводит в консоль количество удалённых записей

**Особенности**:
- Использует `get_all_library_tracks_light()` для получения всех треков без загрузки обложек
- Удаляет запись из БД через `delete_track()` (включает удаление из избранного и кеша обложек)
- Логирует результат в формате `[DB Cleaner] Removed N missing tracks from database`

#### `core/recommendations.py` — Recommendations

Алгоритм вычисляет взвешенную сумму схожести треков по четырём метрикам + штраф за общего исполнителя.

**Веса метрик:**
| Метрика | Вес |
|---------|-----|
| Жанр (`WEIGHT_GENRE`) | 0.35 |
| Темп (`WEIGHT_TEMPO`) | 0.30 |
| Энергия (`WEIGHT_ENERGY`) | 0.20 |
| Настроение (`WEIGHT_MOOD`) | 0.15 |
| Штраф за исполнителя (`PENALTY_ARTIST`) | −0.10 |

**Жанр**: точное совпадение → 1.0, совпадение группы жанров → 0.9, частичное → boost 1.15.
**Аудио-метрики**: нормализация в диапазон [0, 1], затем линейный спад `max(0, 1 - diff / threshold)` с порогом `METRIC_SINGLE_DIM_THRESHOLD_FOR_SIMILARITY_SCORE = 0.14`.

**Динамический порог отбора**:
Значение `min_similarity_threshold` вычисляется по формуле: `SIMILARITY_THRESHOLD_BASE + (similarity_precision / 100)`, где:
- `SIMILARITY_THRESHOLD_BASE = 0.60` — базовая нижняя планка
- `similarity_precision` — настройка пользователя (0–20, по умолч. 10)

При `similarity_precision = 10` порог = 0.70; при `similarity_precision = 0` порог = 0.60; при `similarity_precision = 20` порог = 0.80.

**Ключевые функции:**
- `calculate_similarity(track1, track2) → float`: Балл сходства [0.0, 1.0].
- `find_similar_tracks(current_track, all_tracks, limit=10, min_similarity_threshold=None) → List[TrackInfo]`:
  - Если порог не передан, вычисляется динамически из настроек.
  - Отбирает треки с score ≥ порога, сортирует по убыванию, берёт top `limit`, перемешивает.
- `get_similarity_threshold() → float`: Вычисляет текущий порог из `settings.json`.

#### `core/media_keys.py` — Media Keys Handler
Обработчик глобальных медиа-клавиш (Play/Pause, Next, Previous) для Windows.

**Функции**:
- `_install_media_keys_filter(hwnd, callback)` — регистрация горячих клавиш, callback получает `"play_pause"`, `"next_track"`, `"prev_track"`
- `create_media_keys_handler(hwnd, player, on_next, on_previous)` — создание обработчика с удобным API (принимает player и callbacks)

**Особенности**:
- Использует Windows RegisterHotKey API + QAbstractNativeEventFilter
- Работает глобально даже при свёрнутом в трей окне
- Дедупликация событий (150мс)
- Автоматическая отписка при выходе

#### `core/web_server.py` — WebServer (координатор)
Веб-сервер для удалённого управления плеером через браузер. После рефакторинга разделён на три модуля:

- `web_server.py` — координатор, инициализация, маршруты
- `web_api.py` — обработчики API эндпоинтов с валидацией
- `web_template.py` — HTML/CSS/JS веб-интерфейса

**Особенности**:
- HTTP-сервер на aiohttp (порт настраивается, по умолчанию 8080)
- Синхронизация состояния плеера каждые 1000мс
- Раздельные API: `/api/playing_data` (только статус) + `/api/track` (информация о треке)
- Обложка загружается отдельно при смене трека (оптимизация трафика)
- Корректная работа с плейлистами "Похожие треки", "Избранное", "Топ" — используется актуальный порядок треков из виджета, а не из core playlist (который может быть отсортирован)
- Управление воспроизведением через GET-запросы без передачи данных (next, previous, play_favorites, play_top)
- **Безопасность**: валидация ввода, защита от SQL-инъекций, path traversal protection, security headers
- **IP-фильтрация**: доступ к API разрешён только с локальных/приватных адресов (127.0.0.1, 10.x.x.x, 172.16-31.x.x, 192.168.x.x, ::1)

**API эндпоинты**:

| Метод | Путь | Описание |
|------|------|----------|
| GET | `/` | Веб-интерфейс (HTML) |
| GET | `/Sonic-Flame.ico` | Favicon |
| GET | `/api/status` | Статус воспроизведения (playing, position, duration, volume, repeat, **sort_mode**) |
| GET | `/api/track` | Информация о текущем треке (title, artist, album, duration, **genre, bitrate**, cover base64, is_favorite, playlist_title) |
| GET | `/api/playlist` | Плейлист (массив треков: title, artist, album, duration, filepath) |
| GET | `/api/accent_color` | Текущий акцентный цвет |
| GET | `/api/playing_data` | Статус + current_index + current_track_filepath + is_favorite + accent_color + **sort_mode** |
| GET | `/api/folders` | Список папок (path, name, track_count). Включает "Вся музыка" с общим количеством треков |
| GET | `/api/check` | Имя компьютера (computer_name) |
| GET | `/api/next` | Следующий трек |
| GET | `/api/previous` | Предыдущий трек |
| GET | `/api/play_favorites` | Загрузить плейлист "Избранное" |
| GET | `/api/play_top` | Загрузить плейлист "Топ" |
| GET | `/api/play_similar` | Загрузить плейлист похожих треков для текущего трека |
| GET | `/api/play_artist` | Загрузить все треки исполнителя текущего трека |
| GET | `/api/toggle_repeat` | Переключить режим повтора (none → all → one → none) |
| POST | `/api/play` | Воспроизведение |
| POST | `/api/pause` | Пауза |
| POST | `/api/seek` | Перемотка (`{"position": int}` в мс) |
| POST | `/api/volume` | Громкость (`{"value": float}` 0.0–1.0) |
| POST | `/api/play_track` | Воспроизвести трек по индексу (`{"index": int}`) |
| POST | `/api/play_folder` | Воспроизвести папку (`{"path": str}`) |
| POST | `/api/toggle_favorite` | Переключить статус "избранное" для текущего трека |
| POST | `/api/shutdown` | Закрыть программу (если `allow_remote_shutdown: true`) |

**Безопасность API**:
- Валидация `volume`: ограничение 0.0-1.0
- Валидация `seek`: только неотрицательные integers
- Валидация `index`: проверка диапазона плейлиста
- Валидация `path`: защита от path traversal
- Security middleware: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- Ограничение методов: только GET и POST
- Скрытие filepath в плейлисте (не раскрываются полные пути)

**Ответ `/api/playing_data`**:
```json
{
  "status": {"playing": true, "position": 50000, "duration": 180000, "volume": 0.7, "repeat": "none"},
  "current_index": 0,
  "current_track_filepath": "C:/Music/track.mp3",
  "is_favorite": true,
  "accent_color": "#ed6a02",
  "sort_mode": "artist"
}
```

**Ответ `/api/track`**:
```json
{
  "title": "Track Name",
  "artist": "Artist",
  "album": "Album",
  "duration": 180,
  "genre": "Rock",
  "bitrate": 320,
  "is_favorite": true,
  "cover": "base64encodedwebp...",
  "playlist_title": "Похожие треки (Track Name)"
}
```

**Ответ `/api/folders`**:
```json
[
  {"path": "C:/Music", "name": "Вся музыка", "track_count": 1250},
  {"path": "C:/Music/Rock", "name": "Rock", "track_count": 320},
  {"path": "C:/Music/Pop", "name": "Pop", "track_count": 180}
]
```

**Логика работы**:
1. `updateStatus()` polling каждые 1000мс → `/api/playing_data`
2. При смене `current_index` → вызов `updatePlaylist()` + `updateTrackInfo()`
3. `updateTrackInfo()` → `/api/track` (загружает cover ~200KB только при смене трека)

**Веб-интерфейс**:
- Адаптивная вёрстка (desktop + mobile)
- Обложка (base64 webp), название, артист, альбом
- Seek bar, время слева/справа
- Плейлист с автоскроллом
- SVG-кнопки управления (включая "Избранное")
- Offline detection с overlay "Плеер выключен"
- Sticky-плеер при скролле плейлиста

**Интеграция**:
- Включение/порт в настройках (`ui/settings/page_webserver.py`)
- Синхронизация состояния через `update_web_server_state()`
- Qt-колбеки через сигналы
- Новый сигнал `play_similar_requested` для загрузки похожих треков
- Сигнал `shutdown_requested` для удалённого закрытия программы через `POST /api/shutdown`

### UI модули

#### `ui/web_integration.py` — WebIntegration
Вынесенный из main_window.py модуль для управления веб-сервером.

**Класс `WebIntegration(QObject)`**:
- `_main_window` — ссылка на MainWindow
- `_web_server` — экземпляр WebServer
- `_web_last_track_fp` — отслеживание смены трека

**Методы**:
- `start(port)` — запуск веб-сервера
- `stop()` — остановка веб-сервера
- `is_running()` — проверка состояния
- `set_enabled(enabled)` — включение/выключение из настроек
- `set_port(port)` — смена порта с перезапуском
- `update_playlist()` — синхронизация плейлиста
- `update_favorites()` — синхронизация избранного
- `update_state()` — синхронизация состояния плеера

**Внутренние методы**:
- `_wire_signals()` — подключение сигналов WebServer к методам MainWindow
- `_on_play_folder()` — обработка воспроизведения папки
- `_on_toggle_favorite()` — обработка избранного
- `_on_toggle_repeat()` — обработка повтора
- `_on_shutdown()` — обработка удалённого закрытия (`QApplication.quit()`)

**Изменение громкости через API**:
- `volume_requested` подключён к `_on_volume_changed` (а не напрямую к `player.set_volume`), что обеспечивает сохранение уровня громкости в конфиг (`settings.volume`)

#### `ui/main_window.py` — MainWindow
Главное окно приложения (координатор всех компонентов).

**Рефакторинг**:
- `TitleBarWidget` вынесен в `ui/player/title_bar.py` — кастомный заголовок с SVG-иконкой, статусом сканирования, выпадающим списком сортировки и кнопками сворачивания/закрытия
- `MissingTrackDialog` и `remove_track_from_library` вынесены в `ui/remove_track_dialog.py`

**Сортировка треков (UI)**:
- В титл-баре добавлен выпадающий список (right-aligned) с четырьмя режимами: По исполнителю, По названию, По новизне, Перемешать.
- Значение режима хранится в настройках (`.cache/settings.json`) в поле `playlist_sort_mode`.
- При смене режима через UI новый режим сохраняется в конфиге и применяется ко всем плейлистам.
- При загрузке новой папки сохранённый режим сортировки применяется автоматически (не сбрасывается).
- При смене режима UI перерисовывает плейлист, сохраняя подсветку активного трека.

**Особенности**:
- `Qt.FramelessWindowHint` + `Qt.WA_TranslucentBackground` — безрамочное окно с прозрачностью
- Кастомный title bar (`TitleBarWidget`) с динамическим обновлением статуса (название папки/плейлиста, количество треков)
- Закруглённые углы (12px) через `paintEvent()`
- Перетаскивание окна мышью за title bar
- **Системный трей**: `QSystemTrayIcon` с контекстным меню (Показать/Выход)
- **Мини-виджет**: `MiniPlayerWidget` при сворачивании в трей (если включено в настройках)
- **Обработка удаления трека**: использует `remove_track_from_library` из `ui/remove_track_dialog.py`
- **Библиотека-субпроцесс**: запуск `main.py --library` через `subprocess.Popen`

**Поиск похожих треков (UI)**:
- Обрабатывает запрос от кнопки "Поиск похожих треков" в `ControlsWidget` и из веб-интерфейса (`/api/play_similar`).
- Получает текущий трек из `playlist_widget.get_view_tracks()` по `self._current_playing_filepath` (не из core playlist, т.к. тот может быть отсортирован).
- Использует `core/recommendations.py` для поиска похожих.
- Загружает результаты в текущий плейлист (до 100 треков).
- Обновляет тайтлбар, отображая "Похожие треки (Название трека)" и количество найденных треков.

**Все песни исполнителя (UI)**:
- Кнопка "Все песни исполнителя" в левом краю `ControlsWidget`.
- При нажатии загружает все треки первого (основного) исполнителя текущего трека.
- Использует `get_tracks_by_artist()` из БД.
- Загружает результат в плейлист с заголовком — именем исполнителя.

**Макет**:
```
+--------------------------------------------------------+
| [Icon] Music Player  [Folder/Status] [─] [✕]           |  ← Title bar (40px)
+--------------------------------------------------------+
|  [Sidebar] |  TrackInfo   |   Playlist                 |
|  (60px)    |  Widget       |   Widget                  |  ← Middle (stretch 1)
|            |  (обложка)    |   (плейлист)              |
+--------------------------------------------------------+
|  Seek bar  [0:00 ━━━━━━━━━━ 3:45]                      |
|  [📁] [🔀] [⏮] [▶/⏸] [⏭] [🔁] [🔊] [====] [♡]  |  ← Controls
+--------------------------------------------------------+
```

**Сворачивание в трей** (если `mini_widget_on_minimize`):
- `showMinimized()` переопределён — вместо минимизации в панель задач окно скрывается (`hide()`)
- Появляется иконка в системном трее
- Открывается мини-виджет в правом нижнем углу
- Окно библиотеки закрывается

**Воспроизведение отсутствующих файлов**:
- При `_play_track_at_view_index()` проверяется `os.path.exists(track.filepath)`
- Если файл отсутствует — диалог подтверждения удаления
- При подтверждении: удаление из БД, кеша обложек, текущего плейлиста
- UI автоматически обновляется

**Библиотека как субпроцесс** (`--library` флаг):
- Запускается тот же `main.py` с аргументом `--library` (в frozen — тот же `.exe`)
- IPC через выделенные классы `IPCServer` и `IPCClient` в `core/ipc.py`
- Использует `QLocalSocket` с именем `SonicFlamePlayerIPC_v2`
- Поддержка автоматического переподключения клиента (таймер 500мс)
- Имя сервера: `SonicFlamePlayerIPC_v2`

**Акцентный цвет** — загружается из настроек ДО построения UI, применяется ко всему интерфейсу через `config.ACCENT_COLOR`

**Интеграция с веб-сервером**:
- Вынесена в отдельный класс `WebIntegration` (`ui/web_integration.py`)
- Инициализируется в `__init__`: `self._web_integration = WebIntegration(self)`
- Методы MainWindow вызывают `_web_integration.update_playlist()`, `_web_integration.update_state()`, `_web_integration.update_favorites()`
- Настройки веб-сервера подключены напрямую: `dialog.web_server_toggled.connect(self._web_integration.set_enabled)`

**Медиа-клавиши**:
- Использует `create_media_keys_handler(hwnd, player, on_next, on_previous)` из `core/media_keys.py`
- Упрощённая инициализация в `_setup_media_keys()`

#### `ui/player/title_bar.py` — TitleBarWidget

Вынесенный из main_window.py кастомный заголовок окна.

**Компоненты**:
- Иконка приложения (SVG музыкальная нота)
- Заголовок "SonicFlame Player"
- `playlist_title_label` — название текущего плейлиста/папки
- `sep_label` — разделитель (•)
- `scanning_status_label` — статус сканирования/загрузки
- Выпадающий список сортировки (По исполнителю, По названию, По новизне, Перемешать)
- Кнопки минимизации и закрытия

**Сигналы**:
- `sort_mode_changed(str)` — при изменении режима сортировки

**Методы управления**:
- `set_playlist_title(title)` — установить название плейлиста
- `set_show_separator(show)` — показать/скрыть разделитель
- `set_scanning_status(text, visible)` — установить текст статуса
- `set_scanning_status_style(style)` — установить стиль статуса
- `hide_scanning_status()` — скрыть статус
- `set_sort_mode(mode)` — установить режим сортировки
- `update_close_button_color(color)` — обновить цвет кнопки закрытия

#### `ui/remove_track_dialog.py` — MissingTrackDialog + remove_track_from_library

Вынесенные из main_window.py диалог и функция для удаления треков.

**MissingTrackDialog**:
- Диалог при отсутствии файла трека
- Показывает информацию о треке (название, артист, имя файла)
- Кнопки "Да"/"Нет" для удаления из библиотеки

**remove_track_from_library(filepath, playlist_widget, playlist, main_window)**:
- Удаляет трек из БД (`delete_track`)
- Обновляет плейлист виджета
- Очищает обложку из кеша
- Сбрасывает состояние воспроизведения в main_window

#### `ui/accent_style.py` — Accent Style Applier

**`apply_accent_to_main_window(window, settings_dialog=None)`** — обновляет акцентный цвет во всех виджетах главного окна без перезагрузки UI.

**Механизм обновления**:
- Прямые ссылки: `window.controls_widget`, `window.sidebar`, `window.playlist_widget`, `window.track_info_widget` — вызывают `apply_accent_color(accent)` на каждом
- `findChild(QWidget, "main_container")` — обновление QSS-границы контейнера (border с alpha=0.1)
- `findChildren(FolderBrowseDialog)` — обновление открытого `FolderBrowseDialog` (если есть): вызывает `dlg.apply_accent_color()` → `super().apply_accent_color()` (обновляет close button + перерисовывает акцентную рамку) → обновление всех внутренних виджетов диалога
- Slider'ы: пересоздание QSS через `_get_style()`
- Title bar close button: обновление стиля
- Перерисовка playlist viewport
- `settings_dialog.apply_accent_color(accent)` — если диалог открыт

#### `ui/track_info.py` — TrackInfoWidget + AlbumArtWidget
**`AlbumArtWidget`**:
- Размер: 375x375–525x525px
- `paintEvent()`: чёрный фон → размытая копия с градиентной маской → чёткая обложка (opacity 0.85) → внутренняя чёрная тень (60px)
- SVG-плейсхолдер (музыкальная нота) когда нет обложки
- **Звезда настроения**: `QLabel` с иконкой звезды накладывается поверх `AlbumArtWidget`, чтобы обеспечить видимость поверх заглушки. Цвет звезды (`tempo`, `energy`, `mood`) вычисляется в `utils/helpers.py`.

**`TrackInfoWidget`**:
- `title_label` — 18px, акцентный цвет, bold
- `artist_label` — 18px, белый, bold
- `album_label` — 12px, серый (#AAAAAA)

#### `ui/playlist_view.py` — PlaylistWidget + PlaylistDelegate + PlaylistListWidget

**`PlaylistDelegate`**:
- Кастомная отрисовка через `paint()`
- **Текст**: артист (10px, полупрозрачный белый ~70%, белый при воспроизведении), название (11px, bold, белый, акцентный при воспроизведении)
- **Бейджи** (справа налево): длительность, жанры, корона (lossless), сердце (избранное)
- Высота элемента: 52px

**`PlaylistListWidget`**:
- Зонная обработка кликов: текст → воспроизведение, сердце → избранное, бейджи → редактор тегов
- Сигналы: `track_selected`, `heart_clicked`, `badge_clicked`

**`PlaylistWidget`**:
- `_full_tracks` — все треки из папки
- `_view_tracks` — текущий отображаемый набор (может быть отфильтрован — избранное, топ)
- `show_favorites_only()` / `show_full_playlist()`
- `update_track_data(old_fp, new_track)` — обновление метаданных без пересканирования

**Метод `resort_current_view(mode)`** (`playlist_view.py:631`):
- Пересортировка текущего вида по режиму (`artist`/`title`/`newest`)
- Сохраняет подсветку активного трека

**`FavoritesManager`** — обёртка над `db.py` функциями избранного

#### `ui/controls.py` — ControlsWidget

**Компоненты**:
- Seek slider + time labels (0:00 / 3:45)
- Transport: prev, play/pause (58×58px, круглая), next, repeat (none→all→one), кнопка "Все песни исполнителя" (левый край), кнопка "Поиск похожих треков"
- Volume: icon (mute toggle) + slider
- Heart button (избранное для текущего трека)

**SeekSlider**: кастомный клик/drag для seek, `_is_user_interacting` предотвращает feedback loop

#### `ui/sidebar.py` — SideBarWidget

Боковая панель (ширина ~60px):
- 📁 Открыть папку
- 🎵 Вся музыка — загружает корневую папку (`music_folder`) из конфига без диалога
- ♡ Избранное (toggle)
- ⭐ Топ (toggle)
- ⚙ Настройки
- 📚 Библиотека (субпроцесс)

**Сигналы**: `folder_open_requested`, `all_music_requested`, `favorites_toggled`, `top_requested`, `playlist_type_changed`, `settings_requested`, `library_requested`

#### `ui/settings/` — Пакет настроек (рефакторинг)

Диалог настроек разделён на пакет `ui/settings/` для лучшей организации:

**`dialog.py`** — `SettingsDialog` (координатор):
- Title bar (иконка, заголовок, кнопка закрытия)
- Sidebar с `TabButton` (анимированное переключение: серый → акцентный, ховер → белый)
- Status bar (статистика библиотеки: треков, кеш обложек справа)
- Создаёт 5 страниц-виджетов и соединяет их сигналы

**`widgets.py`** — переиспользуемые виджеты:
- `ColorCircleButton` — кружок выбора акцентного цвета
- `ClickableSlider` — QSlider с click-to-seek
- `SpinnerWidget` — анимированный спиннер
- `TabButton` — кнопка вкладки с QVariantAnimation (плавная смена цвета)

**`page_main.py`** — MainPage:
- **Корневая папка** — кнопка с путём (красная рамка если не задана)
- **Точность подбора похожих** — `ClickableSlider` (0–20)

**`page_appearance.py`** — AppearancePage + `TallItemDelegate`:
- **Акцентный цвет** — 15 пресетов (кружки), включая Slate (`#607884`)
- **Динамический цвет из обложки** — QCheckBox
- **Мини-виджет при сворачивании** — QCheckBox + QComboBox прозрачности (0–80, `TallItemDelegate` для высоты + `QAbstractItemView::item:selected/hover` с акцентным цветом)

**`page_webserver.py`** — WebServerPage + `PortValidator`:
- **Веб-сервер** — QCheckBox включения
- **Порт** — `QLineEdit` с `PortValidator` (1024–65535, запрещены 21/22/80/443). Debounce 2с, красный текст при ошибке, спиннер
- **QR-код** — генерация через библиотеку `qrcode`
- **Удалённое закрытие** — QCheckBox `allow_remote_shutdown`, отключён если сервер выключен

**`page_system.py`** — SystemPage + `CleanupWorker`:
- **Блокировать сон** — QCheckBox
- **Устройство вывода звука** — QComboBox со списком доступных устройств + "По умолчанию". Стилизован через `QAbstractItemView::item:selected/hover` с акцентным цветом. Использует `TallItemDelegate` для высоты элементов.
- **Чистка мусора в БД** — кнопка, запускает `CleanupWorker` в отдельном потоке; результат (количество удалённых треков) выводится на самой кнопке на 3 секунды

**`page_about.py`** — AboutPage:
- **Заголовок** — название приложения и версия акцентным цветом
- **Описание "от автора"**
- **Иконка** — музыкальная нота (128×128, прозрачный фон, акцентный цвет), расположена под текстом
- **Ссылки внизу** — GitHub (белая плашка + чёрный текст) и Сайт проекта (оранжевая плашка `#ed6a02` + белый текст), в один ряд с отступом 100px

#### `ui/library/` — Модули библиотеки

Рефакторинг: код библиотеки вынесен в отдельную папку `ui/library/` для лучшей организации и поддержки.

**Основной импорт**: `from musicplayer.ui.library import LibraryDialog`

##### `ui/library/dialog.py` — LibraryDialog
Диалог библиотеки (запускается как отдельный процесс):
- **Вкладки**: Интерфейс разделен на две вкладки: "Треки" и "Исполнители".
- **Вкладка "Треки"**:
    - Таблица всех треков с пагинацией и виртуальной моделью для быстрой прокрутки.
    - **Звезда настроения**: Колонка "★" с кастомным делегатом `MoodStarDelegate`.
    - Редактирование тегов, воспроизведение, открытие папки.
    - **Фильтр папок** — выпадающий список всех папок с количеством треков.
    - **Фильтр жанров** — выпадающий список всех уникальных жанров.
- **Вкладка "Исполнители"**: содержит `ArtistViewWidget` (загрузка при первом открытии).
- **IPC с основным процессом**: Двусторонняя связь для воспроизведения треков, артистов и синхронизации UI.
- **Умное обновление**: `refresh_data()` проверяет `get_db_mtime()` — перезагружает данные только если БД изменилась.

##### `ui/library/model.py` — LibraryModel + MoodStarDelegate
- `LibraryModel`: Виртуальная модель с постраничной загрузкой (PAGE_SIZE=250). Пагинация на уровне БД. Поддержка фильтров: поиск, жанр, папка, избранное.
- `MoodStarDelegate`: Кастомная отрисовка звезды настроения в таблице.

##### `ui/library/types.py` — Типы и константы
- `Track`: dataclass для отображения треков в UI (`__slots__` для оптимизации памяти)
- Константы колонок: `COL_TITLE`, `COL_ARTIST`, `COL_ALBUM`, `COL_GENRE`, `COL_FOLDER`, `COL_DURATION`, `COL_BITRATE`, `COL_PLAY_COUNT`, `COL_FAVORITE`, `COL_MOOD`, `COLUMN_COUNT`
- `HEADERS`: Заголовки столбцов таблицы

##### `ui/library/worker.py` — DataWorker
Универсальный `QThread` для фоновых операций с БД. Принимает функцию и её аргументы, возвращает результат через сигнал `results_ready`.

##### `ui/library/settings.py` — Настройки библиотеки
Сохранение и загрузка ширины колонок таблицы в `.cache/library_col_widths.json`.

##### `ui/library/artist_view.py` — ArtistViewWidget
Основной виджет для вкладки "Исполнители".
- **Состояния**: `QStackedWidget` — спиннер "Загрузка..." или сетка карточек.
- **Кеширование**: `load_if_needed()` проверяет `db.get_artists_cache_status()`, при необходимости запускает `ArtistProcessingWorker`.
- **Адаптивная сетка**: `QGridLayout` с автоматическим пересчётом колонок при resize.
- **Сигналы**: `artist_play_requested` при клике на карточку.

##### `ui/library/artist_card.py` — ArtistCardWidget
Виджет карточки исполнителя.
- **Визуализация**: Коллаж из 4 обложек (или плейсхолдер), имя артиста, количество треков.
- **Анимация**: `QPropertyAnimation` для плавного изменения цвета текста и рамки при наведении.

##### `ui/library/artist_worker.py` — ArtistProcessingWorker
Фоновый `QThread` для обработки данных исполнителей.
- **Агрегация**: Группировка треков по основному исполнителю (первому в списке при множественных).
- **Фильтрация**: Минимум 3 трека для отображения.
- **Генерация коллажей**: До 4 обложек → коллаж 2x2, сохраняется в `.cache/artist_collages/`.
- **Сигнал**: `artist_ready` при готовности каждого исполнителя (динамическое добавление в UI).
- **Кеширование**: Результат сохраняется в таблицу `artists_cache` БД.

#### `ui/tag_editor/` — Редактор тегов (пакет)

Редактор тегов с расширенными возможностями (mutagen), разделён на модули:

##### `base_dialog.py` — BaseFramelessDialog
Базовый класс для frameless-диалогов. Содержит:
- `paintEvent` с акцентной рамкой
- `mousePressEvent`/`mouseMoveEvent` для перетаскивания окна
- `_build_title_bar(title_text)` — кастомный заголовок с иконкой, кнопкой закрытия
- `_setup_ui()` — создание контейнера с чёрным фоном (единая структура для всех диалогов)

##### `editor.py` — TagEditorDialog
Наследует `BaseFramelessDialog`. Основной диалог редактора:
- **Удаление трека**: кнопка "Удалить" → подтверждение → флаг `delete_confirmed`.
- **Перемещение трека**: кнопка "Переместить в папку" → вызов `move_track_to_folder()` → обновление `file_path`.
- **Редактирование полей**: title, artist, album, year, track number, genre.
- **Синхронизация с именем файла**: заполнение из имени, генерация имени из тегов.
- **Управление обложками**: загрузка, онлайн-поиск (iTunes/Deezer), генерация.
- **Поиск метаданных онлайн** через iTunes и Deezer.
- **Асинхронное сохранение** в фоновом потоке.

##### `track_mover.py` — move_track_to_folder
Функция перемещения трека в другую папку:
- Валидация: папка внутри `music_folder`, не совпадает с текущей, нет дубликата имени.
- `shutil.move()` + обновление избранного (`toggle_favorite(new_path)`).
- Возвращает новый путь или `None`.

##### `base_dialog.py`, `dialogs.py` — Dialog classes
- `TrackSearchResultsDialog` — результаты поиска треков.
- `CoverSearchResultsDialog` — выбор обложки.
- `CoverTile` — плитка обложки с SVG-заглушкой.
- Все наследуют `BaseFramelessDialog`, устранено ~55 строк дублирования.

##### `threads.py` — Worker threads
- `_TrackSearchThread` — поиск треков через iTunes/Deezer.
- `_CoverDownloadThread` — асинхронная загрузка обложек (не блокирует UI).
- `_SaveTagsThread` — сохранение тегов в фоне (MP3, FLAC, M4A/MP4).

##### `cover.py`, `cover_thread.py` — Cover generation
- `_generate_abstract_cover()` — генерация обложки на фоновом изображении.
- `_CoverSearchThread` — поиск обложек с дедупликацией через MD5.
    - **Онлайн-поиск обложек**: Поиск по API iTunes и Deezer с выбором из результатов.
    - Генерация обложек двойным кликом по фрейму отсутствующей обложки трека
- **Поиск информации о треке**:
    - **Онлайн-поиск метаданных**: Поиск полной информации о треке по API iTunes и Deezer.
    - Автоматический подбор наилучшего совпадения.
    - Несколько вариантов на выбор, с подсветкой полного совпадения **Artist - TrackTitle** (+TrackTime).
- **Сохранение**: Асинхронное сохранение в фоновом потоке с анимацией ожидания.
- После сохранения — перезапуск воспроизведения с сохранением позиции.

#### `ui/svg_icons.py` — SVG-иконки

Все иконки — функции возвращающие SVG-строки:

`get_play_svg`, `get_pause_svg`, `get_play_small_svg`, `get_pause_small_svg`, `get_next_svg`, `get_previous_svg`, `get_shuffle_svg`, `get_repeat_svg`, `get_repeat_one_svg`, `get_volume_high_svg`, `get_volume_mute_svg`, `get_folder_svg`, `get_all_music_svg`, `get_crown_svg`, `get_heart_svg`, `get_settings_svg`, `get_library_svg`, `get_top_svg`, `get_music_note_svg`, `get_similar_tracks_svg`, `get_artist_svg`, `get_info_svg`, `get_warning_svg`, `get_error_svg`, `get_question_svg`

`get_all_music_svg` — иконка «Вся музыка»: залитая папка с прозрачной одиночной нотой внутри (SVG-маска).
`get_artist_svg` — иконка «Исполнитель»: силуэт головы и плеч.
`get_info_svg`, `get_warning_svg`, `get_error_svg`, `get_question_svg` — иконки для `StyledMessageBox`.
`get_settings_svg`, `get_library_svg`, `get_top_svg` — иконки боковой панели.

#### `ui/mini_widget.py` — MiniPlayerWidget

Мини-плеер для системного трея (480×60px):
- Всегда поверх окон (`Qt.WindowStaysOnTopHint | Qt.Tool`)
- Перетаскиваемый (за область исполнителя/названия)
- Кнопка разворачивания | Артист / Название | ⏮ ▶/⏸ ⏭
- При наведении иконки меняют цвет на акцентный
- Фон с настраиваемой прозрачностью: `_idle_alpha` (0–255) при уходе мыши, при наведении плавно анимируется до 255 (непрозрачный). Значение задаётся через настройки (`mini_widget_opacity` → 0–80, где 0 = 255, 80 = 51)
- Автоматически обновляется при смене трека/состояния
- Метод `set_opacity(value)` — обновляет `_idle_alpha`, `_bg_alpha` и конечное значение `fade_out_anim`

#### `ui/widgets/` — Переиспользуемые виджеты

Пакет общих виджетов, используемых в различных диалогах приложения.

**`frameless_dialog.py`** — `FramelessDialog(QDialog)`:
- Базовый frameless-диалог с `Qt.FramelessWindowHint | Qt.Dialog` и `WA_TranslucentBackground`
- Акцентная рамка через `paintEvent()` (цвет `get_accent_color()` с alpha=26, ширина 2px)
- Перетаскивание окна через `mousePressEvent`/`mouseMoveEvent`
- Close button (`self._close_btn`): обновляется динамически через `_apply_close_btn_accent()` и публичный `apply_accent_color()` (вызывает `update()` для перерисовки рамки)

**`folder_browse_dialog.py`** — `FolderBrowseDialog(FramelessDialog)`:
- Кастомный диалог выбора папки с тёмной темой, заменяющий `QFileDialog`
- Используется в: `settings/dialog.py` (выбор корневой папки), `tag_editor/track_mover.py` (перемещение трека), `player/main_window.py`
- **`_build_ui(title_text)`**: собирает layout из title bar (через `FramelessDialog._build_title_bar`), левой панели (ключевые папки), правой панели (фильтр + tree), нижней панели (breadcrumb + кнопка "Выбрать")
- **Левая панель** (`_key_list: QListWidget`): топ-10 папок по количеству треков из БД (`get_all_folders()`), фильтр по `root_path` если задан
- **Правая панель**:
  - `_filter_input: QLineEdit` — быстрый поиск с debounce-фильтрацией видимых элементов
  - `_sort_combo: QComboBox` — сортировка: по названию / дате / размеру
  - `_root_header: QLabel` — кликабельный заголовок корневой папки (если `root_path` задан)
  - `_tree: QTreeWidget` — файловое дерево с ленивой подгрузкой (`_populate_subdirs`), иконки папок через `QSvgRenderer`
- **Нижняя панель**: breadcrumb + track count + кнопка "Выбрать" (акцентный цвет, disabled без выбора)
- **`apply_accent_color()`**: вызывает `super().apply_accent_color()` (обновляет close button + рамку), затем переписывает QSS для: `_key_list` (selected), `_sort_combo` (border + dropdown), `_filter_input` (focus), `_root_header` (text), `_tree` (selected), `_select_btn` (background + hover)
- **Навигация**: `_navigate_to(path)` — иерархический поиск/подгрузка пути, `_expand_parents` — разворачивание предков
- **Ограничение root**: `_norm_root` + `_is_inside_root()` — фильтрация дочерних элементов

**`styled_message_box.py`** — `StyledMessageBox(FramelessDialog)`:
- Кастомный MessageBox с иконками: `info`, `warning`, `error`, `question`
- Иконки — SVG из `ui/svg_icons.py` (`get_info_svg`, `get_warning_svg`, `get_error_svg`, `get_question_svg`)
- Поддержка до 3 кнопок с кастомными названиями и результатами
- Последняя кнопка — акцентный цвет (primary action)
- Авто-закрытие по таймеру (`auto_close`, секунды)
- Автоматический подсчёт высоты под текст

### Utils модули

#### `utils/audio_scanner.py` — AudioScanner
QThread для сканирования папок. Для максимальной производительности использует `ThreadPoolExecutor` для параллельной обработки файлов.

**Сигналы**:
- `scanning_started(str)` — путь к папке
- `track_scanned(TrackInfo)` — каждый найденный трек
- `scanning_progress(int, int)` — текущий/всего
- `tracks_removed(int)` — количество удалённых отсутствующих файлов
- `scanning_finished(list)` — финальный список треков
- `scanning_error(str)` — ошибка

#### `utils/helpers.py`
- `format_duration(seconds)` → `"M:SS"`
- `is_audio_file(filepath)` → bool
- `sanitize_filename(filename)` → str
- `get_folder_path(filepath)` → str
- `get_color_from_features(tempo, energy, mood)` -> QColor

## Git конфигурация

**`.gitignore`** — файл игнорирования Git:
- Python: `__pycache__/`, `*.py[cod]`, `*.egg-info/`
- Virtual environments: `.venv/`, `venv/`, `ENV/`
- IDE: `.idea/`, `.vscode/`, `*.swp`
- Build/Distribution: `build/`, `dist/`, `*.spec`
- Cache/Data: `.cache/`, `*.db*`
- OS: `.DS_Store`, `Thumbs.db`
- Logs: `*.log`
- Android app: `SonicFlame/` (отдельный проект)

## Цветовая схема

| Элемент            | Цвет                    |
|--------------------|-------------------------|
| Фон                | `#000000`               |
| Основной текст     | `#FFFFFF`               |
| Акцентный цвет     | `#ed6a02` (настраиваемый) |
| Разделители        | `rgba(80, 80, 80, 0.5)` |
| Бейджи фон         | `rgba(60, 60, 60, 140)` |
| Бейджи текст       | `#BEBEBE`               |
| Корона             | `#FFD700`               |
| Hover фон кнопок   | `rgba(80, 80, 80, 0.4)`|
| Тень окна          | `rgba(200, 200, 200, 100)` |

## Глобальные константы

| Константа           | Значение        | Файл                   |
|---------------------|-----------------|------------------------|
| APP_VERSION         | `0.9.93`        | `musicplayer/config.py`|
| ACCENT_COLOR        | `#ed6a02`       | `musicplayer/config.py`|
| TEXT_COLOR          | `#FFFFFF`       | `musicplayer/config.py`|
| DIVIDER_COLOR       | `rgba(80,80,80,0.5)` | `musicplayer/config.py`|
| PROJECT_DIR         | корень проекта  | `musicplayer/config.py`|
| CACHE_DIR           | `.cache/`       | `musicplayer/config.py`|
| DB_PATH             | `.cache/musicplayer.db` | `musicplayer/config.py`|
| COVERS_DIR          | `.cache/covers/`| `musicplayer/config.py`|
| ARTIST_COLLAGES_DIR | `.cache/artist_collages/` | `musicplayer/config.py`|
| SETTINGS_FILE       | `.cache/settings.json` | `musicplayer/config.py`|
| COL_WIDTHS_FILE     | `.cache/library_col_widths.json` | `musicplayer/config.py`|
| MIN_TEMPO / MAX_TEMPO | 40 / 200     | `musicplayer/config.py`|
| MIN_ENERGY / MAX_ENERGY | 0.01 / 1.0 | `musicplayer/config.py`|
| MIN_MOOD / MAX_MOOD | 0.01 / 1.0      | `musicplayer/config.py`|
| Мин. размер окна    | 1100×600        | `ui/main_window.py`    |

Все пути кэша централизованы в `config.py` и используются всеми модулями вместо захардкоженных относительных путей.

## Поток данных при воспроизведении

```
User → Sidebar: открыть папку
  → QFileDialog → folder_path
  → AudioScanner(folder_path, use_cache=True).start()
    → Compare disk vs DB (get_folder_filepaths)
    → Delete missing files from DB + covers
    → For each file on disk:
        → If mtime unchanged: load from DB
        → Else: extract_metadata() → upsert_track()
      → emit track_scanned(TrackInfo)
        → ScanningManager._on_track_scanned()
          → playlist.add_tracks()
          → playlist_widget.add_track()
    → emit scanning_finished(tracks)
      → MainWindow._on_scanning_finished()
        → Show "Загружено: N треков. Не найдено: M"
        → Auto-play first track (or restore last_track)
        → Enable sidebar buttons
```

## Архитектура IPC (Плеер ↔ Библиотека)

Связь между основным процессом плеера и субпроцессом библиотеки реализована через выделенные классы `IPCServer` и `IPCClient` в модуле `core/ipc.py`. Это позволяет обоим процессам обмениваться JSON-сообщениями в реальном времени.

- **Роли**:
  - **Плеер (Сервер)**: `MainWindow` создает `IPCServer` с именем `SonicFlamePlayerIPC_v2` и ожидает одно подключение от процесса библиотеки.
  - **Библиотека (Клиент)**: Процесс, запущенный с флагом `--library`, создает `IPCClient` и устанавливает постоянное соединение с сервером плеера.

- **Классы**:
  - `IPCServer` (`core/ipc.py:24`): Наследует `QObject`, создает `QLocalServer`, обрабатывает подключения и сообщения. Сигналы: `client_connected`, `client_disconnected`, `play_track_requested`, `artist_play_requested`, `library_closed`. Методы: `start()`, `stop()`, `send_refresh()`, `send_close()`, `send_show()`, `send_accent_color()`.
  - `IPCClient` (`core/ipc.py:145`): Наследует `QObject`, создает `QLocalSocket`, поддерживает автоматическое переподключение через таймер (500мс). Сигналы: `connected`, `disconnected`, `refresh_requested`, `close_requested`, `show_requested`, `accent_color_changed`. Методы: `start()`, `stop()`, `send_play_track()`, `send_play_artist()`, `send_library_closed()`.

- **Потоки данных**:
  - **Библиотека → Плеер**: Отправляет сообщения для управления плеером.
    - `{"type": "play", "payload": {"filepath": "..."}}`: Команда на воспроизведение трека, выбранного в библиотеке.
    - `{"type": "play_artist", "payload": {"artist": "..."}}`: Команда на воспроизведение всех треков артиста.
    - `{"type": "close"}`: Уведомление о том, что окно библиотеки закрывается.
  - **Плеер → Библиотека**: Отправляет команды для управления окном библиотеки.
    - `{"type": "refresh"}`: Перезагрузить и отобразить актуальные данные в таблице библиотеки.
    - `{"type": "close"}`: Закрыть окно библиотеки (например, при сворачивании плеера в трей).
    - `{"type": "show"}`: Показать окно библиотеки.
    - `{"type": "accent_color", "payload": {"color": "..."}}`: Изменить акцентный цвет в библиотеке.

- **Схема**:
```
┌──────────────────┐           ┌──────────────────────┐
│   Player (main)  │           │ Library (subprocess) │
│                  │           │  main.py --library   │
│  IPCServer       │◄─────────►│  IPCClient           │
│  QLocalServer    │   JSON    │  QLocalSocket        │
│ "SonicFlame...v2"│           │  (auto-reconnect)    │
└──────────────────┘           └──────────────────────┘
```

- **Особенности**:
  - Автоматическое переподключение: `IPCClient` использует таймер для повторных попыток подключения каждые 500мс.
  - Одновременное подключение: `IPCServer` поддерживает только одно подключение (отклоняет остальные).
  - Управление цветом: При изменении акцентного цвета в плеере он автоматически передается в библиотеку.
  - **Умное обновление библиотеки**: `send_refresh()` → библиотека проверяет `get_db_mtime()` — если БД не изменилась, перезагрузка таблицы пропускается.

- **Статус**: Реализация завершена. Проблемы с race condition и переподключением решены.

## Известные ограничения

1. **FramelessWindowHint** — системный заголовок отключён, перетаскивание только за кастомный title bar
2. **QMediaPlayer** — зависит от установленных кодеков FFmpeg в системе
3. **Плейлист** — одна папка за раз + фильтрованные виды (избранное/топ)
4. **Метаданные** — lyrics, BPM, composer не извлекаются
5. **Обложки** — если несколько в файле, берётся первая
6. **Мини-виджет** — позиционируется на основном мониторе
7. **SMTC (System Media Transport Controls)** — Qt6 `QMediaPlayer.metaData()` не пробрасывает метаданные в системный оверлей Windows. Для полной интеграции с SMTC требуется Windows Runtime API (`winrt`)

## Запуск

```bash
# Установка зависимостей
pip install -r requirements.txt

# Запуск плеера
python main.py

# Запуск библиотеки (отдельный процесс)
python main.py --library

# Установка как пакета
pip install -e .
musicplayer          # или sonicflame
```

## В планах

[x] **Анализатор настроения трека** — `Реализовано`
   - Определение эмоциональной окраски музыки на основе аудиохарактеристик (`tempo`, `energy`, `mood`).
   - Данные сохраняются в БД.
   - Визуализируется в виде цветной звезды на обложке и в библиотеке.

[x] **Подбор похожих треков** — `Реализовано`
   - Рекомендательная система на основе метаданных и анализа аудио
   - Анализ аудио реализован

[x] **Сортировка плейлиста** — `Реализовано`
   - Четыре режима: по исполнителю, по названию, по новизне и перемешивание (shuffle)
   - Сохранение режима в конфиге, применение при загрузке папок

[x] **Веб-сервер с WebAPI** — `Реализовано`
   - HTTP сервер для управления воспроизведением
   - Веб-интерфейс с информацией о текущем треке и плейлисте
   - Полнофункцианальный API
   - Мобильная адаптация

[x] **Мобильное приложение для Android** — `Реализовано`
   - Приложение на Kotlin для управления плеером
   - Подключение к плееру через локальную сеть через Web API
   - Общий стиль дизайна с основным приложением. Поддержка динамической смены акцентного цвета.
   - Ввод адреса сервера текстом или сканирование QR из настроек плеера, 
   - Seek-бар (интервал обновления: 1 сек)  прогресса воспроизведения, Воспроизведение/Пауза, следующий, предыдущий, переключение режимов повтора (нет, все, один трек)
   - Добавление/удаление треков из избранного с визуальным отображением иконкой.
    - Плейлист, воспроизведение любого трека из плейлиста,Загрузка плейлистов (Избранное, Топ, Папки)

## Лицензия

GNU General Public License v3.0 (GPL v3)