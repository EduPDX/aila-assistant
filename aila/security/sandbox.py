"""Sandbox de caminhos: garante que operações de arquivo fiquem confinadas
a uma raiz permitida, prevenindo path traversal (``..``) e acesso ao sistema.
"""

from __future__ import annotations

from pathlib import Path


class SandboxViolation(Exception):
    """Levantada quando um caminho tenta escapar da raiz do sandbox."""


class PathSandbox:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def resolve(self, path: str | Path) -> Path:
        """Resolve ``path`` relativo à raiz e valida que continua dentro dela.

        Aceita tanto caminhos relativos quanto absolutos, mas o resultado
        final DEVE estar contido em ``self.root``.
        """
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()

        if resolved != self.root and self.root not in resolved.parents:
            raise SandboxViolation(
                f"Caminho fora do sandbox: {resolved} (raiz: {self.root})"
            )
        return resolved

    def is_inside(self, path: str | Path) -> bool:
        try:
            self.resolve(path)
            return True
        except SandboxViolation:
            return False
