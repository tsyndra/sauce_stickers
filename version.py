"""Application version and default update source."""

from __future__ import annotations

# Bump this on every release (must match dist/version.json after build.bat).
APP_VERSION = "1.4.4"

# GitHub Releases assets: version.json + SauceStickers.exe
# https://github.com/tsyndra/sauce_stickers/releases/latest/download/...
DEFAULT_UPDATE_BASE = (
    "https://github.com/tsyndra/sauce_stickers/releases/latest/download"
)
