"""
SVG Icons Module

Contains all UI button icons as inline SVG strings.
This ensures no external file dependencies and consistent visual quality.
"""

# Global accent color (can be overridden in UI)
from musicplayer import config as cfg
ICON_SIZE = 24  # Default size in pixels


def get_accent() -> str:
    return cfg.get_accent_color()


def get_play_svg(size: int = 42, color: str = "#FFFFFF") -> str:
    """Play button SVG - white circle with transparent play triangle."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path fill-rule="evenodd" fill="{color}" d="
            M12 1a11 11 0 1 0 0 22 11 11 0 0 0 0-22z
            M8.85 6.15v11.7l9-5.85z
        "/>
    </svg>
    """


def get_pause_svg(size: int = 42, color: str = "#FFFFFF") -> str:
    """Pause button SVG - white circle with transparent pause bars."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path fill-rule="evenodd" fill="{color}" d="
            M12 1a11 11 0 1 0 0 22 11 11 0 0 0 0-22z
            M8 6.5h3v11h-3z
            M13 6.5h3v11h-3z
        "/>
    </svg>
    """


def get_play_small_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Small play button SVG (for other uses)."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path fill-rule="evenodd" fill="{color}" d="
            M12 1a11 11 0 1 0 0 22 11 11 0 0 0 0-22z
            M8.5 5.5v13l10-6.5z
        "/>
    </svg>
    """


def get_pause_small_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Small pause button SVG (for other uses)."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path fill-rule="evenodd" fill="{color}" d="
            M12 1a11 11 0 1 0 0 22 11 11 0 0 0 0-22z
            M8 6.5h3v11h-3z
            M13 6.5h3v11h-3z
        "/>
    </svg>
    """


def get_next_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Next track button SVG."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M5 4.14v15.72a1 1 0 0 0 1.5.86l11.04-6.86a1 1 0 0 0 0-1.72L6.5 3.28A1 1 0 0 0 5 4.14z" fill="{color}"/>
        <rect x="19" y="4" width="2" height="16" rx="1" fill="{color}"/>
    </svg>
    """


def get_previous_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Previous track button SVG."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M19 19.86V4.14a1 1 0 0 0-1.5-.86L6.46 10.14a1 1 0 0 0 0 1.72l11.04 6.86a1 1 0 0 0 1.5-.86z" fill="{color}"/>
        <rect x="3" y="4" width="2" height="16" rx="1" fill="{color}"/>
    </svg>
    """


def get_shuffle_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Shuffle toggle button SVG."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M16 3h5v5M4 20L20.5 3.5M21 16v5h-5M15 15l6 6M4 4l5 5" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    """


def get_repeat_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Repeat toggle button SVG."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M17 1l4 4-4 4" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M3 11V9a4 4 0 0 1 4-4h14" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M7 23l-4-4 4-4" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M21 13v2a4 4 0 0 1-4 4H3" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    """


def get_repeat_one_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Repeat one track button SVG (repeat mode = one).
    Uses a circle with '1' drawn as a path (not text) since QSvgRenderer doesn't support <text>.
    """
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M17 1l4 4-4 4" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M3 11V9a4 4 0 0 1 4-4h14" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M7 23l-4-4 4-4" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M21 13v2a4 4 0 0 1-4 4H3" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="12" cy="12" r="5" fill="#000" stroke="{color}" stroke-width="1"/>
        <path d="M11.5 9.5 L11.5 14.5 L10.5 14.5 L10.5 13.5 L12.5 13.5 L12.5 14.5 L11.5 14.5" fill="{color}" stroke="{color}" stroke-width="0.5"/>
    </svg>
    """


def get_volume_high_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Volume high SVG."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M11 5L6 9H2v6h4l5 4V5z" fill="{color}"/>
        <path d="M15.54 8.46a5 5 0 0 1 0 7.07" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
        <path d="M19.07 4.93a10 10 0 0 1 0 14.14" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
    </svg>
    """


def get_volume_mute_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Volume mute SVG."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M11 5L6 9H2v6h4l5 4V5z" fill="{color}"/>
        <line x1="23" y1="9" x2="17" y2="15" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
        <line x1="17" y1="9" x2="23" y2="15" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
    </svg>
    """


def get_folder_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Open folder SVG."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    """


