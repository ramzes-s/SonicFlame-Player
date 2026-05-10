"""
Web Interface Template

HTML/JS/CSS for the web player interface.
"""

WEB_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
    <title>SonicFlame Player</title>
    <link rel="icon" type="image/x-icon" href="/Sonic-Flame.ico">
    <style>
        :root { --accent-color: #ed6a02; }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        html, body {
            background: #000; color: #fff;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            height: 100%; width: 100%; overflow-x: hidden;
        }
        body {
            display: flex; justify-content: center; align-items: flex-start;
            padding: 26px 16px; min-height: 100vh;
        }
        .container {
            width: 100%; max-width: 900px;
            display: flex; gap: 4px;
        }
        .player-section {
            display: flex; flex-direction: row; align-items: flex-start;
            gap: 16px; flex-shrink: 0;
            position: sticky;
            top: 26px;
            max-height: calc(100vh - 52px);
            overflow: hidden;
        }
        .player-main {
            display: flex; flex-direction: column; align-items: center;
            width: 44%;
            min-width: 360px; max-width: 420px;
        }
        .cover {
            width: 100%; aspect-ratio: 1;
            max-width: 420px; border-radius: 12px;
            background: #1a1a1a; display: flex; align-items: center; justify-content: center;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5); margin-bottom: 16px;
        }
        .cover img { width: 100%; height: 100%; object-fit: cover; border-radius: 12px; }
        
        .track-info {
            text-align: center; margin-bottom: 16px; width: 100%;
            min-height: 56px;
        }
        .track-title {
            font-size: 15px; font-weight: bold;
            color: #fff; margin-bottom: 4px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .track-artist {
            font-size: 13px; color: var(--accent-color);
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .track-album {
            font-size: 11px; color: #666; margin-top: 2px;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        
        .seek-container { display: flex; align-items: center; gap: 10px; width: 100%; margin-bottom: 12px; }
        .seek-bar {
            flex: 1 1 auto; height: 4px; min-width: 0;
            -webkit-appearance: none; appearance: none;
            background: transparent;
            border-radius: 2px; outline: none; cursor: pointer;
        }
        .seek-bar::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 14px; height: 14px; margin-top: -5px;
            background: var(--accent-color); border-radius: 50%; cursor: pointer;
        }
        .seek-bar::-moz-range-thumb {
            width: 14px; height: 14px;
            background: var(--accent-color); border-radius: 50%; cursor: pointer; border: none;
        }
        .seek-bar::-webkit-slider-runnable-track {
            height: 4px; border-radius: 2px;
            background: linear-gradient(to right, var(--accent-color) var(--seek-before-width, 0%), #333 var(--seek-before-width, 0%));
        }
        .seek-bar::-moz-range-track {
            height: 4px; border-radius: 2px;
            background: linear-gradient(to right, var(--accent-color) var(--seek-before-width, 0%), #333 var(--seek-before-width, 0%));
        }

        .time-display {
            font-size: 11px; color: #fff; white-space: nowrap;
        }
        .time-current { flex: 0 0 auto; }
        .time-total { flex: 0 0 auto; }
        
        .controls {
            display: flex; justify-content: center; align-items: center; gap: 20px; margin-bottom: 12px;
            position: relative;
        }
        .btn {
            background: none; border: none; color: #fff; cursor: pointer;
            transition: color 0.2s; display: flex; align-items: center; justify-content: center;
            padding: 0;
        }
        .btn:hover { color: #ccc; }
        .btn:active { color: #888; }
        .btn svg { fill: currentColor; }
        
        .btn-play {
            width: 78px; height: 78px;
        }
        
        .playlist-section {
            flex: 1; min-width: 0; display: flex; flex-direction: column;
            overflow: hidden;
            border-radius: 8px;
        }
        .playlist {
            background: #0a0a0a; border-radius: 8px;
            flex: 1; overflow-y: auto;
            min-height: 200px;
            max-height: calc(100vh - 80px);
        }
        .playlist::-webkit-scrollbar { width: 6px; }
        .playlist::-webkit-scrollbar-track { background: #0a0a0a; }
        .playlist::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
        .playlist::-webkit-scrollbar-thumb:hover { background: #444; }

        .folder-dropdown::-webkit-scrollbar { width: 4px; }
        .folder-dropdown::-webkit-scrollbar-track { background: #0a0a0a; }
        .folder-dropdown::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }
        .folder-dropdown::-webkit-scrollbar-thumb:hover { background: #444; }
        
        .offline-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(0,0,0,0.95);
            flex-direction: column;
            justify-content: center;
            align-items: center;
            gap: 20px;
            z-index: 1000;
        }
        .offline-overlay.visible { display: flex; }
        .offline-text { color: #888; font-size: 16px; text-align: center; }
        .btn-refresh {
            padding: 12px 24px; background: var(--accent-color); color: #fff;
            border: none; border-radius: 8px; font-size: 14px; cursor: pointer;
        }
        .btn-refresh:hover { opacity: 0.9; }

        .folder-dropdown {
            display: none;
            position: absolute;
            bottom: 5px;
            left: -10px;
            background: #0a0a0a;
            border: 1px solid #333;
            border-radius: 8px;
            min-width: 240px;
            max-height: 480px;
            overflow-y: auto;
            z-index: 100;
        }
        .folder-dropdown.visible { display: block; }
        .folder-item {
            padding: 10px 12px;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #222;
        }
        .folder-item:hover { background: #151515; }
        .folder-item .path {
            color: #fff;
            font-size: 12px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 220px;
        }
        .folder-item .count {
            color: #999;
            font-size: 11px;
            margin-left: 8px;
            flex-shrink: 0;
        }
        
        .playlist-item {
            padding: 10px 12px; border-bottom: 1px solid #1a1a1a; cursor: pointer;
            display: flex; justify-content: space-between; align-items: center;
            height: 52px;
            box-sizing: border-box;
        }
        .playlist-item:hover { background: #151515; }
        .playlist-item.active {
            background: #1a1a1a;
            border-left: 3px solid var(--accent-color);
            padding-left: 9px;
        }
        .playlist-item .info {
            display: flex; flex-direction: column; justify-content: center;
            min-width: 0; flex: 1;
        }
        .playlist-item .title {
            font-size: 13px; color: #fff;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .playlist-item .artist {
            font-size: 11px; color: #666;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .playlist-item .duration {
            font-size: 11px; color: #666; white-space: nowrap; margin-left: 8px;
            flex-shrink: 0;
        }
        
        @media (max-width: 790px) {
            body { padding: 0 12px 12px; }
            .container {
                flex-direction: column;
                align-items: center;
                gap: 6px;
            }
            .player-section {
                width: 100%;
                justify-content: center;
                position: sticky;
                top: 0;
                max-height: none;
                background: #000;
                z-index: 10;
                padding: 12px 0 6px 0;
                box-shadow: 0 4px 12px rgba(0,0,0,0.5);
            }
            .player-main {
                width: 90%;
                max-width: none;
                min-width: 0;
            }
            .cover {
                width: 90%;
                margin-left: auto; margin-right: auto;
            }
            .playlist-section {
                width: 100%;
                min-height: 200px;
            }
            .playlist {
                max-height: none;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="player-section">
            <div class="player-main">
                <div class="cover" id="cover"></div>
                <div class="track-info">
                    <div class="track-title" id="title">-</div>
                    <div class="track-artist" id="artist">-</div>
                    <div class="track-album" id="album">-</div>
                </div>
                <div class="seek-container">
                    <span class="time-display time-current" id="currentTime">0:00</span>
                    <input type="range" class="seek-bar" id="seek" min="0" max="100" value="0">
                    <span class="time-display time-total" id="totalTime">0:00</span>
                </div>
                <div class="controls">
                    <button class="btn" id="folderBtn" title="Выбрать папку">
                        <svg width="26" height="26" viewBox="0 0 24 24"><path d="M10 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2h-8l-2-2z"/></svg>
                    </button>
                    <button class="btn" id="prevBtn">
                        <svg width="32" height="32" viewBox="0 0 24 24"><path d="M6 6h2v12H6zm3.5 6l8.5 6V6z"/></svg>
                    </button>
                    <button class="btn btn-play" id="playBtn">
                        <svg id="playIcon" width="44" height="44" viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg>
                    </button>
                    <button class="btn" id="nextBtn">
                        <svg width="32" height="32" viewBox="0 0 24 24"><path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z"/></svg>
                    </button>
                    <button class="btn" id="heartBtn" title="Избранное">
                        <svg width="28" height="28" viewBox="0 0 24 24"><path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"/></svg>
                    </button>
                    <div class="folder-dropdown" id="folderDropdown">
                        <div class="folder-list" id="folderList"></div>
                    </div>
                </div>
            </div>
        </div>
        <div class="playlist-section">
            <div class="playlist" id="playlist"></div>
        </div>
    </div>
    <div class="offline-overlay" id="offlineOverlay">
        <div class="offline-text">Плеер выключен</div>
        <button class="btn-refresh" onclick="location.reload()">Обновить страницу</button>
    </div>
    <script>
        let currentIndex = -1;
        let currentFilepath = null;
        let isPlaying = false;
        let isOffline = false;
        let pollInterval = null;
        let abortController = null;
        let lastPlaylistHash = '';
        let clientSeekTimer = null;

        function getPlaylistHash(tracks) {
            return tracks.map(t => t.filepath).join('|');
        }

        async function fetchWithTimeout(url, timeout = 3000) {
            const controller = new AbortController();
            const id = setTimeout(() => controller.abort(), timeout);
            try {
                const res = await fetch(url, { signal: controller.signal });
                clearTimeout(id);
                return res;
            } catch (e) {
                clearTimeout(id);
                if (e.name !== 'AbortError') {
                    console.log('fetch error:', e.message, e.name);
                    showOffline();
                }
                return null;
            }
        }

        function formatTime(ms) {
            const s = Math.floor(ms / 1000);
            const m = Math.floor(s / 60);
            return m + ':' + (s % 60).toString().padStart(2, '0');
        }

        function showOffline() {
            isOffline = true;
            clearInterval(pollInterval);
            document.getElementById('offlineOverlay').classList.add('visible');
        }

        function hideOffline() {
            isOffline = false;
            document.getElementById('offlineOverlay').classList.remove('visible');
        }

        function animateSeekBar() {
            const seekBar = document.getElementById('seek');
            const currentTimeDisplay = document.getElementById('currentTime');
            
            let currentValue = parseFloat(seekBar.value);
            let maxValue = parseFloat(seekBar.max);
            
            if (currentValue < maxValue) {
                currentValue += 100;
                seekBar.value = currentValue;
                
                currentTimeDisplay.textContent = formatTime(currentValue);

                const percent = maxValue > 0 ? (currentValue / maxValue) * 100 : 0;
                seekBar.style.setProperty('--seek-before-width', percent + '%');
            }
        }

        let initialLoad = true;

        async function updateStatus() {
            if (isOffline) return;
            const res = await fetchWithTimeout('/api/playing_data');
            if (!res || !res.ok) {
                if (!isOffline) showOffline();
                return;
            }

            hideOffline();

            try {
                const data = await res.json();

                document.documentElement.style.setProperty('--accent-color', data.accent_color);

                const heartIcon = document.getElementById('heartBtn');
                if (heartIcon) {
                    heartIcon.style.color = data.is_favorite ? 'var(--accent-color)' : '#fff';
                }

                const status = data.status;
                const newIndex = data.current_index;
                const newFilepath = data.current_track_filepath;

                const trackChanged = (newIndex !== currentIndex || newFilepath !== currentFilepath) && newIndex !== -1;

                if (trackChanged) {
                    currentIndex = newIndex;
                    currentFilepath = newFilepath;
                    highlightCurrentTrack();
                }

                if (initialLoad) {
                    initialLoad = false;
                    await updateTrackInfo();
                } else if (trackChanged) {
                    await updateTrackInfo();
                }

                const prevPlaying = isPlaying;
                isPlaying = status.playing;
                if (isPlaying && !prevPlaying) {
                    await updateTrackInfo();
                }

                const playIcon = document.getElementById('playIcon');
                playIcon.setAttribute('width', status.playing ? '44' : '44');
                playIcon.innerHTML = status.playing
                    ? '<path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>'
                    : '<path d="M8 5v14l11-7z"/>';

                const seekBar = document.getElementById('seek');
                seekBar.value = status.position;
                seekBar.max = status.duration || 100;
                
                const percent = status.duration > 0 ? (status.position / status.duration) * 100 : 0;
                seekBar.style.setProperty('--seek-before-width', percent + '%');

                document.getElementById('currentTime').textContent = formatTime(status.position);
                document.getElementById('totalTime').textContent = formatTime(status.duration);

                if (status.playing && !clientSeekTimer) {
                    clientSeekTimer = setInterval(animateSeekBar, 100);
                } else if (!status.playing && clientSeekTimer) {
                    clearInterval(clientSeekTimer);
                    clientSeekTimer = null;
                }
            } catch (e) {
                if (!isOffline) showOffline();
            }
        }

        async function updatePlaylist() {
            try {
                const res = await fetch('/api/playlist');
                if (!res.ok) return;
                const tracks = await res.json();
                const container = document.getElementById('playlist');
                if (!container) return;
                if (tracks.length === 0) return;
                lastPlaylistHash = getPlaylistHash(tracks);
                container.innerHTML = tracks.map((t, i) =>
                    '<div class="playlist-item' + (i === currentIndex ? ' active' : '') + '" data-index="' + i + '">' +
                    '<div class="info"><div class="title">' + (t.title || '-') + '</div><div class="artist">' + (t.artist || '-') + '</div></div>' +
                    '<div class="duration">' + formatTime((t.duration || 0) * 1000) + '</div></div>'
                ).join('');
            } catch (e) { console.error(e); }
        }

        async function updateTrackInfo() {
            try {
                const res = await fetch('/api/track');
                if (!res.ok) return;
                const track = await res.json();

                if (!track) return;

                await updatePlaylist();

                document.getElementById('title').textContent = track.title || '-';
                document.getElementById('artist').textContent = track.artist || '-';
                document.getElementById('album').textContent = track.album || '-';
                if (track.cover) {
                    document.getElementById('cover').innerHTML = '<img src="data:image/webp;base64,' + track.cover + '">';
                } else {
                    document.getElementById('cover').innerHTML = '<svg width="48" height="48" viewBox="0 0 24 24" style="fill:#333"><path d="M12 3v10.55c-.59-.34-1.27-.55-2-.55-2.21 0-4 1.79-4 4s1.79 4 4 4 4-1.79 4-4V7h4V3h-6z"/></svg>';
                }
            } catch (e) { console.error(e); }
        }

        function highlightCurrentTrack() {
            const container = document.getElementById('playlist');
            if (!container) return;
            const items = container.querySelectorAll('.playlist-item');
            items.forEach((item, i) => {
                if (i === currentIndex) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });
            const activeItem = container.querySelector('.playlist-item.active');
            if (activeItem) {
                activeItem.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }

        document.getElementById('playBtn').onclick = () => {
            fetch(isPlaying ? '/api/pause' : '/api/play', {method: 'POST'}).then(() => updateTrackInfo());
        };
        document.getElementById('prevBtn').onclick = () => {
            fetch('/api/previous').then(() => updateTrackInfo());
        };
        document.getElementById('nextBtn').onclick = () => {
            fetch('/api/next').then(() => updateTrackInfo());
        };
        document.getElementById('heartBtn').onclick = () => {
            fetch('/api/toggle_favorite', {method: 'POST'}).then(updateStatus);
        };
        document.getElementById('seek').onchange = (e) => fetch('/api/seek', {
            method: 'POST', headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({position: parseInt(e.target.value)})
        });
        document.getElementById('playlist').onclick = (e) => {
            const item = e.target.closest('.playlist-item');
            if (item) {
                currentIndex = parseInt(item.dataset.index);
                highlightCurrentTrack();
                fetch('/api/play_track', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({index: currentIndex})
                }).then(() => updateTrackInfo());
                document.querySelector('.player-section').scrollIntoView({behavior: 'smooth', block: 'start'});
            }
        };

        let folderDropdownVisible = false;

        async function loadFolders() {
            const res = await fetch('/api/folders');
            if (!res.ok) return;
            const folders = await res.json();
            const container = document.getElementById('folderList');
            if (!container) return;
            container.innerHTML = folders.map(f =>
                '<div class="folder-item" data-path="' + f.path + '">' +
                '<span class="path" title="' + f.path + '">' + f.name + '</span>' +
                '<span class="count">' + f.track_count + '</span>' +
                '</div>'
            ).join('');

            container.querySelectorAll('.folder-item').forEach(item => {
                item.onclick = () => {
                    fetch('/api/play_folder', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({path: item.dataset.path})
                    }).then(() => {
                        hideFolderDropdown();
                        updateStatus();
                    });
                };
            });
        }

        function showFolderDropdown() {
            loadFolders();
            document.getElementById('folderDropdown').classList.add('visible');
            folderDropdownVisible = true;
        }

        function hideFolderDropdown() {
            document.getElementById('folderDropdown').classList.remove('visible');
            folderDropdownVisible = false;
        }

        document.getElementById('folderBtn').onclick = (e) => {
            e.stopPropagation();
            if (folderDropdownVisible) {
                hideFolderDropdown();
            } else {
                showFolderDropdown();
            }
        };

        document.addEventListener('click', (e) => {
            if (!e.target.closest('#folderBtn') && !e.target.closest('#folderDropdown')) {
                hideFolderDropdown();
            }
        });

        updateStatus();
        pollInterval = setInterval(updateStatus, 1000);
    </script>
</body>
</html>"""


def get_web_html() -> str:
    """Return the web interface HTML."""
    return WEB_HTML