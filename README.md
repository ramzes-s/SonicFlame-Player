# SonicFlame Player

Modern desktop audio player with a GUI built on Python (PySide6/Qt6).

![SonicFlame Player](SonicFlamePlayer_vision.png)

## Features

[Technical documentation](TECHNICAL.md)

### Playback
- Supports MP3, FLAC, M4A/MP4 formats
- Playback controls: Play/Pause, Next, Previous
- Repeat mode, favorites, sorting
- **Artist tracks** — load all tracks by the current artist from the controls bar
- **Similar tracks** — find tracks similar to the currently playing one (genre, tempo, energy, mood)
- Seek bar and volume control
- System media keys
- Automatic switching to a new audio output device when connected (headphones, speakers, etc.)

### Library & Organization
- "Artists" view in the library with cover collages
- Folder scanning with metadata extraction
- SQLite database for track information storage
- Favorites and **Top listened** (top 100 by play count)
- Smart sync: detects folder changes, auto-updates the DB
- Track mood analysis (tempo, energy, mood) via librosa (async, background thread)
- Colored mood star overlay on album art
- DB cleanup for tracks with missing files

### Interface
- Frameless window with custom title bar
- Album art display with ambient blur effect
- Playlist with auto-scroll to current track
- Customizable accent color (15 presets) with optional dynamic color based on album art palette
- System tray mini-widget
- Dark theme with smooth transitions

### Track Sorting
- Sorting mechanism added to the playlist.
- Sort modes: by artist, by title, by newest (mtime), shuffle.
- Controls: dropdown in the right side of the title bar next to the minimize button.
- Sort mode is persisted in config (`.cache/settings.json`, field `playlist_sort_mode`) and applies to all playlists.
- "Newest" mode sorts by file modification time (mtime); falls back to current time if unavailable.
- Changing the sort mode through the UI saves it to config and applies to subsequent folder loads.
- Saved sort mode is automatically applied when loading a new folder (no reset).
- Active track highlight is preserved after changing sort order.

### Tag Editor
- Edit: title, artist, album, genre, year
- Rename file
- Online track info search (iTunes, Deezer API)
- Cover art search and download
- Genre delimiters: `;`, `,`, `/`

### Additional
- Library as a separate process (subprocess)
- IPC communication between player and library
- Dynamic color (from album art)
- System tray icon

### Web Server for Remote Control
- Built-in HTTP server (aiohttp) on port 8080 (configurable, debounced restart)
- Responsive web interface (desktop + mobile)
- Playback controls: Play/Pause, Next/Previous, Seek, Volume
- Playlist loading: folders, Favorites, Top, Similar Tracks
- Display: cover (base64), title, artist, album, playlist with auto-scroll
- Real-time playback status (polling every 1000ms)
- Folder selection from indexed list
- Offline detection with "Player is offline" notification
- REST API for external app control

### Android App for Remote Control
- Playback controls: Play/Pause, Next, Previous
- Repeat, favorites toggle
- Seek bar and volume control
- Styled to match the main player: black theme with dynamic accent color
- Playlists: folders, Top, Favorites, Full Library (5000+ tracks)
- Connection via QR code or manually (IP:PORT)

## Installation

```bash
pip install -r requirements.txt
```

## Running

```bash
python main.py
```

To open the library in a separate window:
```bash
python main.py --library
```

## Requirements

- Python 3.9+
- PySide6 >= 6.6
- mutagen >= 1.47
- Pillow >= 10.0
- aiohttp >= 3.9
- numpy >= 1.24
- librosa (for audio analysis)
- qrcode[pil] (for QR code generation)

## Color Scheme

- Background: `#000000` (black)
- Text: `#FFFFFF` (white)
- Accent: `#ed6a02` (customizable)

## License

GNU General Public License v3.0 (GPL v3)