def get_music_note_svg(size: int = 200, color: str = "#ed6a02") -> str:
    """Sonic Flame SVG icon for album art placeholder."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 256 256" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <linearGradient id="main-grad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style="stop-color:#ffbc00;stop-opacity:1" />
                <stop offset="50%" style="stop-color:#ff6a00;stop-opacity:1" />
                <stop offset="100%" style="stop-color:#ff3c00;stop-opacity:1" />
            </linearGradient>
        </defs>
        
        <!-- Внешнее разорванное кольцо -->
        <path d="M128 20C68.35 20 20 68.35 20 128C20 187.65 68.35 236 128 236C187.65 236 236 187.65 236 128" 
              stroke="url(#main-grad)" stroke-width="6" stroke-linecap="round" opacity="0.3" />
        
        <!-- Левая малая волна -->
        <path d="M80 140C80 140 90 100 110 110C130 120 120 160 140 170C160 180 180 150 180 150" 
              stroke="url(#main-grad)" stroke-width="14" stroke-linecap="round" />
        
        <!-- Центральная большая волна -->
        <path d="M60 120C60 120 85 40 128 60C171 80 160 180 196 200" 
              stroke="url(#main-grad)" stroke-width="16" stroke-linecap="round" />
        
        <!-- Правая акцентная точка/волна -->
        <circle cx="180" cy="90" r="10" fill="url(#main-grad)" />
        
        <!-- Декоративные штрихи (энергия) -->
        <line x1="128" y1="20" x2="128" y2="40" stroke="url(#main-grad)" stroke-width="4" stroke-linecap="round" />
        <line x1="236" y1="128" x2="216" y2="128" stroke="url(#main-grad)" stroke-width="4" stroke-linecap="round" />
    </svg>
    """


def get_crown_svg(size: int = 14, color: str = "#FFD700") -> str:
    """Crown SVG icon for lossless formats (FLAC, WAV, etc)."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M2 20h20v2H2v-2zM4 18l2-14 4 6 2-8 2 8 4-6 2 14H4z" fill="{color}"/>
    </svg>
    """


def get_heart_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Heart SVG icon for favorites."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 
                 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09
                 C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5
                 c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" fill="{color}"/>
    </svg>
    """


def get_settings_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Settings/gear SVG icon."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58
                 a.49.49 0 0 0 .12-.61l-1.92-3.32a.49.49 0 0 0-.59-.22l-2.39.96
                 c-.5-.38-1.03-.7-1.62-.94l-.36-2.54a.484.484 0 0 0-.48-.41h-3.84
                 c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96
                 a.49.49 0 0 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58
                 c-.05.3-.07.62-.07.94s.02.64.07.94l-2.03 1.58a.49.49 0 0 0-.12.61
                 l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54
                 c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54
                 c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32
                 c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6A3.6 3.6 0 1 1 12 8.4
                 a3.6 3.6 0 0 1 0 7.2z" fill="{color}"/>
    </svg>
    """


def get_library_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Library/collection SVG icon."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M4 20h16v2H4v-2zM6 4v14h2V4H6zm5 0v14h2V4h-2zm5 0v14h2V4h-2z" fill="{color}"/>
    </svg>
    """


def get_top_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Top / trending tracks SVG icon — star or trending chart."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87L18.18 22 12 18.56 5.82 22 7 14.14 2 9.27l6.91-1.01L12 2z"
              fill="{color}"/>
    </svg>
    """

