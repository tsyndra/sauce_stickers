@echo off
setlocal

python -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

python -m PyInstaller --noconfirm --onefile --windowed --name SauceStickers main.py
if errorlevel 1 exit /b 1

python -c "import json; from pathlib import Path; from version import APP_VERSION; Path('dist').mkdir(exist_ok=True); Path('dist/version.json').write_text(json.dumps({'version': APP_VERSION, 'file': 'SauceStickers.exe', 'notes': ''}, ensure_ascii=False, indent=2), encoding='utf-8'); print('version.json', APP_VERSION)"

echo.
echo Готово:
echo   dist\SauceStickers.exe
echo   dist\version.json
echo.
echo Скопируйте оба файла в папку обновлений (сетевая шара / HTTP).
echo Источник задаётся в version.py → DEFAULT_UPDATE_BASE
echo или update_base.txt рядом с exe на филиале.
echo.
pause
