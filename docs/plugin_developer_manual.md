# Руководство для разработчиков плагинов MusicPlayer2

Это руководство описывает архитектуру, требования и API для создания плагинов, расширяющих функциональность плеера. Плагины загружаются динамически через централизованный `PluginHub` и не имеют прямого доступа к внутренностям приложения.

---

## 1. Обнаружение и загрузка

### 1.1. Директория плагинов

Все плагины располагаются в папке `plugins/` рядом с исполняемым файлом (или корнем проекта в dev-режиме). Путь определяется в `config.py`:

```python
PLUGINS_DIR = PROJECT_DIR / "plugins"
ENABLE_PLUGINS = True
```

- Директория создаётся автоматически при запуске плеера (`main_window.py:106`).
- Если `ENABLE_PLUGINS = False` — плагины не обнаруживаются и не загружаются.
- Внутри `plugins/` должен быть файл `__init__.py` (создаётся автоматически).

### 1.2. Структура папки плагина

```
plugins/<plugin_name>/
├── plugin.json          # Манифест (обязательно)
├── __init__.py          # Точка входа с register(hub) (обязательно)
├── ...                   # Вспомогательные модули (опционально)
└── _vendor/              # Сторонние зависимости (опционально, для frozen exe)
```

> **Важно**: Имя папки **не обязано** совпадать с `name` или `entry` в манифесте, но рекомендуется для ясности. Папки, начинающиеся с `_`, игнорируются.

### 1.3. Формат манифеста `plugin.json`

```json
{
    "name": "duplicate_finder",
    "display_name": "Поиск дублей в библиотеке",
    "version": "1.0.0",
    "entry": "duplicate_finder",
    "description": "Находит дубликаты треков по названию и исполнителю",
    "settings_page": true
}

```

| Поле | Тип | Обязательное | Описание |
|------|-----|-------------|----------|
| `name` | string | да | Уникальный идентификатор плагина. Используется для ключа `plugin_enabled_<name>` в настройках. |
| `display_name` | string | нет | Отображаемое имя (если нет — используется `name`). |
| `version` | string | нет | Семантическая версия (по умолчанию `"0.0.0"`). |
| `entry` | string | нет | Модуль для импорта (по умолчанию значение `name`). Без расширения `.py`. |
| `description` | string | нет | Краткое описание (отображается в списке плагинов под именем). |
| `settings_page` | bool | нет | Флаг наличия UI-настроек (по умолчанию `false`). |
| `requires` | array[string] | нет | Список pip-пакетов, необходимых плагину (информационно, для документации). |

### 1.4. Процесс загрузки

```python
# main_window.py
self._plugin_manager = PluginManager(self, self.settings)
self._plugin_pages = []
self._plugin_manager.discover()       # Шаг 1: сканирование
self._plugin_manager.register_all()   # Шаг 2: загрузка и регистрация
```

**Шаг 1 — `discover()`**:
- Проходит по подпапкам `plugins/`, игнорируя начинающиеся с `_`.
- Читает `plugin.json`, создаёт объект `PluginInfo`.

**Шаг 2 — `register_all()`**:
- Добавляет `plugins/` в `sys.path`.
- Для каждого **включённого** плагина (проверка `get_plugin_enabled(name)`):
  - Устанавливает глобальную переменную `_current_plugin_info = info`.
  - Выполняет `__import__(info.entry, fromlist=['register'])`.
  - Вызывает `plugin_mod.register(self._hub)`.
  - Сбрасывает `_current_plugin_info = None`.

**Очистка устаревших настроек**:
После `discover()` менеджер автоматически удаляет ключи `plugin_enabled_*` для плагинов, которых больше нет на диске (`cleanup_plugin_settings()`).

---

## 2. API PluginHub

`PluginHub` — единственный способ взаимодействия плагина с плеером. Плагин получает его в свою функцию `register(hub)`.

### 2.1. UI-интеграция

#### `add_sidebar_button(svg_getter, tooltip, callback) -> QPushButton`

Добавляет кнопку в боковую панель.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `svg_getter` | `Callable[[str], str]` | Функция, принимающая параметр `color` (HEX-строка) и возвращающая SVG-строку. |
| `tooltip` | str | Всплывающая подсказка. |
| `callback` | `Callable` | Функция без аргументов, вызываемая при клике. |

**Пример:**
```python
hub.add_sidebar_button(
    lambda color="#FFFFFF": f'<svg>... fill="{color}" ...</svg>',
    "Online Поиск музыкиЫ",
    on_download_clicked,
)
```

