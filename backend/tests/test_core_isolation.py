"""app.core is the shared review engine; it must stay independent of any domain."""

import ast
from pathlib import Path

import app.core as core_pkg


def test_core_never_imports_domains() -> None:
    offenders = []
    for path in sorted(Path(core_pkg.__file__).parent.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            offenders += [f"{path.name}:{node.lineno} imports {n}" for n in names if n.startswith("app.domains")]
    assert not offenders, "\n".join(offenders)
