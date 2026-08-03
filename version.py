"""Application version and default update source."""

from __future__ import annotations

# Bump this on every release (must match dist/version.json after build.bat).
APP_VERSION = "1.1.0"

# Folder or HTTP URL with version.json + SauceStickers.exe.
# Examples:
#   r"\\fileserver\Share\SauceStickers"
#   "https://example.com/sauce_stickers"
# Empty = автопроверка выключена, пока не зададите путь (см. README).
DEFAULT_UPDATE_BASE = ""
