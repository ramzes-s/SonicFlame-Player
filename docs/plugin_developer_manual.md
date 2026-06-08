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

Регистрирует фабрику виджета, который отображается **в отдельном FramelessDialog** при нажатии кнопки "⚙ Настроить" во вкладке "Плагины". Виджет **никогда** не встраивается напрямую в окно настроек, а открывается в модальном диалоге.

| Параметр | Тип | Описание |
|----------|-----|----------|
| `widget_factory` | `Callable[[], QWidget]` | Функция без аргументов, возвращающая виджет-страницу настроек. |

**Почему не встраивание:**
На Windows виджеты с HWND-бэкендом (`QTableWidget`, `QComboBox`, `QLineEdit`, `QTreeWidget` и т.д.) вызывают артефакт DWM flash при размещении внутри безрамочного окна (`FramelessWindowHint`). Единственное надёжное решение — не встраивать их вовсе, а открывать в отдельном модальном `FramelessDialog`.

**Как это работает:**
```python
# page_plugins.py:_open_config()
dlg = FramelessDialog(self.window())
inner = dlg._setup_ui()
inner.addWidget(dlg._build_title_bar(f"{info.display_name} — настройки"))
config = info.settings_widget_factory()
inner.addWidget(config)
inner.addStretch()
dlg.center_on_parent()
dlg.exec()
```

**Рекомендации:**
- Виджет может **безопасно** содержать любые Qt-виджеты, включая `QTableWidget`, `QComboBox`, `QScrollArea` — они не встраиваются в безрамочное окно.
- Виджет открывается в модальном диалоге — `apply_accent_color()` не вызывается во время показа (диалог блокирует смену цвета). При старте используйте `cfg.get_accent_color()`.
- Для простых без-интерактивных страниц (только `QLabel`, пояснения) можно обойтись и без отдельного диалога, но архитектура единообразна для всех плагинов.
- Если плагину нужно открыть **собственное полноценное окно** (не встроенный виджет, а отдельный диалог поиска дублей и т.п.), используйте шаблон «закрыть родителя через singleShot» (см. раздел 2.1.4.1).

**Пример:**
```python
hub.set_settings_widget(lambda: YMSettingsPage(hub.get_settings()))
```

##### 2.1.4.1. Шаблон «отдельное окно плагина» (auto-close)

Для плагинов, которые должны открывать собственное полноценное окно (поиск дублей, менеджер геймпада и т.п.), используйте следующий шаблон:

```python
class MyPluginPage(QWidget):
    def __init__(self, settings):
        super().__init__()
        self._settings = settings
        self._opened = False
        lo = QVBoxLayout(self)
        lo.addStretch()
        QTimer.singleShot(0, self._auto_open)

    def _auto_open(self):
        if self._opened:
            return
        self._opened = True
        mw = _hub.get_main_window() if _hub else self.window()
        p = self.window()
        if p and p is not self:
            p.close()
        QTimer.singleShot(0, lambda mw=mw: _open_my_dialog(mw))
```

**Логика:**
- `_auto_open` вызывается через `QTimer.singleShot(0)` после создания виджета (но после того, как FramelessDialog из `_open_config` уже показан).
- Сначала захватывается ссылка на главное окно (`mw`), затем родительский диалог закрывается (`p.close()`) — окно настроек исчезает немедленно.
- Второй `QTimer.singleShot(0)` нужен, чтобы дождаться полного уничтожения родительского диалога (виджет `self` может быть удалён к этому моменту, поэтому вся логика вынесена в модульную функцию `_open_my_dialog`).
- Функция `_open_my_dialog` не имеет доступа к `self`, вся необходимая логика должна быть самодостаточной.

**Пример реализации (duplicate_finder):**
```python
def _open_dupe_dialog(parent_window):
    """Создаёт и показывает диалог поиска дублей (без self)."""
    from musicplayer.ui.widgets.frameless_dialog import FramelessDialog
    from musicplayer.ui.tag_editor.widgets import LoadingBar

    dialog = FramelessDialog(parent_window)
    inner = dialog._setup_ui()
    # ... построение UI, closures ...
    dialog.exec()


def register(hub):
    hub.set_settings_widget(lambda: DuplicateFinderPage(hub.get_settings()))
```

> **Важно:** Функция `_open_dupe_dialog` не должна ссылаться на `self`, `hub` или другие объекты, которые могут быть удалены при закрытии родительского диалога. Используйте только переданные аргументы и глобальные переменные модуля (`_hub`, константы `cfg`).

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

Если плагин использует акцентный цвет в UI, его страница настроек (и любые дочерние виджеты) могут реализовать метод:

```python
def apply_accent_color(self, color: str):
    """Обновить цвета при смене акцента."""
    self._some_label.setStyleSheet(f"color: {color};")
```

**Важно:** Начиная с версии, где виджеты настроек открываются в отдельном `FramelessDialog` (модально), `apply_accent_color()` **не вызывается** во время показа диалога — модальный `exec()` блокирует смену цвета. Метод сохраняется для обратной совместимости, но для новых плагинов достаточно использовать `cfg.get_accent_color()` при построении UI.

Метод по-прежнему вызывается:
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
    """Страница настроек плагина. Открывается в отдельном FramelessDialog
    при нажатии '⚙ Настроить' во вкладке 'Плагины'."""

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


def register(hub):
    """Точка входа — вызывается PluginManager при загрузке плагина."""
    logger.info("Test Plugin registered")
    hub.set_settings_widget(lambda: TestPage(hub.get_settings()))
```

> **Примечание:** `apply_accent_color()` не требуется — страница открывается модально, акцентный цвет не может измениться во время показа. Достаточно `cfg.get_accent_color()` в `__init__`.

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
7. Виджеты с HWND-бэкендом (`QTableWidget`, `QComboBox`, `QLineEdit`, `QTreeWidget`, `QScrollArea` и т.д.) **не должны** встраиваться напрямую в безрамочное окно (`FramelessWindowHint` + `WA_TranslucentBackground`) — это вызывает DWM flash на Windows. Всегда используйте шаблон с отдельным `FramelessDialog` (реализовано в `_open_config` автоматически).
8. Виджет настроек открывается **модально** — `apply_accent_color()` не вызывается. При старте используйте `cfg.get_accent_color()` напрямую.
9. Для плагинов, которым нужно собственное полноценное окно (не встраиваемый виджет), используйте шаблон «auto-close» из раздела 2.1.4.1. Функция с логикой окна не должна ссылаться на `self`, только на переданные аргументы.

---

*Дата обновления: 2026-06-08*
