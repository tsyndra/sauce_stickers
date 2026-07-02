@echo off
setlocal

python -m pip install -r requirements.txt
python -m PyInstaller --onefile --windowed --name SauceStickers main.py

echo.
echo Готово: dist\SauceStickers.exe
pause
