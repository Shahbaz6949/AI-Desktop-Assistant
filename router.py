from __future__ import annotations

import os
import re
import subprocess
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus


@dataclass
class RouteResult:
    handled: bool
    action_text: str = ""


def _open_with_chrome(url: str, chrome_path: str | None) -> bool:
    try:
        if chrome_path:
            cp = Path(chrome_path)
            if cp.exists():
                subprocess.Popen([str(cp), "--new-window", url], close_fds=True)
                return True
        return False
    except Exception:
        return False


def _open_chrome_app(chrome_path: str | None) -> bool:
    # Open Chrome itself (best effort)
    try:
        if chrome_path:
            cp = Path(chrome_path)
            if cp.exists():
                subprocess.Popen([str(cp)], close_fds=True)
                return True
        # fallback: rely on PATH association
        subprocess.Popen("chrome", shell=True)
        return True
    except Exception:
        return False


def open_url(url: str, chrome_preferred: bool, chrome_path: str | None) -> bool:
    if chrome_preferred and _open_with_chrome(url, chrome_path):
        return True
    try:
        os.startfile(url)  # type: ignore[attr-defined]
        return True
    except Exception:
        try:
            return webbrowser.open(url, new=1)
        except Exception:
            return False


def open_path(path_str: str) -> bool:
    try:
        p = Path(path_str).expanduser()
        if p.exists():
            os.startfile(str(p))  # type: ignore[attr-defined]
            return True
    except Exception:
        pass
    return False


def route_command(text: str,
                  chrome_preferred: bool = True,
                  chrome_path: str | None = None,
                  allow_open_file: bool = True,
                  allow_open_url: bool = True,
                  allow_open_app: bool = True) -> RouteResult:
    t = (text or "").strip()
    t_norm = re.sub(r"\s+", " ", t).strip().lower()

    # OPEN CHROME
    if t_norm in ("open chrome", "open google chrome", "chrome open"):
        ok = allow_open_app and _open_chrome_app(chrome_path)
        return RouteResult(True, "Opening Chrome" if ok else "Could not open Chrome")

    # OPEN YOUTUBE
    if t_norm in ("open youtube", "youtube open", "open yt"):
        ok = allow_open_url and open_url("https://www.youtube.com", chrome_preferred, chrome_path)
        return RouteResult(True, "Opening YouTube" if ok else "Could not open YouTube")

    # OPEN LINKEDIN
    if t_norm in ("open linkedin", "linkedin open"):
        ok = allow_open_url and open_url("https://www.linkedin.com", chrome_preferred, chrome_path)
        return RouteResult(True, "Opening LinkedIn" if ok else "Could not open LinkedIn")

    # GOOGLE SEARCH (explicit)
    m = re.match(r"^(search on google|google search|search google)\s+(.+)$", t_norm)
    if m:
        q = m.group(2).strip()
        url = "https://www.google.com/search?q=" + quote_plus(q)
        ok = allow_open_url and open_url(url, chrome_preferred, chrome_path)
        return RouteResult(True, f"Searching Google: {q}" if ok else "Could not open Google search")

    # GOOGLE SEARCH (short)
    m = re.match(r"^search\s+(.+)$", t_norm)
    if m:
        q = m.group(1).strip()
        url = "https://www.google.com/search?q=" + quote_plus(q)
        ok = allow_open_url and open_url(url, chrome_preferred, chrome_path)
        return RouteResult(True, f"Searching Google: {q}" if ok else "Could not open Google search")

    # YOUTUBE SEARCH
    m = re.match(r"^(youtube search|search youtube)\s+(.+)$", t_norm)
    if m:
        q = m.group(2).strip()
        url = "https://www.youtube.com/results?search_query=" + quote_plus(q)
        ok = allow_open_url and open_url(url, chrome_preferred, chrome_path)
        return RouteResult(True, f"Searching YouTube: {q}" if ok else "Could not open YouTube search")

    # YOUTUBE PLAY (opens results; user clicks first)
    m = re.match(r"^(play|play on youtube)\s+(.+)$", t_norm)
    if m:
        q = m.group(2).strip()
        url = "https://www.youtube.com/results?search_query=" + quote_plus(q)
        ok = allow_open_url and open_url(url, chrome_preferred, chrome_path)
        return RouteResult(True, f"Playing on YouTube: {q}" if ok else "Could not open YouTube")

    # OPEN URL
    m = re.match(r"^open\s+(https?://\S+)$", t_norm)
    if m:
        url = m.group(1)
        ok = allow_open_url and open_url(url, chrome_preferred, chrome_path)
        return RouteResult(True, f"Opening {url}" if ok else "Could not open link")

    # OPEN FILE <path>
    m = re.match(r"^open file\s+(.+)$", t, flags=re.IGNORECASE)
    if m and allow_open_file:
        p = m.group(1).strip().strip('"')
        ok = open_path(p)
        return RouteResult(True, "Opening file" if ok else "File not found")

    # OPEN APP <command>
    m = re.match(r"^open app\s+(.+)$", t, flags=re.IGNORECASE)
    if m and allow_open_app:
        cmd = m.group(1).strip().strip('"')
        try:
            subprocess.Popen(cmd, shell=True)
            return RouteResult(True, "Opening app")
        except Exception:
            return RouteResult(True, "Could not open app")

    return RouteResult(False, "")
