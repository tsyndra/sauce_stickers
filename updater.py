"""Auto-update: check remote version.json, download exe, replace and restart."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import config
from version import APP_VERSION, DEFAULT_UPDATE_BASE

MANIFEST_NAME = "version.json"
DEFAULT_EXE_NAME = "SauceStickers.exe"


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    source: str
    notes: str = ""


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def current_exe_path() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve()
    return Path(__file__).resolve()


def parse_version(value: str) -> tuple[int, ...]:
    cleaned = value.strip().lstrip("vV")
    parts: list[int] = []
    for chunk in cleaned.split("."):
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts) if parts else (0,)


def is_newer(remote: str, local: str = APP_VERSION) -> bool:
    return parse_version(remote) > parse_version(local)


def get_update_base() -> str:
    """Priority: config → update_base.txt next to exe → DEFAULT_UPDATE_BASE."""
    saved = config.get_update_base()
    if saved:
        return saved

    side = current_exe_path().parent / "update_base.txt"
    try:
        text = side.read_text(encoding="utf-8").strip()
        if text and not text.startswith("#"):
            return text.splitlines()[0].strip()
    except OSError:
        pass

    return (DEFAULT_UPDATE_BASE or "").strip()


def _join_base(base: str, name: str) -> str:
    base = base.rstrip("/\\")
    if base.lower().startswith(("http://", "https://")):
        return f"{base}/{name}"
    return str(Path(base) / name)


def _read_bytes(location: str, timeout: float = 20.0) -> bytes:
    if location.lower().startswith(("http://", "https://")):
        request = urllib.request.Request(
            location,
            headers={"User-Agent": f"SauceStickers/{APP_VERSION}"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()

    path = Path(location)
    if not path.is_file():
        raise FileNotFoundError(f"Файл не найден: {location}")
    return path.read_bytes()


def _download_to_file(
    location: str,
    destination: Path,
    *,
    timeout: float = 60.0,
    progress=None,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".partial")

    if location.lower().startswith(("http://", "https://")):
        request = urllib.request.Request(
            location,
            headers={"User-Agent": f"SauceStickers/{APP_VERSION}"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            with tmp.open("wb") as out:
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
    else:
        src = Path(location)
        total = src.stat().st_size
        done = 0
        with src.open("rb") as inp, tmp.open("wb") as out:
            while True:
                chunk = inp.read(64 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)

    tmp.replace(destination)


def fetch_update_info(base: str | None = None) -> UpdateInfo | None:
    """Return remote update info if newer than APP_VERSION, else None."""
    base = (base if base is not None else get_update_base()).strip()
    if not base:
        raise ValueError(
            "Не задан источник обновлений.\n"
            "Укажите сетевую папку или URL в version.py (DEFAULT_UPDATE_BASE)\n"
            "или в %APPDATA%\\SauceStickers\\config.json → update_base,\n"
            "или в файле update_base.txt рядом с exe."
        )

    manifest_url = _join_base(base, MANIFEST_NAME)
    raw = _read_bytes(manifest_url)
    data = json.loads(raw.decode("utf-8-sig"))
    version = str(data.get("version", "")).strip()
    if not version:
        raise ValueError("В version.json нет поля version")

    if not is_newer(version):
        return None

    file_name = str(data.get("file") or data.get("url") or DEFAULT_EXE_NAME).strip()
    if file_name.lower().startswith(("http://", "https://", "\\\\")) or (
        len(file_name) > 2 and file_name[1] == ":"
    ):
        source = file_name
    else:
        source = _join_base(base, file_name)

    notes = str(data.get("notes") or "").strip()
    return UpdateInfo(version=version, source=source, notes=notes)


def download_update(info: UpdateInfo, *, progress=None) -> Path:
    """Download new exe into a temp file; return its path."""
    suffix = Path(info.source).suffix or ".exe"
    fd, tmp_name = tempfile.mkstemp(prefix="SauceStickers_update_", suffix=suffix)
    os.close(fd)
    target = Path(tmp_name)
    try:
        _download_to_file(info.source, target, progress=progress)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    if target.stat().st_size < 1024:
        target.unlink(missing_ok=True)
        raise RuntimeError("Скачанный файл слишком маленький — обновление прервано")
    return target


def apply_update_and_restart(new_exe: Path) -> None:
    """Replace running frozen exe via a hidden PowerShell helper, then exit."""
    if not is_frozen():
        raise RuntimeError("Автозамена exe работает только в собранном приложении")

    current = current_exe_path()
    pid = os.getpid()
    ps1 = Path(tempfile.gettempdir()) / f"SauceStickers_update_{pid}.ps1"

    def _q(path: Path | str) -> str:
        return "'" + str(path).replace("'", "''") + "'"

    # No cmd/find windows — wait for PID, copy, relaunch.
    script = f"""$ErrorActionPreference = 'Continue'
$pidToWait = {pid}
$src = {_q(new_exe)}
$dst = {_q(current)}
for ($i = 0; $i -lt 120; $i++) {{
  if (-not (Get-Process -Id $pidToWait -ErrorAction SilentlyContinue)) {{ break }}
  Start-Sleep -Milliseconds 500
}}
Start-Sleep -Milliseconds 800
Copy-Item -LiteralPath $src -Destination $dst -Force
if (-not $?) {{
  Start-Sleep -Seconds 1
  Copy-Item -LiteralPath $src -Destination $dst -Force
}}
Remove-Item -LiteralPath $src -Force -ErrorAction SilentlyContinue
Start-Process -FilePath $dst
Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
"""
    ps1.write_text(script, encoding="utf-8")

    creationflags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(ps1),
        ],
        close_fds=True,
        creationflags=creationflags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
