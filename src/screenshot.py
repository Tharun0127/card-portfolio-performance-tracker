"""Take screenshots of docs/index.html with a headless Chromium browser (Edge or Chrome).

This step is optional. If no browser is found the build carries on and the existing
images in docs/img are left as they are.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from src.paths import DOCS_DIR

IMG_DIR = DOCS_DIR / "img"

# name: (url suffix, window height)
SHOTS = {
    "page1_overview": ("?theme=light#overview", 1130),
    "page2_bridge": ("?theme=light#bridge", 1060),
    "page2_bridge_exit_run_rate": ("?theme=light&scenario=B#bridge", 1060),
    "page3_heatmap": ("?theme=light#heatmap", 1330),
    "page4_attrition": ("?theme=light#attrition", 1480),
}

CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_browser() -> str | None:
    for path in CANDIDATES:
        if Path(path).exists():
            return path
    for name in ("msedge", "google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def main() -> None:
    browser = find_browser()
    if browser is None:
        print("No Edge or Chrome found. Skipping screenshots.")
        return

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    page = (DOCS_DIR / "index.html").resolve().as_uri()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as profile:
        for name, (suffix, height) in SHOTS.items():
            target = IMG_DIR / f"{name}.png"
            target.unlink(missing_ok=True)
            subprocess.run(
                [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                 "--no-first-run", f"--user-data-dir={profile}",
                 f"--window-size=1180,{height}", "--virtual-time-budget=4000",
                 f"--screenshot={target}", page + suffix],
                check=False, capture_output=True, timeout=120,
            )
            # The browser launcher can return before the file is written, so wait for it.
            deadline = time.time() + 45
            while not target.exists() and time.time() < deadline:
                time.sleep(0.5)
            time.sleep(1.0)
            status = "ok" if target.exists() else "FAILED"
            print(f"  {name}.png {status}")


if __name__ == "__main__":
    main()
