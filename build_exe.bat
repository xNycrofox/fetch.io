@echo off
echo ===============================================
echo     Erstelle Fetch.io als einzelne .exe-Datei
echo ===============================================
echo.

echo Starte PyInstaller...
pyinstaller fetchio.spec

echo.
echo ===============================================
echo Build abgeschlossen!
echo Die .exe-Datei befindet sich im Verzeichnis "dist".
echo ===============================================
echo.

pause 