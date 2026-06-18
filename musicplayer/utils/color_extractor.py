"""
Dynamic Color Extractor

Extracts dominant accent color from album cover art using Pillow.
Handles dark/desaturated covers by boosting brightness and saturation,
and adds subtle accent tint to grayscale/monochrome covers.
"""

from PIL import Image
from colorsys import rgb_to_hsv, hsv_to_rgb
import io


# Minimum brightness for the final accent color (for normal covers)
MIN_V = 0.85
# Minimum saturation for the final accent color (for normal covers)
MIN_S = 0.70
# Threshold: pixels below this saturation are considered "gray"
GRAY_THRESHOLD = 0.15
# Threshold: if fraction of colored pixels is below this, treat as grayscale cover
GRAY_COVER_THRESHOLD = 0.05


def _boost_color(r: int, g: int, b: int) -> tuple[int, int, int]:
    """Boost a color's saturation and brightness for UI accent usage (normal covers)."""
    h, s, v = rgb_to_hsv(r / 255, g / 255, b / 255)

    if s >= MIN_S and v >= MIN_V:
        return r, g, b

    s = max(s, MIN_S)
    v = max(v, MIN_V)

    nr, ng, nb = hsv_to_rgb(h, s, v)
    return int(nr * 255), int(ng * 255), int(nb * 255)


def _boost_color_for_gray(r: int, g: int, b: int) -> tuple[int, int, int]:
    """
    Boost color for borderline-gray covers (5-10% colored) — only brightness,
    preserve the pastel saturation.
    """
    MIN_S_GRAY = 0.25
    h, s, v = rgb_to_hsv(r / 255, g / 255, b / 255)
    s = max(s, MIN_S_GRAY)
    v = max(v, MIN_V)
    nr, ng, nb = hsv_to_rgb(h, s, v)
    return int(nr * 255), int(ng * 255), int(nb * 255)


def _mix_with_color(r: int, g: int, b: int, neutral_r: int, neutral_g: int, neutral_b: int, neutral_ratio: float) -> tuple[int, int, int]:
    """
    Mix a color with a neutral tone (white or gray).
    neutral_ratio=0 → pure neutral, neutral_ratio=1 → original color.
    """
    nr = int(r * neutral_ratio + neutral_r * (1 - neutral_ratio))
    ng = int(g * neutral_ratio + neutral_g * (1 - neutral_ratio))
    nb = int(b * neutral_ratio + neutral_b * (1 - neutral_ratio))
    return min(nr, 255), min(ng, 255), min(nb, 255)


def _to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def _default_color() -> str:
    """Fallback to default accent."""
    from musicplayer import config as cfg
    return cfg.get_accent_color()


