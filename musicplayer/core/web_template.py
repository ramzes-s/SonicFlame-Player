"""
Web Interface Template

HTML/JS/CSS for the web player interface.
Loads from res/web_templates/ at runtime.
"""

import sys
from pathlib import Path


def _templates_dir() -> Path:
    """Return path to res/web_templates/ directory (works in dev and frozen modes)."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS) / "res" / "web_templates"
    return Path(__file__).resolve().parent.parent.parent / "res" / "web_templates"


def get_web_html() -> str:
    """Return the full web interface HTML with embedded CSS and JS."""
    tpl = _templates_dir()
    css = (tpl / "style.css").read_text(encoding="utf-8")
    js = (tpl / "app.js").read_text(encoding="utf-8")
    html = (tpl / "index.html").read_text(encoding="utf-8")
    return html.replace("{css}", css).replace("{js}", js)
