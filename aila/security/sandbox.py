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
        # raízes de LEITURA extras: pastas que o USUÁRIO anexou explicitamente
        # (autorização direta). Escrita continua SÓ no workspace (self.root).
        self.read_roots: list[Path] = []

    def add_read_root(self, path: str | Path) -> Path:
        """Autoriza LEITURA de uma pasta anexada pelo usuário (não escrita)."""
        p = Path(path).expanduser().resolve()
        if p not in self.read_roots:
            self.read_roots.append(p)
        return p

    def remove_read_root(self, path: str | Path) -> bool:
        """Remove uma raiz de leitura (revogação). Retorna True se existia."""
        p = Path(path).expanduser().resolve()
        try:
            self.read_roots.remove(p)
            return True
        except ValueError:
            return False

    def read_bases(self) -> list[Path]:
        """Raízes onde a LEITURA é permitida (workspace + pastas anexadas)."""
        return [self.root, *self.read_roots]

    @staticmethod
    def _within(resolved: Path, base: Path) -> bool:
        return resolved == base or base in resolved.parents

    def resolve(self, path: str | Path, *, read: bool = False) -> Path:
        """Resolve ``path`` e valida o confinamento. Escrita (``read=False``) só
        no workspace; leitura (``read=True``) também nas pastas anexadas pelo
        usuário. Aceita caminho relativo (à raiz) ou absoluto.
        """
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        resolved = candidate.resolve()

        bases = self.read_bases() if read else [self.root]
        if not any(self._within(resolved, b) for b in bases):
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