> **Важно**: SVG-функция получает актуальный цвет текста. Для статичного цвета укажите его напрямую.

#### `add_context_action(text, callback)`

Добавляет пункт в контекстное меню (правая кнопка мыши по треку в плейлисте).

| Параметр | Тип | Описание |
|----------|-----|----------|
| `text` | str | Текст пункта меню. |
| `callback` | `Callable` | Функция без аргументов. |

#### `add_settings_page(page_widget, tab_name)`

Добавляет **отдельную вкладку** в диалог настроек.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `page_widget` | `QWidget` | Готовая страница настроек. |
| `tab_name` | str | Название вкладки (отображается в боковом меню). |

Вкладки плагинов располагаются перед вкладкой "О программе".

#### `set_settings_widget(widget_factory)`

Регистрирует фабрику виджета, который встраивается внутрь вкладки "Плагины" (под переключателем плагина). Альтернатива `add_settings_page` для простых настроек.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `widget_factory` | `Callable[[], QWidget]` | Функция без аргументов, возвращающая виджет-страницу настроек. |

**Важные требования к встроенному виджету:**
- Виджет должен уметь скрываться/показываться — его видимость переключается автоматически при включении/выключении плагина.
- Если виджет использует акцентный цвет, реализуйте метод `apply_accent_color(self, color: str)`. Он вызывается при смене цвета в настройках.

**Пример:**
```python
hub.set_settings_widget(lambda: YMSettingsPage(hub.get_settings()))
```

### 2.2. Управление плеером

#### `get_player() -> AudioPlayer`

Возвращает экземпляр `AudioPlayer`. Доступные методы для плагинов:

| Метод | Описание |
|-------|----------|
| `.play()` | Начать воспроизведение. |
| `.pause()` | Пауза. |
| `.stop()` | Остановка. |
| `.get_state() -> QMediaPlayer.State` | Текущее состояние. |
| `.get_position() -> int` | Позиция в мс. |
| `.set_position(ms: int)` | Перемотка. |
| `.get_duration() -> int` | Длительность в мс. |
| `.set_volume(vol: float)` | Громкость (0.0–1.0). |
| `.get_volume() -> float` | Текущая громкость. |
| `.is_playing() -> bool` | Флаг воспроизведения. |
| `.toggle_play_pause()` | Переключить play/pause. |

> **Важно**: Плагин **не должен** вызывать `.load_source()` напрямую. Для воспроизведения собственных файлов используйте `player.player.setSource(QUrl.fromLocalFile(...))`.

#### `get_playlist_widget() -> PlaylistWidget`

Возвращает виджет плейлиста. Используйте только для чтения текущего плейлиста (`get_view_tracks()`). Модификация плейлиста из плагина не поддерживается.

#### `get_main_window() -> QWidget`

Возвращает главное окно плеера (как родитель для диалогов).

### 2.3. Настройки и конфигурация

#### `get_settings() -> AppSettings`

Возвращает объект настроек. Плагин может читать и писать свои ключи:

```python
settings = hub.get_settings()
# Чтение
token = settings._data.get("ym_token", "")
# Запись
settings._data["ym_token"] = "new_token"
settings._save()
```

> **Важно**: Все ключи плагина должны иметь уникальный префикс (например, `ym_token`, `ym_quality`), чтобы избежать коллизий.

#### `get_config_value(key: str) -> Any`

Получить значение глобальной константы из `config.py` по имени атрибута:

```python
plugins_dir = hub.get_config_value("PLUGINS_DIR")
temp_dir = hub.get_config_value("TEMP_DIR")
```

### 2.4. База данных

#### `get_db() -> module`

Возвращает модуль `musicplayer.core.db` для прямых запросов:

```python
db = hub.get_db()
with db.get_connection() as conn:
    cur = conn.execute("SELECT ...")
```

Доступные функции модуля: `get_connection()`, `extract_metadata()`, `upsert_track()`, `get_track()`, `delete_track()`.

#### `add_tracks_to_library(filepaths: list)`

Добавляет аудиофайлы в библиотеку: извлекает метаданные, сохраняет в БД, кэширует обложки. Если файлы добавлены в текущую открытую папку — автоматически запускает пересканирование.

```python
hub.add_tracks_to_library(["/path/to/new/track.mp3"])
```

---

## 3. Жизненный цикл плагина

### 3.1. Регистрация

