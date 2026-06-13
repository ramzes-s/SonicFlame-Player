# План: Yandex Music Downloader — подключаемый модуль (аддон)

## 1. Архитектура плагинов

### 1.1. Система плагинов

```
MusicPlayer2/
├── plugins/                              # Папка аддонов (можно удалить целиком)
│   ├── __init__.py
│   └── ym_downloader/                    # Аддон скачивания с YM
│       ├── __init__.py                   # register(hub) — точка входа
│       ├── plugin.json                   # Метаданные: имя, версия, автор
│       ├── api.py                        # YM API клиент (поиск, скачивание, превью)
│       ├── metadata.py                   # Запись тегов + обложки в MP3
│       ├── ui.py                         # Диалоги (поиск, скачивание)
│       └── managers.py                   # Менеджер скачивания (ретря, temp, сохранение)
├── musicplayer/
│   ├── core/
│   │   ├── plugin_manager.py             # PluginHub + PluginManager (базовый класс плагина)
│   │   └── ...                           # Всё остальное без изменений
│   ├── ui/
│   │   ...                               # Никаких зависимостей от ym_downloader
│   └── config.py                         # Новая константа: PLUGINS_DIR = PROJECT_DIR / 'plugins'
```

### 1.2. PluginHub — Мост между аддоном и плеером

`PluginHub` — объект, который плеер передаёт аддону при регистрации. Содержит методы для взаимодействия с плеером, но НЕ даёт прямого доступа к внутренним объектам.

```python
class PluginHub:
    def show_dialog(self, dialog_class, *args, **kwargs) -> QDialog
    def get_player(self) -> AudioPlayer              # Только play/pause/stop
    def get_db(self) -> ModuleType                    # Только публичные функции db
    def get_settings(self) -> AppSettings
    def get_main_window(self) -> QWidget              # Только как parent для диалогов
    def add_tracks_to_library(self, filepaths: List[str])
    def get_config_value(self, key: str)
    def add_settings_page(self, page_widget, tab_name: str)
```

### 1.3. PluginManager

Загрузка плагинов при старте плеера (`main.py` или в `MainWindow.__init__`):

```python
# config.py
PLUGINS_DIR = PROJECT_DIR / 'plugins'
ENABLE_PLUGINS = True                     # False → плагины не загружаются

# plugin_manager.py
class PluginManager:
    def discover(self) -> List[PluginInfo]  # Сканирует plugins/, читает plugin.json
    def load_plugin(self, info: PluginInfo) -> bool  # Импортирует модуль
    def register_all(self, hub: PluginHub)  # Вызывает register(hub) у каждого
```

Если `plugins/` не существует или пуста — `discover()` возвращает пустой список, плеер работает как обычно.

## 2. Компоненты аддона ym_downloader

### 2.1. plugin.json

```json
{
    "name": "ym_downloader",
    "display_name": "Yandex Music Downloader",
    "version": "1.0.0",
    "entry": "ym_downloader",
    "description": "Поиск и скачивание треков с Yandex Music",
    "settings_page": true,
    "requires": ["yandex-music"]
}
```

### 2.2. api.py — YM API клиент

```python
class YandexMusicAPI:
    def __init__(self, token: str)
    def login(self) -> bool                    # Проверка токена
    def search(self, query: str, page=0) -> List[TrackInfo]  # Поиск
    def download_to_temp(self, track_id: str, temp_dir: Path) -> Optional[Path]
        # Ретраи до 5 раз, пауза 3с
        # Проверка длительности: <60с → реклама → retry
        # Возвращает путь к temp-файлу или None
    def get_track_cover(self, track_id: str) -> Optional[bytes]
    def get_preview_url(self, artist: str, title: str) -> Optional[str]
        # Публичное API Deezer (без логина) → 30с превью
```

### 2.3. metadata.py — Запись тегов

