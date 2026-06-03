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

async function fetchWithTimeout(url, options = {}, timeout = 3000) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    try {
        const res = await fetch(url, { ...options, signal: controller.signal });
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
    const res = await fetchWithTimeout('/api/playing_data', {method: 'POST'}, 3000);
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
        const res = await fetch('/api/playlist', {method: 'POST'});
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
        const res = await fetch('/api/track', {method: 'POST'});
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
    fetch('/api/previous', {method: 'POST'}).then(() => updateTrackInfo());
};
document.getElementById('nextBtn').onclick = () => {
    fetch('/api/next', {method: 'POST'}).then(() => updateTrackInfo());
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
    const res = await fetch('/api/folders', {method: 'POST'});
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
