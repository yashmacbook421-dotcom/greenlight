"""The screen engine is arithmetic. No model may be reachable from it.

Two checks: a static scan of every import statement in the package, and a
runtime check that importing the package does not pull an LLM client into
the interpreter transitively.
"""

import ast
import subprocess
import sys
from pathlib import Path

import app.domains.interconnection.screens as screens_pkg

FORBIDDEN_ROOTS = {"anthropic", "openai", "app.core.llm", "app.domains.interconnection.agent"}
SCREENS_DIR = Path(screens_pkg.__file__).parent


def _is_forbidden(module: str) -> bool:
    return any(module == root or module.startswith(root + ".") for root in FORBIDDEN_ROOTS)


def test_no_forbidden_import_statements() -> None:
    offenders = []
    for path in sorted(SCREENS_DIR.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            else:
                continue
            offenders += [f"{path.name}:{node.lineno} imports {n}" for n in names if _is_forbidden(n)]
    assert not offenders, "screen engine must not import a model:\n" + "\n".join(offenders)


def test_importing_screens_loads_no_llm_client() -> None:
    probe = (
        "import sys, pkgutil, importlib\n"
        "import app.domains.interconnection.screens as p\n"
        "for m in pkgutil.walk_packages(p.__path__, p.__name__ + '.'):\n"
        "    importlib.import_module(m.name)\n"
        f"bad = sorted(n for n in sys.modules if any(n == r or n.startswith(r + '.') for r in {sorted(FORBIDDEN_ROOTS)!r}))\n"
        "print(','.join(bad))\n"
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "", f"importing the screen engine loaded: {out.stdout.strip()}"


def test_screens_do_no_io() -> None:
    """Screens are pure arithmetic: no database, network or clock may be reachable from them."""
    probe = (
        "import sys, pkgutil, importlib\n"
        "import app.domains.interconnection.screens as p\n"
        "for m in pkgutil.walk_packages(p.__path__, p.__name__ + '.'):\n"
        "    importlib.import_module(m.name)\n"
        "roots = ('sqlalchemy', 'psycopg', 'app.db', 'httpx', 'requests', 'urllib.request', 'fastapi')\n"
        "print(','.join(sorted(n for n in sys.modules if any(n == r or n.startswith(r + '.') for r in roots))))\n"
    )
    out = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "", f"importing the screen engine loaded: {out.stdout.strip()}"
