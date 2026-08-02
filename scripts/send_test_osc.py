"""Envia estados de avatar de teste via OSC — para validar o receptor no Unreal.

Uso (com o venv ativo e o extra [avatar] instalado):

    python scripts/send_test_osc.py                # 127.0.0.1:8000
    python scripts/send_test_osc.py 127.0.0.1 8000

Deixe o Unreal rodando com o BP_AilaReceiver (OSC Server na mesma porta). Este
script manda uma sequência de estados (pensando, feliz+gesto, confuso, falando)
a cada 1,5 s. Você deve ver as mensagens /aila/* chegando no Unreal.
"""

from __future__ import annotations

import sys
import time

from aila.avatar.emotion_engine import EmotionEngine
from aila.avatar.osc_bridge import OSCAvatarBridge


def main() -> None:
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000

    bridge = OSCAvatarBridge(host, port)
    e = EmotionEngine()

    sequence = [
        ("pensando", e.thinking()),
        ("feliz + gesto", e.from_text("Pronto, funcionou!")),
        ("confiante (explicando)", e.from_text("Recomendo a seguinte solução.")),
        ("confuso", e.from_text("Hmm, encontrei um erro no traceback...")),
        ("ouvindo", e.listening()),
        ("neutro", e.idle()),
    ]

    print(f"Enviando estados de teste para OSC {host}:{port} (Ctrl+C para parar)\n")
    try:
        while True:
            for label, state in sequence:
                p = state.to_event_payload()
                bridge.send(p)
                print(f"  -> {label:24} emotion={p['emotion']:10} gesture={p['gesture']}")
                time.sleep(1.5)
            print("--- repetindo ---")
    except KeyboardInterrupt:
        print("\nencerrado.")


if __name__ == "__main__":
    main()