Функция `register(hub)` вызывается один раз при старте приложения (или при перезагрузке плагинов). В ней плагин должен:

1. Зарегистрировать UI-элементы (sidebar, context menu).
2. Зарегистрировать настройки (вкладку или встроенный виджет).
3. Инициализировать внутренние компоненты (API-клиенты, менеджеры).
4. Проверить необходимые условия (токен, зависимости).

### 3.2. Включение/Отключение

- Плагин можно отключить через интерфейс настроек (переключатель во вкладке "Плагины").
- Отключённые плагины не импортируются и не вызывают `register()`.
- При отключении зависимостей перезагрузка не требуется — изменения применяются при следующем запуске.
- Ключ `plugin_enabled_<name>` хранится в `settings.json`.

### 3.3. Удаление

- Для удаления плагина достаточно удалить его папку из `plugins/`.
- При следующем запуске `cleanup_plugin_settings()` удалит устаревшие ключи настроек.
- Никаких изменений в ядре плеера не требуется.

---

## 4. Обработка ошибок и логирование

### 4.1. Импорт и регистрация

`PluginManager` оборачивает импорт и вызов `register()` в `try/except`. Ошибка в одном плагине не влияет на другие.

### 4.2. Рекомендации по надёжности

- Внутри `register()` используйте `try/except` для критических операций.
- Для логирования используйте `logging.getLogger(__name__)`:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  logger.info("Plugin initialized")
  logger.error("Something went wrong", exc_info=True)
  ```
- Не прерывайте выполнение приложения при ошибках инициализации.

---

## 5. Зависимости и сборка

### 5.1. Режим разработки (PyCharm/python main.py)

Зависимости устанавливаются через `pip install -r requirements.txt` в виртуальное окружение. Плагин может импортировать любые установленные пакеты.

### 5.2. Frozen exe (PyInstaller)

- Плагины **исключены** из сборки: `excludes=['plugins']` в `.spec`.
- Плагин должен предоставлять свои зависимости самостоятельно.
- Рекомендуемый способ — папка `_vendor/` внутри плагина, добавляемая в `sys.path`:

  ```python
  # В начале __init__.py плагина:
  import sys
  from pathlib import Path
  vendor = Path(__file__).parent / "_vendor"
  if vendor.exists() and str(vendor) not in sys.path:
      sys.path.insert(0, str(vendor))
  ```

- Скрипт `install_deps.py` внутри плагина может использоваться для заполнения `_vendor/`.

### 5.3. Стандартная библиотека

Для frozen exe стандартные модули (например, `xml`, `email`) могут отсутствовать, если не указаны в `hiddenimports`. Плагин может включить их в свой `_vendor/`.

---

## 6. UI-стилизация

### 6.1. Цвета

Все цвета интерфейса стандартизированы в `config.py`. Плагин **должен** использовать константы:

```python
from musicplayer import config as cfg

# Основные цвета:
cfg.BG_COLOR             # #000000 — фон
cfg.TEXT_COLOR           # #FFFFFF — текст
cfg.SECONDARY_TEXT_COLOR # #888888 — вторичный текст
cfg.TERTIARY_TEXT_COLOR  # #CCCCCC — текст подписей
cfg.DISABLED_TEXT_COLOR  # #666666 — отключённый
cfg.SECONDARY_BG_COLOR   # #1a1a1a — альтернативный фон
cfg.DIVIDER_COLOR        # rgba(80,80,80,0.5) — разделители
cfg.ACCENT_COLOR         # #ed6a02 (может меняться пользователем)
cfg.get_accent_color()   # Функция для получения текущего акцентного цвета
```

> **Запрещено** хардкодить HEX/rgba цвета без явной необходимости.

### 6.2. Акцентный цвет

Если плагин использует акцентный цвет в UI, его страница настроек (и любые дочерние виджеты) должны реализовать метод:

```python
def apply_accent_color(self, color: str):
    """Обновить цвета при смене акцента."""
    self._some_label.setStyleSheet(f"color: {color};")
```

Этот метод вызывается:
- Для встроенных виджетов — через `PluginsPage.apply_accent_color()`.
- Для отдельных вкладок — через `SettingsDialog.apply_accent_color()`.

### 6.3. Стиль полей ввода и кнопок

Для единообразия используйте `QSS` с константами:

```python
# Поле ввода с нижней рамкой акцентного цвета:
input.setStyleSheet(f"""
    QLineEdit {{
        background-color: {cfg.INPUT_BG_COLOR};
        border: none;
        border-bottom: 1px solid {cfg.get_accent_color()};
        color: {cfg.INPUT_TEXT_COLOR};
        font-size: 14px;
        padding: 2px 4px;
    }}
    QLineEdit:focus {{
        border-bottom: 2px solid {cfg.get_accent_color()};
    }}
""")