def get_info_svg(size: int = 32, color: str = "#FFFFFF") -> str:
    """Info icon - lowercase 'i' in a circle."""
    r = size / 2
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" stroke="{color}" stroke-width="2"/>
        <text x="12" y="16" text-anchor="middle" fill="{color}" font-size="12" font-weight="bold" font-family="sans-serif">i</text>
    </svg>
    """


def get_warning_svg(size: int = 32, color: str = "#FFFFFF") -> str:
    """Warning icon - triangle with exclamation mark."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 2L2 20h20L12 2z" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>
        <line x1="12" y1="9" x2="12" y2="14" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
        <circle cx="12" cy="17" r="1" fill="{color}"/>
    </svg>
    """


def get_error_svg(size: int = 32, color: str = "#FFFFFF") -> str:
    """Error icon - X in a circle."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" stroke="{color}" stroke-width="2"/>
        <line x1="8" y1="8" x2="16" y2="16" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
        <line x1="16" y1="8" x2="8" y2="16" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
    </svg>
    """


def get_question_svg(size: int = 32, color: str = "#FFFFFF") -> str:
    """Question icon - question mark in a circle."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="10" stroke="{color}" stroke-width="2"/>
        <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="12" cy="17" r="1" fill="{color}"/>
    </svg>
    """


def get_all_music_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """All Music SVG — solid folder with a single note cut out."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
            <mask id="nm">
                <rect width="24" height="24" fill="white"/>
                <ellipse cx="11" cy="16" rx="2.5" ry="1.8" fill="black"/>
                <path d="M11 16V9l4 1.5" stroke="black" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
            </mask>
        </defs>
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" fill="{color}" stroke="{color}" stroke-width="0.5" mask="url(#nm)"/>
    </svg>
    """


def get_artist_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Artist / musician SVG icon (head and shoulders silhouette)."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="8" r="4.5" stroke="{color}" stroke-width="1.5"/>
        <path d="M4 22C4 17.5817 7.58172 14 12 14C16.4183 14 20 17.5817 20 22" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
    </svg>
    """


def get_similar_tracks_svg(size: int = ICON_SIZE, color: str = "#FFFFFF") -> str:
    """Similar tracks search SVG icon (magnifying glass with a music note)."""
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <!-- Magnifying glass -->
        <circle cx="11" cy="11" r="8" stroke="{color}" stroke-width="2"/>
        <line x1="16.5" y1="16.5" x2="21" y2="21" stroke="{color}" stroke-width="2" stroke-linecap="round"/>
        <!-- Music note -->
        <path d="M10 8V14C9.45 13.68 8.75 13.5 8 13.5C6.9 13.5 6 14.4 6 15.5C6 16.6 6.9 17.5 8 17.5C9.1 17.5 10 16.6 10 15.5V9.5L14 8V13.5C13.45 13.18 12.75 13 12 13C10.9 13 10 13.9 10 15V8H10.5L14.5 6.5L15 6V11.5C14.45 11.18 12.75 11 13 11C11.9 11 11 11.9 11 13V6H11.5L15.5 4.5L16 4V9.5C15.45 9.18 14.75 9 14 9C12.9 9 12 9.9 12 11V4H12.5L16.5 2.5L17 2V7.5C16.45 7.18 15.75 7 15 7C13.9 7 13 7.9 13 9V2H13.5L17.5 0.5L18 0V5.5C17.45 5.18 16.75 5 16 5C14.9 5 14 5.9 14 7V0H14.5L18.5 -1.5L19 -2V3.5C18.45 3.18 17.75 -0.1 19 -0.1C19.45 -0.82 19.75 -1 19 -1C17.9 -1 17 -0.1 17 1V-6H17.5L21.5 -7.5L22 -8V-2.5C21.45 -2.82 20.75 -3 20 -3C18.9 -3 18 -2.1 18 -1V-8H18.5L22.5 -9.5L23 -10V-4.5C22.45 -4.82 21.75 -5 21 -5C19.9 -5 19 -4.1 19 -3V-10H19.5L23.5 -11.5L24 -12V-6.5C23.45 -6.82 22.75 -7 22 -7C20.9 -7 20 -6.1 20 -5V-12H20.5L24.5 -13.5L25 -14V-8.5C24.45 -8.82 23.75 -9 23 -9C21.9 -9 21 -8.1 21 -7V-14H21.5L25.5 -15.5L26 -16V-10.5C25.45 -10.82 24.75 -11 24 -11C22.9 -11 22 -10.1 22 -9V-16H22.5L26.5 -17.5L27 -18V-12.5C26.45 -12.82 25.75 -13 25 -13C23.9 -13 23 -12.1 23 -11V-18H23.5L27.5 -19.5L28 -20V-14.5C27.45 -14.82 26.75 -15 26 -15C24.9 -15 24 -14.1 24 -13V-20H24.5L28.5 -21.5L29 -22V-16.5C28.45 -16.82 27.75 -17 27 -17C25.9 -17 25 -16.1 25 -15V-22H25.5L29.5 -23.5L30 -24V-18.5C29.45 -18.82 28.75 -19 28 -19C26.9 -19 26 -18.1 26 -17V-24H26.5L30.5 -25.5L31 -26V-20.5C30.45 -20.82 29.75 -21 29 -21C27.9 -21 27 -20.1 27 -19V-26H27.5L31.5 -27.5L32 -28V-22.5C31.45 -22.82 30.75 -23 30 -23C28.9 -23 28 -22.1 28 -21V-28H28.5L32.5 -29.5L33 -30V-24.5C32.45 -24.82 31.75 -25 31 -25C29.9 -25 29 -24.1 29 -23V-30H29.5L33.5 -31.5L34 -32V-26.5C33.45 -26.82 32.75 -27 32 -27C30.9 -27 30 -26.1 30 -25V-32H30.5L34.5 -33.5L35 -34V-28.5C34.45 -28.82 33.75 -29 33 -29C31.9 -29 31 -28.1 31 -27V-34H31.5L35.5 -35.5L36 -36V-30.5C35.45 -30.82 34.75 -31 34 -31C32.9 -31 32 -30.1 32 -29V-36H32.5L36.5 -37.5L37 -38V-32.5C36.45 -32.82 35.75 -33 35 -33C33.9 -33 33 -32.1 33 -31V-38H33.5L37.5 -39.5L38 -40V-34.5C37.45 -34.82 36.75 -35 36 -35C34.9 -35 34 -34.1 34 -33V-40H34.5L38.5 -41.5L39 -42V-36.5C38.45 -36.82 37.75 -37 37 -37C35.9 -37 35 -36.1 35 -35V-42H35.5L39.5 -43.5L40 -44V-38.5C39.45 -38.82 38.75 -39 38 -39C36.9 -39 36 -38.1 36 -37V-44H36.5L40.5 -45.5L41 -46V-40.5C40.45 -40.82 39.75 -41 39 -41C37.9 -41 37 -40.1 37 -39V-46H37.5L41.5 -47.5L42 -48V-42.5C41.45 -42.82 40.75 -43 40 -43C38.9 -43 38 -42.1 38 -41V-48H38.5L42.5 -49.5L43 -50V-44.5C42.45 -44.82 41.75 -45 41 -45C39.9 -45 39 -44.1 39 -43V-50H39.5L43.5 -51.5L44 -52V-46.5C43.45 -46.82 42.75 -47 42 -47C40.9 -47 40 -46.1 40 -45V-52H40.5L44.5 -53.5L45 -54V-48.5C44.45 -48.82 43.75 -49 43 -49C41.9 -49 41 -48.1 41 -47V-54H41.5L45.5 -55.5L46 -56V-50.5C45.45 -50.82 44.75 -51 44 -51C42.9 -51 42 -50.1 42 -49V-56H42.5L46.5 -57.5L47 -58V-52.5C46.45 -52.82 45.75 -53 45 -53C43.9 -53 43 -52.1 43 -51V-58H43.5L47.5 -59.5L48 -60V-54.5C47.45 -54.82 46.75 -55 46 -55C44.9 -55 44 -54.1 44 -53V-60H44.5L48.5 -61.5L49 -62V-56.5C48.45 -56.82 47.75 -57 47 -57C45.9 -57 45 -56.1 45 -55V-62H45.5L49.5 -63.5L50 -64V-58.5C49.45 -58.82 48.75 -59 49 -59C47.9 -59 47 -58.1 47 -57V-64H47.5L51.5 -65.5L52 -66V-60.5C51.45 -60.82 50.75 -61 51 -61C49.9 -61 49 -60.1 49 -59V-66H49.5L53.5 -67.5L54 -68V-62.5C53.45 -62.82 52.75 -63 53 -63C51.9 -63 51 -62.1 51 -61V-68H51.5L55.5 -69.5L56 -70V-64.5C55.45 -64.82 54.75 -65 55 -65C53.9 -65 53 -64.1 53 -63V-70H53.5L57.5 -71.5L58 -72V-66.5C57.45 -66.82 56.75 -67 57 -67C55.9 -67 55 -66.1 55 -65V-72H55.5L59.5 -73.5L60 -74V-68.5C59.45 -68.82 58.75 -69 59 -69C57.9 -69 57 -68.1 57 -67V-74H57.5L61.5 -75.5L62 -76V-70.5C61.45 -70.82 60.75 -71 61 -71C59.9 -71 59 -70.1 59 -69V-76H61.5L62 -76Z" fill="{color}"/>
    </svg>
    """
