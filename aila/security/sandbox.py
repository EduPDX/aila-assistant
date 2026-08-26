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
        # (autorização direta). Escrita: workspace + write_roots (config opt-in).
        self.read_roots: list[Path] = []
        # raízes de ESCRITA extras (ex.: Documentos/Desktop) — só as que o usuário
        # habilitou em security.write_roots. Vazio = escrita SÓ no workspace.
        self.write_roots: list[Path] = []

    def add_read_root(self, path: str | Path) -> Path:
        """Autoriza LEITURA de uma pasta anexada pelo usuário (não escrita)."""
        p = Path(path).expanduser().resolve()
        if p not in self.read_roots:
            self.read_roots.append(p)
        return p

    def add_write_root(self, path: str | Path) -> Path:
        """Autoriza ESCRITA numa pasta extra (ex.: ~/Documents). Opt-in do usuário
        via config; a escrita ainda passa pelo gate de permissão (confirmação)."""
        p = Path(path).expanduser().resolve()
        if p not in self.write_roots:
            self.write_roots.append(p)
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
        """Raízes onde a LEITURA é permitida (workspace + anexadas + escrita)."""
        return [self.root, *self.read_roots, *self.write_roots]

    def write_bases(self) -> list[Path]:
        """Raízes onde a ESCRITA é permitida (workspace + write_roots opt-in)."""
        return [self.root, *self.write_roots]

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

        bases = self.read_bases() if read else self.write_bases()
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