# Кнопка с акцентным фоном:
btn.setStyleSheet(f"""
    QPushButton {{
        background-color: {cfg.get_accent_color()};
        border: none;
        color: {cfg.TEXT_COLOR};
        font-size: 12px;
        padding: 0 16px;
    }}
    QPushButton:hover {{
        background-color: {cfg.TEXT_COLOR};
        color: {cfg.get_accent_color()};
    }}
""")
```

---

## 7. Полный пример плагина

### 7.1. `plugins/test_plugin/plugin.json`

```json
{
    "name": "test_plugin",
    "display_name": "Test Plugin",
    "version": "0.0.1",
    "entry": "test_plugin",
    "description": "Тестовый плагин — просто чтобы было",
    "settings_page": true
}
```

### 7.2. `plugins/test_plugin/__init__.py`

```python
"""Test Plugin — минимальный плагин для проверки UI нескольких плагинов."""

import logging
from PySide6.QtWidgets import QVBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt
from musicplayer import config as cfg

logger = logging.getLogger(__name__)


class TestPage(QWidget):
    def __init__(self, settings):
        super().__init__()
        self._settings = settings
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setAlignment(Qt.AlignCenter)

        self._label = QLabel("Привет! Это тестовый плагин.\n"
                             "Тут ничего нет, просто проверка.")
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 14px;")
        layout.addWidget(self._label)

    def apply_accent_color(self, color: str):
        """Обновить цвета при смене акцентного цвета."""
        self._label.setStyleSheet(
            f"color: {cfg.TERTIARY_TEXT_COLOR}; font-size: 14px;")


def register(hub):
    """Точка входа — вызывается PluginManager при загрузке плагина."""
    logger.info("Test Plugin registered")
    hub.set_settings_widget(lambda: TestPage(hub.get_settings()))
```

---

## 8. Структура API-методов PluginHub (справочно)

| Метод | Назначение |
|-------|-----------|
| `add_sidebar_button(svg_getter, tooltip, callback)` | Кнопка в боковую панель |
| `add_context_action(text, callback)` | Пункт в контекстном меню |
| `add_settings_page(page_widget, tab_name)` | Отдельная вкладка в настройках |
| `set_settings_widget(widget_factory)` | Встроенный виджет во вкладке "Плагины" |
| `get_player()` | Экземпляр AudioPlayer |
| `get_playlist_widget()` | Виджет плейлиста (только чтение) |
| `get_main_window()` | Главное окно (родитель для диалогов) |
| `get_settings()` | Объект AppSettings |
| `get_db()` | Модуль БД для прямых запросов |
| `add_tracks_to_library(filepaths)` | Добавление треков в библиотеку |
| `get_config_value(key)` | Константа из config.py |

---

## 9. Структура PluginInfo (для информации)

Поле `settings_widget_factory` заполняется автоматически при вызове `hub.set_settings_widget()` и не должен устанавливаться плагином напрямую.

```python
class PluginInfo:
    name: str                       # Уникальный ID
    display_name: str               # Отображаемое имя
    version: str                    # Версия
    entry: str                      # Модуль для импорта
    description: str                # Описание
    settings_page: bool             # Флаг наличия UI настроек
    requires: list                  # Список зависимостей
    settings_widget_factory: Callable  # Устанавливается hub.set_settings_widget()
```

---

## 10. Ограничения

1. Плагин **не может** добавлять свои зависимости в `requirements.txt` проекта.
2. Плагин **не должен** модифицировать ядро плеера (файлы в `musicplayer/core/`).
3. Плагин **не должен** импортировать внутренние модули напрямую — только через `PluginHub`.
4. `add_settings_page()` создаёт отдельную вкладку; если планируется несколько плагинов, используйте `set_settings_widget()` для встраивания в общую вкладку.
5. Плагин **не должен** полагаться на наличие других плагинов.
6. Для frozen exe зависимости плагина не входят в `.exe` — их нужно предоставлять через `_vendor/`.
7. Метод `apply_accent_color()` вызывается при смене цвета в настройках (не при загрузке). При старте используйте `cfg.get_accent_color()` напрямую.

---

*Дата обновления: 2026-06-06*
