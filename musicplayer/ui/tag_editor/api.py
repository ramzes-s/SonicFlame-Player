import json
import logging
import urllib.request

logger = logging.getLogger(__name__)


def _search_itunes_covers_static(artist, album):
    results = []
    query = urllib.request.quote(f"{artist} {album}".strip())
    url = f"https://itunes.apple.com/search?term={query}&media=music&limit=10"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for item in data.get("results", []):
            if item.get("wrapperType") != "collection":
                continue
            art_url = item.get("artworkUrl100", "")
            if not art_url:
                continue
            art_url = art_url.replace("100x100", "600x600")
            title = item.get("collectionName", "")
            a_name = item.get("artistName", "")
            label = f"{a_name} — {title}" if title else a_name
            try:
                req_img = urllib.request.Request(art_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req_img, timeout=5) as resp_img:
                    img_data = resp_img.read()
                results.append((label, img_data))
            except Exception as e:
                logger.warning("iTunes cover image download failed: %s", e)
    except Exception as e:
        logger.warning("iTunes cover search failed: %s", e)
    return results


def _search_deezer_covers_static(artist, album):
    results = []
    query = urllib.request.quote(f"{artist} {album}".strip())
    url = f"https://api.deezer.com/search/album?q={query}&limit=10"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for item in data.get("data", []):
            cover_url = item.get("cover_xl", "") or item.get("cover_big", "")
            if not cover_url:
                continue
            title = item.get("title", "")
            artist_name = item.get("artist", {}).get("name", "")
            label = f"{artist_name} — {title}" if title else artist_name
            try:
                req_img = urllib.request.Request(cover_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req_img, timeout=5) as resp_img:
                    img_data = resp_img.read()
                results.append((label, img_data))
            except Exception as e:
                logger.warning("Deezer cover image download failed: %s", e)
    except Exception as e:
        logger.warning("Deezer cover search failed: %s", e)
    return results


def _search_itunes_tracks_static(artist, title):
    results = []
    params_parts = []
    if artist:
        params_parts.append(f"artistTerm={urllib.request.quote(artist)}")
    if title:
        params_parts.append(f"term={urllib.request.quote(title)}")
    params = "&".join(params_parts) + "&media=music&entity=song&limit=15"
    url = f"https://itunes.apple.com/search?{params}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for item in data.get("results", []):
            item["trackId"] = item.get("trackId", hash(item.get("trackName", "")))
            item["source"] = "iTunes"
            results.append(item)
    except Exception as e:
        logger.warning("iTunes track search failed: %s", e)
    return results


def _search_deezer_tracks_static(artist, title):
    results = []
    query = urllib.request.quote(f"{artist} {title}".strip())
    url = f"https://api.deezer.com/search?q={query}&limit=10"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        for item in data.get("data", []):
            track_data = {
                "trackId": item.get("id", hash(item.get("title", ""))),
                "trackName": item.get("title", ""),
                "artistName": item.get("artist", {}).get("name", ""),
                "collectionName": item.get("album", {}).get("title", ""),
                "releaseDate": item.get("release_date", ""),
                "genres": [],
                "primaryGenreName": item.get("genre", ""),
                "trackTimeMillis": item.get("duration", 0) * 1000 if item.get("duration") else 0,
                "artworkUrl100": item.get("album", {}).get("cover_xl", "") or item.get("album", {}).get("cover_big", ""),
                "source": "Deezer",
            }
            results.append(track_data)
    except Exception as e:
        logger.warning("Deezer track search failed: %s", e)
    return results