```python
def write_tags(mp3_path: str, track_info: TrackInfo, cover_bytes: Optional[bytes])
    # mutagen:
    #   TIT2, TPE1, TALB, TDRC (год), TCON (жанр), TRCK (номер)
    #   APIC (обложка, 3/image/jpeg)
    #   Комментарий: "Downloaded from Yandex Music"
```

### 2.4. managers.py

```python
class DownloadManager(QObject):
    """
    Координатор процесса скачивания.
    """
    # Сигналы
    search_completed = Signal(list)           # List[TrackInfo]
    download_progress = Signal(int)           # 0-100%
    preview_ready = Signal(str)               # путь к temp-файлу
    download_failed = Signal(str)             # причина
    save_completed = Signal(str)              # путь к сохранённому файлу
    
    def search_tracks(self, query: str)       # → search_completed
    def download_and_preview(self, track: TrackInfo)
        # 1. Скачивает в temp
        # 2. Проверяет длительность (реклама?)
        # 3. → preview_ready
        # 4. Плеер начинает воспроизведение temp-файла
    def save_track(self, path: str, dest_folder: str)
        # 1. Копирует в dest_folder с нормальным именем
        # 2. Пишет теги + обложку
        # 3. Добавляет в БД (upsert_track)
        # 4. → save_completed
    def discard_preview(self)                # Удаляет temp
```

### 2.5. ui.py — Диалоги

**SearchDialog** (`BaseFramelessDialog`):
- Поле поиска + кнопка "Найти"
- Список результатов: артист — название — длительность
- Кнопка "Слушать" для каждого трека
- Анимация загрузки при каждом нажатии

**SaveDialog** (наследует `FramelessDialog`):
- Показывает инфо о треке (обложка, название, артист)
- Кнопка "Выбрать папку" → `FolderBrowseDialog`
- Кнопка "Сохранить" / "Отмена"
- Во время скачивания: прогресс-бар

### 2.6. register() — Точка входа

```python
# plugins/ym_downloader/__init__.py

def register(hub: PluginHub):
    # 1. Добавить страницу в настройки (вкладка "Внешние API")
    from .ui import YMSettingsPage
    hub.add_settings_page(YMSettingsPage, "Внешние API")
    
    # 2. Добавить кнопку в боковую панель
    # hub.add_sidebar_button("ym_download", icon, callback)
    # Либо: добавить пункт в контекстное меню плейлиста
    
    # 3. Зарегистрировать горячие клавиши (опционально)
```

## 3. Изменения в существующем коде

### 3.1. Новые файлы (минимальные изменения core)

| Файл | Описание |
|------|----------|
| `musicplayer/core/plugin_manager.py` | PluginHub, PluginManager |
| `musicplayer/config.py` | + `PLUGINS_DIR`, + `ENABLE_PLUGINS` |

### 3.2. Изменения

| Файл | Изменение |
|------|-----------|
| `musicplayer/config.py` | +2 константы |
| `musicplayer/ui/player/main_window.py` | + `PluginManager.init()` после загрузки UI |
| `musicplayer/ui/settings/dialog.py` | + `add_settings_page()` в PluginHub (добавляет вкладку) |
| `main.py` | Создание `plugins/` директории если нет |
| `requirements.txt` | + `yandex-music` (только если аддон установлен) |

### 3.3. Что НЕ меняется

- `player.py`, `playlist.py`, `db/*.py` — без изменений
- Все UI компоненты плеера — без зависимостей от плагина
- Если `plugins/` удалена → `plugin_manager.py` просто ничего не загружает

## 4. Работа с PyInstaller

### Вариант 1: Аддон встроен в .exe (рекомендуемый)

```
MusicPlayer2/
├── plugins/ym_downloader/        # Будет запаковано в .exe
```

В `.spec` файле:
```python
a = Analysis(
    ...
    datas=[('plugins\\ym_downloader', 'plugins\\ym_downloader')],
)
```

Плюсы: одна сборка, всё включено.
Минусы: нельзя удалить удалением папки.

