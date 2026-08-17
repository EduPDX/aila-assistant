"""Gera o Code Graph PRÉ-CONSTRUÍDO p/ embutir no .exe.

O app empacotado (PyInstaller) não carrega as fontes .py de ``aila/`` como
arquivos varráveis (ficam compiladas no PYZ), então o CodeGraph não consegue
construir o grafo em runtime. Este script roda no BUILD (com o repositório
presente), gera ``code_graph.prebuilt.db`` e o build o embute (--add-data);
o GraphService usa esse arquivo quando não encontra fontes.
"""

from __future__ import annotations

from pathlib import Path

from aila.cognition.graph import CodeGraph, GraphStore
from aila.core.config import PROJECT_ROOT

out = Path("code_graph.prebuilt.db")
for p in (out, Path(f"{out}-wal"), Path(f"{out}-shm")):
    p.unlink(missing_ok=True)

st = GraphStore(out)
rep = CodeGraph(st, PROJECT_ROOT).build(subdir="aila")
st.recompute_importance()
st.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")   # consolida o WAL no .db
st.close()
print(f"prebuilt code graph: {rep}")