def extract_accent_color(cover_data: bytes) -> str:
    """
    Extract a dominant accent color from album cover art.

    Algorithm:
    1. Quantize image to find palette colors
    2. Separate into "colored" (S >= GRAY_THRESHOLD) and "gray" pixels
    3. If colored pixels < GRAY_COVER_THRESHOLD (5%):
       - Compute weighted average hue of colored pixels
       - Mix the hue with white/gray heavily → almost-white with subtle tint
       - Very low saturation floor to keep it subtle
    4. If colored pixels between 5% and 10%:
       - Same averaging, but mix less → pastel tint
    5. Otherwise (normal colorful cover > 10%):
       - Score colors by frequency × saturation × brightness
       - Take the top scoring color and boost S/V to minimums

    Args:
        cover_data: Raw image bytes (JPEG, PNG, WebP, etc.)

    Returns:
        Hex color string (e.g. "#cdffd5")
    """
    try:
        img = Image.open(io.BytesIO(cover_data)).convert("RGB")
        img.thumbnail((128, 128))

        # Quantize to small palette
        quantized = img.quantize(colors=16, method=Image.Quantize.MEDIANCUT)
        palette = quantized.getpalette()

        # Count pixel occurrences
        color_counts: dict[tuple[int, int, int], int] = {}
        pixels = list(quantized.getdata())
        for px in pixels:
            idx = px * 3
            rgb = (palette[idx], palette[idx + 1], palette[idx + 2])
            color_counts[rgb] = color_counts.get(rgb, 0) + 1

        total_pixels = sum(color_counts.values())
        if total_pixels == 0:
            return _default_color()

        # Classify pixels
        gray_pixels_count = 0
        black_count = 0
        white_count = 0

        colored_entries = []  # (h, s, v, count, rgb)

        for rgb, count in color_counts.items():
            h, s, v = rgb_to_hsv(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)

            if s >= GRAY_THRESHOLD:
                colored_entries.append((h, s, v, count, rgb))
            else:
                gray_pixels_count += count
                # Track black vs white ratio among gray pixels
                brightness = (rgb[0] + rgb[1] + rgb[2]) / (3 * 255)
                if brightness < 0.3:
                    black_count += count
                elif brightness > 0.7:
                    white_count += count

        colored_total = sum(e[3] for e in colored_entries)
        colored_fraction = colored_total / total_pixels

        if colored_fraction < GRAY_COVER_THRESHOLD:
            # Very few colored pixels (< 5%) → almost-white with subtle tint
            if colored_entries:
                sin_sum = 0.0
                cos_sum = 0.0
                total_weight = 0.0
                for h, s, v, count, rgb in colored_entries:
                    w = count * s
                    sin_sum += __import__('math').sin(2 * __import__('math').pi * h) * w
                    cos_sum += __import__('math').cos(2 * __import__('math').pi * h) * w
                    total_weight += w

                if total_weight > 0:
                    avg_h = (__import__('math').atan2(sin_sum, cos_sum) / (2 * __import__('math').pi)) % 1.0

                    # Start with very low saturation for subtle tint
                    rr, gg, bb = hsv_to_rgb(avg_h, 0.15, 1.0)
                    rr, gg, bb = int(rr * 255), int(gg * 255), int(bb * 255)

                    # Determine neutral color: white or gray based on black/white ratio
                    if black_count > white_count:
                        # More black → use gray as neutral
                        neutral = (180, 180, 180)
                    else:
                        neutral = (255, 255, 255)

                    # Very high neutral ratio → almost all neutral
                    # 0% colored → 0.97 neutral, 5% colored → 0.88 neutral
                    neutral_ratio = 1.0 - (colored_fraction / GRAY_COVER_THRESHOLD) * 0.09
                    neutral_ratio = max(0.88, min(0.97, neutral_ratio))

                    rr, gg, bb = _mix_with_color(rr, gg, bb, *neutral, neutral_ratio)

                    # Minimal boost — just brightness, keep saturation very low
                    boosted = _boost_color_for_very_gray(rr, gg, bb)
                else:
                    boosted = (237, 106, 2)
            else:
                boosted = (237, 106, 2)

        elif colored_fraction < 0.10:
            # 5-10% colored → pastel tint
            if colored_entries:
                sin_sum = 0.0
                cos_sum = 0.0
                total_weight = 0.0
                for h, s, v, count, rgb in colored_entries:
                    w = count * s
                    sin_sum += __import__('math').sin(2 * __import__('math').pi * h) * w
                    cos_sum += __import__('math').cos(2 * __import__('math').pi * h) * w
                    total_weight += w

                if total_weight > 0:
                    avg_h = (__import__('math').atan2(sin_sum, cos_sum) / (2 * __import__('math').pi)) % 1.0

                    rr, gg, bb = hsv_to_rgb(avg_h, 0.20, 1.0)
                    rr, gg, bb = int(rr * 255), int(gg * 255), int(bb * 255)

                    # Determine neutral: white or gray based on black/white ratio
                    if black_count > white_count:
                        neutral = (160, 160, 160)
                    else:
                        neutral = (255, 255, 255)

                    # 5% → 0.93 neutral, 10% → 0.60 neutral
                    neutral_ratio = 1.0 - (colored_fraction - GRAY_COVER_THRESHOLD) / 0.05 * 0.33
                    neutral_ratio = max(0.60, min(0.93, neutral_ratio))

                    rr, gg, bb = _mix_with_color(rr, gg, bb, *neutral, neutral_ratio)

                    boosted = _boost_color_for_gray(rr, gg, bb)
                else:
                    boosted = (237, 106, 2)
            else:
                boosted = (237, 106, 2)

        else:
            # Normal cover (> 10% colored): score by frequency × saturation × brightness
            scored = []
            for h, s, v, count, rgb in colored_entries:
                if rgb == (0, 0, 0) or rgb == (255, 255, 255):
                    continue
                if v < 0.1:
                    continue
                score = count * max(s, 0.3) * max(v, 0.4)
                scored.append((score, rgb))

            if scored:
                scored.sort(key=lambda x: x[0], reverse=True)
                _, best_rgb = scored[0]
                boosted = _boost_color(*best_rgb)
            else:
                boosted = (237, 106, 2)

        return _to_hex(*boosted)

    except Exception as e:
        print(f"extract_accent_color: color extraction failed: {e}")

    return _default_color()


def _boost_color_for_very_gray(r: int, g: int, b: int) -> tuple[int, int, int]:
    """
    Minimal boost for very-gray covers — just ensure brightness,
    keep saturation very low (subtle tint on white/gray).
    """
    MIN_S_VERY_GRAY = 0.15
    h, s, v = rgb_to_hsv(r / 255, g / 255, b / 255)
    s = max(s, MIN_S_VERY_GRAY)
    v = max(v, MIN_V)
    nr, ng, nb = hsv_to_rgb(h, s, v)
    return int(nr * 255), int(ng * 255), int(nb * 255)


def extract_accent_color_from_path(cover_path: str) -> str:
    """Extract accent color from a cover art file on disk."""
    try:
        with open(cover_path, "rb") as f:
            cover_data = f.read()
        return extract_accent_color(cover_data)
    except Exception as e:
        print(f"extract_accent_color_from_path: failed for {cover_path}: {e}")
        return _default_color()