### Вариант 2: Аддон как внешняя папка (максимальная модульность)

В `.spec`:
```python
exe = EXE(
    ...
    exclude_modules=['yandex_music*'],  # Не вшивать YM в exe
)
```

При запуске плеер ищет `plugins/` рядом с .exe:
```
dist/MusicPlayer2/
├── MusicPlayer2.exe
├── plugins/
│   └── ym_downloader/
│       ├── ... (чистый Python, не скомпилирован)
│       ├── yandex_music/          # pip install --target ...
│       └── mutagen/               # pip install --target ...
```

В `plugin_manager.py` добавлен путь к папке плагина в `sys.path`:
```python
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    base = Path(sys.executable).parent
else:
    base = PROJECT_DIR

plugins_path = base / 'plugins'
if plugins_path.exists():
    sys.path.insert(0, str(plugins_path))
```

Плюсы: удалил папку `plugins/` — нет аддона. Обновление аддона без пересборки exe.
Минусы: нужно следить за зависимостями (yandex-music, mutagen — уже есть в основном проекте).

### Итоговое решение для сборки

**Гибридный подход:**
- В штатной сборке `plugins/ym_downloader/` запакован в .exe (Вариант 1)
- Пользователь может создать внешнюю `plugins/` рядом с .exe — она переопределяет встроенную
- Или удалить `plugins/ym_downloader/` из распакованной сборки

## 5. Поток данных пользователя

```
Settings → Вкладка "Внешние API"
    → Пользователь вставил OAuth URL → токен распарсен
    → Валидация: запрос к YM API → статус "Подключено"
    
Sidebar → Новая кнопка "🔽 Скачать"
    → SearchDialog → ввод "queen bohemian rhapsody"
    → Поиск → 20 результатов
    → Выбор трека → кнопка "Слушать"
    
DownloadManager:
    → api.download_to_temp()           # 0-5 попыток, пауза 3с
    → temp-файл готов
    → Сигнал preview_ready(temp_path)
    
Плеер:
    → Загружает temp-файл, начинает воспроизведение с 0:00
    → В диалоге меняется кнопка на "Сохранить" / "Отмена"
    
Пользователь слушает:
    → Если нравится → "Сохранить"
        → FolderBrowseDialog (выбор папки)
        → Копирование в папку + запись тегов + обложка
        → upsert_track → авто-появление в библиотеке
        → Готово: уведомление
    → Если не нравится → "Отмена"
        → temp-файл удалён
        → Можно искать другой трек
```

## 6. Ограничения

| Ограничение | Причина |
|-------------|---------|
| Только MP3 192kbps | YM отдаёт premium-форматы только подписчикам |
| Иногда реклама (33с) вместо трека | YM free tier. Ретрай 5 раз с паузой 3с решает |
| Токен в `settings.json` | Можно добавить шифрование позже |
| Только 20 результатов на страницу | Ограничение YM API. Можно сделать пагинацию |
| yandex-music должна быть установлена | Зависимость плагина. В сборке вшивается в exe |

## 7. Этапы реализации

| Этап | Что делаем | Зависит от |
|------|-----------|------------|
| **1** | `core/plugin_manager.py` + PluginHub + PluginManager | Нет |
| **2** | `plugins/ym_downloader/` — пустой каркас с `register()` | Этап 1 |
| **3** | `api.py` — YM API (поиск, скачивание, ретраи) | Нет |
| **4** | `ui.py` — SearchDialog, SaveDialog | Этап 3 |
| **5** | `managers.py` — DownloadManager (координация) | Этапы 3, 4 |
| **6** | `metadata.py` — запись тегов + обложка | mutagen |
| **7** | Интеграция настроек — вкладка "Внешние API" | Этап 2 |
| **8** | Кнопка в боковой панели / контекстном меню | Этап 5 |
| **9** | Интеграция PyInstaller .spec | Все |
