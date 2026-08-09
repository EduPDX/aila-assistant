@echo off
REM ============================================================
REM  Aila — build + deploy com duplo-clique.
REM  Empacota o backend + Electron e joga o instalador no Downloads.
REM ============================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0desktop\build.ps1" %*
echo.
pause
