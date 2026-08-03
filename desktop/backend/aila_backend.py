"""Entry point do backend para empacotar com PyInstaller.

Gera um executável (aila-backend.exe) que sobe o servidor FastAPI da Aila.
O Electron chama este exe quando o app está empacotado (ver electron/main.js).
"""

from aila.main import run

if __name__ == "__main__":
    run()
