@echo off
REM ============================================================
REM  Aila — rodar do CODIGO-FONTE (dev), com duplo-clique.
REM  Sem build: sobe o backend do repositorio e abre no navegador.
REM  Mudancas no codigo aparecem na hora (backend reinicia sozinho;
REM  front: recarregue o navegador). Ctrl+C encerra.
REM ============================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1" %*
pause
