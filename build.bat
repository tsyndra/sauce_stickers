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
echo Выложите оба файла в GitHub Release (latest):
echo   https://github.com/tsyndra/sauce_stickers/releases
echo Пример:
echo   gh release create vX.Y.Z dist\SauceStickers.exe dist\version.json --title "vX.Y.Z"
echo.
pause