**Author:** ramzes  
**Website:** [smartoff.net](https://smartoff.net)  
**E-mail:** [ramzes@smartoff.net](mailto:ramzes@smartoff.net)

---

# SonicFlame Player

Современный десктопный аудиоплеер с графическим интерфейсом на Python (PySide6/Qt6).

## Возможности

[Техническая документация](TECHNICAL.md)

### Воспроизведение
- Поддержка форматов MP3, FLAC, M4A/MP4
- Управление воспроизведением: Play/Pause, Next, Previous
- Повтор, избранное, сортировка
- **Все песни исполнителя** — загрузка всех треков текущего исполнителя из панели управления
- **Похожие треки** — поиск треков по жанру, темпу, энергии и настроению
- Seek bar и регулятор громкости
- Системные медиа-клавиши
- Автоматическое переключение на новое аудиоустройство вывода при его подключении (наушники, колонки и т.д.)

### Библиотека и организация
- Представление "Исполнители" в библиотеке с коллажами из обложек
- Сканирование папок с музыкой с извлечением метаданных
- SQLite-база данных для хранения информации о треках
- Избранное и **Топ прослушиваний** (топ-100 по количеству воспроизведений)
- Умный sync: отслеживание изменений в папке, автоматическое обновление БД
- Анализ настроения трека (tempo, energy, mood) через librosa (асинхронный, в отдельном потоке)
- Цветная звезда настроения на обложке
- Очистка БД от треков с отсутствующими файлами

### Интерфейс
- Безрамочное окно с кастомным title bar
- Отображение обложек с эффектом ambient blur
- Плейлист с автоскроллом до текущего трека
- Настраиваемый акцентный цвет (15 пресетов, включая Slate) с возможностью включения динамической смены цвета в зависимости от палитры обложки трека
- Мини-виджет для системного трея
- Тёмная тема с плавными переходами

### Сортировка треков
- Добавлен механизм сортировки треков в плейлисте.
- Режимы сортировки: по исполнителю (artist), по названию (title), по новизне (newest), перемешать (shuffle).
- Управление: выпадающий список сортировки расположен в правом краю титл-бара рядом с кнопкой сворачивания окна.
- Значение режима сортировки хранится в конфиге (.cache/settings.json) в поле `playlist_sort_mode` и применяется ко всем плейлистам.
- По новизне: сортировка по времени изменения файла (mtime). Если mtime недоступен, используется текущее время.
- Изменение режима через UI сохраняется в конфиге и применяется к последующим загрузкам папок.
- При загрузке новой папки сохранённый режим сортировки применяется автоматически (не сбрасывается).
- Подсветка активного трека сохраняется на воспроизводимом треке после смены сортировки.

### Редактор тегов
- Редактирование: title, artist, album, genre, year
- Переименование файла
- Поиск информации о треке онлайн (iTunes, Deezer API)
- Поиск и загрузка обложек
- Разделитель жанров: `;`, `,`, `/`

### Дополнительно
- Библиотека как отдельный процесс (субпроцесс)
- IPC связь между плеером и библиотекой
- Динамический цвет (по обложке трека)
- Системный трей с иконкой

### Веб-сервер для удалённого управления
- Встроенный HTTP-сервер (aiohttp) на порту 8080 (настраивается, debounce-перезапуск 2с)
- Веб-интерфейс с адаптивной вёрсткой (desktop + mobile)
- Управление воспроизведением: Play/Pause, Next/Previous, Seek, Volume
- Загрузка плейлистов: папки, Избранное, Топ, Похожие треки
- Отображение: обложка (base64), название, артист, альбом, плейлист с автоскроллом
- Индикация состояния воспроизведения в реальном времени (polling 1000мс)
- Выбор папки из списка индексированных
- Offline detection с уведомлением "Плеер выключен"
- Поддержка управления через внешние приложения (REST API)

### Android-приложение для удалённого управления
- Управление воспроизведением: Play/Pause, Next, Previous
- Повтор, добавление/удаление избранное
- Seek bar и регулятор громкости
- Стилизация под основной плеер: чёрный с динамическим акцентным цветом
- Плейлисты: загрузка папок, Топ прослушиваний, Избранного, Всей библиотеки (5000+)
- Подключение по QR-коду или вручную (IP:PORT)

## Установка

```bash
pip install -r requirements.txt
```

## Запуск

```bash
python main.py
```

Для запуска библиотеки в отдельном окне:
```bash
python main.py --library
```

## Требования

- Python 3.9+
- PySide6 >= 6.6
- mutagen >= 1.47
- Pillow >= 10.0
- aiohttp >= 3.9
- numpy >= 1.24
- librosa (для анализа аудио)
- qrcode[pil] (для генерации QR-кодов)

## Цветовая схема

- Фон: `#000000` (чёрный)
- Текст: `#FFFFFF` (белый)
- Акцент: `#ed6a02` (настраиваемый)

## Лицензия

GNU General Public License v3.0 (GPL v3)

**Автор:** ramzes  
**Сайт:** [smartoff.net](https://smartoff.net)  
**E-mail:** [ramzes@smartoff.net](mailto:ramzes@smartoff.net)
