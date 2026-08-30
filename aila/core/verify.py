"""Auto-verificação e lint de arquivos recém-escritos: sintaxe (compile/node/
gofmt/json/toml/yaml) e lint leve (ruff --select F). Realimenta erros no
contexto para o modelo se autocorrigir. Funções puras — extraídas de
engine.py (Fase 2). Inclui os conjuntos de ferramentas de ESCRITA usados pela
serialização de escrita e pela verificação. Re-exportado pelo engine para
compatibilidade (testes e chamadas existentes importam de aila.core.engine)."""
from __future__ import annotations

import json

_VERIFY_WRITE_TOOLS = {"file.write", "file.edit", "code.write_file"}
# Ferramentas que ALTERAM estado → executadas em SÉRIE (as de leitura vão em
# paralelo). Faltavam file.copy/file.mkdir/project.add aqui: rodavam concorrentes,
# com risco de corrida ao mexer nos mesmos arquivos.
_WRITE_TOOLS = {
    "file.write", "file.edit", "file.delete", "file.move", "file.copy", "file.mkdir",
    "code.write_file", "code.execute", "code.run", "memory.save", "project.add",
}
# Ferramentas que, quando dão OK, significam "o arquivo foi mesmo gravado/movido"
# (usado p/ decidir se a rede de segurança precisa salvar por conta própria).
_WRITE_OK_TOOLS = _VERIFY_WRITE_TOOLS | {"file.copy", "file.move", "file.mkdir"}


def _verr(lang: str, name: str, detail: str) -> str:
    """Mensagem padrão de falha de sintaxe (o prefixo ❌ VERIFICAÇÃO é o gancho que
    o system prompt manda o modelo priorizar)."""
    return (f"❌ VERIFICAÇÃO: sintaxe {lang} inválida em {name}: {detail}. "
            "Corrija antes de continuar.")


def _verify_external(cmd: list[str], name: str, lang: str) -> str | None:
    """Check de sintaxe via ferramenta EXTERNA (ex.: node --check, gofmt -e).
    Só roda se a ferramenta existir no PATH (degrada em silêncio se não). Nunca
    levanta exceção; timeout curto p/ não travar o turno."""
    import shutil
    import subprocess

    if shutil.which(cmd[0]) is None:      # ferramenta não instalada → não verifica
        return None
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode == 0:
        return None
    lines = [ln for ln in (proc.stderr or proc.stdout or "").splitlines() if ln.strip()]
    # prefere a linha do erro real (node: 'SyntaxError: ...'); fallback: 1ª linha
    # (gofmt: 'arq.go:2:1: expected ...'). Evita devolver só o caminho do arquivo.
    detail = next((ln for ln in lines if "error" in ln.lower()), lines[0] if lines else "")
    return _verr(lang, name, detail.strip()[:300] or "erro de sintaxe")


def _auto_verify_file(path: str | None) -> str | None:
    """Verificação IMEDIATA e barata de SINTAXE de um arquivo recém-escrito,
    escolhendo o verificador pela extensão. Multi-linguagem:

    In-process (sempre disponível, instantâneo):
      - ``.py``            -> ``compile()``
      - ``.json``          -> ``json.loads``
      - ``.toml``          -> ``tomllib``
      - ``.yaml``/``.yml`` -> ``yaml.safe_load``
    Externo (só se a ferramenta existir no PATH; degrada em silêncio):
      - ``.js``/``.mjs``/``.cjs``/``.jsx`` -> ``node --check``
      - ``.go``                            -> ``gofmt -e``

    Devolve mensagem de erro se o arquivo estiver quebrado, ou ``None`` se OK / tipo
    não verificável / arquivo inexistente. NUNCA levanta exceção."""
    if not path:
        return None
    from pathlib import Path

    _JS = {".js", ".mjs", ".cjs", ".jsx"}
    _INPROC = {".py", ".json", ".toml", ".yaml", ".yml"}
    try:
        p = Path(path)
        suffix = p.suffix.lower()
        if suffix not in _INPROC and suffix not in _JS and suffix != ".go":
            return None
        if not p.is_file():
            return None
    except (OSError, ValueError):
        return None

    # --- verificadores EXTERNOS (não precisam ler o arquivo aqui) ---
    if suffix in _JS:
        return _verify_external(["node", "--check", str(p)], p.name, "JavaScript")
    if suffix == ".go":
        return _verify_external(["gofmt", "-e", str(p)], p.name, "Go")

    # --- verificadores IN-PROCESS ---
    try:
        src = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError, ValueError):
        return None
    try:
        if suffix == ".py":
            compile(src, str(p), "exec")
        elif suffix == ".json":
            json.loads(src)
        elif suffix == ".toml":
            import tomllib
            tomllib.loads(src)
        else:  # .yaml / .yml
            import yaml
            yaml.safe_load(src)
    except SyntaxError as e:
        return _verr("Python", p.name, f"linha {e.lineno}: {e.msg}")
    except json.JSONDecodeError as e:
        return _verr("JSON", p.name, f"linha {e.lineno}: {e.msg}")
    except ValueError as e:  # tomllib.TOMLDecodeError herda de ValueError; null bytes
        return _verr(suffix.lstrip(".").upper() or "arquivo", p.name, str(e)[:200])
    except Exception as e:  # noqa: BLE001 - yaml.YAMLError etc.; verificação nunca derruba
        return _verr(suffix.lstrip(".").upper() or "arquivo", p.name, str(e).splitlines()[0][:200])
    return None


def _lint_python() -> str | None:
    """Python do venv do projeto (tem o ruff), com fallback p/ o do sistema."""
    from aila.core.config import PROJECT_ROOT

    for rel in ("Scripts/python.exe", "bin/python"):
        cand = PROJECT_ROOT / ".venv" / rel
        if cand.exists():
            return str(cand)
    import sys

    return sys.executable or None


def _auto_lint_file(path: str | None) -> str | None:
    """Auto-lint LEVE de um .py recém-escrito: roda ``ruff --select F`` (pyflakes:
    nome indefinido, import/variável não usada, redefinição) — só PROBLEMAS REAIS,
    nada de formatação. Timeout curto, saída enxuta (não poluir o contexto do 7B).
    Devolve mensagem de problemas ou ``None``. NUNCA levanta exceção."""
    if not path:
        return None
    import subprocess
    from pathlib import Path

    from aila.core.config import PROJECT_ROOT

    try:
        p = Path(path)
        if p.suffix.lower() != ".py" or not p.is_file():
            return None
        if p.stat().st_size > 200_000:      # arquivo muito grande → pula (custo)
            return None
    except OSError:
        return None
    exe = _lint_python()
    if not exe:
        return None
    try:
        proc = subprocess.run(
            [exe, "-m", "ruff", "check", str(p), "--select", "F", "--output-format=concise"],
            cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if proc.returncode == 0:
        return None
    out = (proc.stdout or "").strip()
    if not out:
        return None
    lines = out.splitlines()
    head = "\n".join(lines[:8])
    more = f"\n… (+{len(lines) - 8} outros)" if len(lines) > 8 else ""
    return (f"⚠️ LINT (ruff) em {p.name}:\n{head}{more}\n"
            "Corrija esses problemas antes de seguir (ex.: nome indefinido, "
            "import/variável não usada).")
