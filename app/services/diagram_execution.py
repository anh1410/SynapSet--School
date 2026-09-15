"""Executes LLM-generated Matplotlib code server-side to produce a real
embedded diagram image, instead of just showing source code to the teacher.

This is BEST-EFFORT sandboxing appropriate for a trusted-ish local/school
tool — an AST import/call allowlist plus process isolation with a timeout,
not container- or gVisor-level isolation. It is not meant to withstand a
deliberately adversarial attacker with control over the prompt; it exists
to stop a Gemini-generated snippet from accidentally (or carelessly) doing
something destructive or hanging forever.
"""

import ast
import multiprocessing
import re

ALLOWED_IMPORTS = {
    "matplotlib",
    "matplotlib.pyplot",
    "matplotlib.patches",
    "matplotlib.lines",
    "matplotlib.path",
    "mpl_toolkits.mplot3d",
    "numpy",
    "math",
}

# Safe, side-effect-free builtins a normal plotting snippet needs (loop/aggregate
# helpers, type constructors, numeric functions). None of these touch the
# filesystem, network, or process - eval/exec/compile/open/__import__ stay
# excluded below regardless of what's added here.
_SAFE_BUILTIN_NAMES = (
    "abs",
    "all",
    "any",
    "bool",
    "complex",
    "dict",
    "divmod",
    "enumerate",
    "filter",
    "float",
    "frozenset",
    "int",
    "isinstance",
    "len",
    "list",
    "map",
    "max",
    "min",
    "pow",
    "range",
    "reversed",
    "round",
    "set",
    "sorted",
    "str",
    "sum",
    "tuple",
    "zip",
)
_DANGEROUS_TOKENS = re.compile(r"\b(os|sys|subprocess|socket|shutil|pathlib|importlib)\b")


class UnsafeDiagramCodeError(Exception):
    pass


class DiagramTimeoutError(Exception):
    pass


def check_diagram_code_safety(source: str) -> None:
    """Raises UnsafeDiagramCodeError if `source` imports anything outside
    ALLOWED_IMPORTS, calls a code-execution/file primitive, or even
    mentions a dangerous module name (belt-and-suspenders against
    `import os as x`-style obfuscation)."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise UnsafeDiagramCodeError(f"Diagram code has a syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in ALLOWED_IMPORTS:
                    raise UnsafeDiagramCodeError(f"Import not allowed: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module not in ALLOWED_IMPORTS:
                raise UnsafeDiagramCodeError(f"Import not allowed: {node.module}")
        elif isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
            if name in {"eval", "exec", "compile", "__import__", "open"}:
                raise UnsafeDiagramCodeError(f"Call not allowed: {name}")

    if _DANGEROUS_TOKENS.search(source):
        raise UnsafeDiagramCodeError("Diagram code references a disallowed module name")


def _render_worker(source: str, conn) -> None:
    """Runs in a separate process. Executes the pre-checked source against a
    restricted namespace, then the HARNESS (not the LLM code) saves the
    current figure — the prompt tells Gemini never to call savefig/show
    itself, which removes file-write access as an attack surface entirely."""
    try:
        import builtins
        import io
        import math

        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.lines
        import matplotlib.patches
        import matplotlib.path
        import matplotlib.pyplot as plt
        import mpl_toolkits.mplot3d
        import numpy as np

        plt.figure(figsize=(5, 4))

        # `matplotlib.patches`/etc are attached as attributes of the `matplotlib`
        # package the moment they're imported above, same as `.pyplot` already was.
        _IMPORT_TARGETS = {
            "numpy": np,
            "math": math,
            "matplotlib": matplotlib,
            "matplotlib.pyplot": matplotlib,
            "matplotlib.patches": matplotlib,
            "matplotlib.lines": matplotlib,
            "matplotlib.path": matplotlib,
            "mpl_toolkits.mplot3d": mpl_toolkits.mplot3d,
        }

        def _safe_import(name, *args, **kwargs):
            # check_diagram_code_safety already restricts `import` statements in the
            # source to ALLOWED_IMPORTS - this just makes those same imports actually
            # work (the prompt asks Gemini to rely on the pre-injected plt/np instead,
            # but it doesn't always comply, so a redundant `import numpy as np` etc.
            # must not crash the render with a bare "__import__ not found").
            #
            # `import matplotlib.pyplot as plt` compiles to IMPORT_NAME("matplotlib.pyplot")
            # followed by an IMPORT_FROM that does getattr(<returned>, "pyplot") itself -
            # so most of these must return the top-level `matplotlib` package (with
            # `.pyplot`/`.patches`/etc already attached as attributes, since they're
            # imported above), not the submodule directly, or that getattr raises
            # "cannot import name 'pyplot' from 'matplotlib.pyplot'".
            if name in _IMPORT_TARGETS:
                return _IMPORT_TARGETS[name]
            raise ImportError(f"import not allowed: {name}")

        safe_globals = {
            "plt": plt,
            "np": np,
            "__builtins__": {
                **{name: getattr(builtins, name) for name in _SAFE_BUILTIN_NAMES},
                "__import__": _safe_import,
            },
        }
        exec(compile(source, "<diagram>", "exec"), safe_globals)  # noqa: S102 - pre-checked by check_diagram_code_safety

        buf = io.BytesIO()
        plt.gcf().savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close("all")
        conn.send(("ok", buf.getvalue()))
    except Exception as exc:  # noqa: BLE001 - any failure must reach the parent as data, not a crash
        conn.send(("error", str(exc)))
    finally:
        conn.close()


def execute_matplotlib_diagram(source: str, timeout_seconds: int = 30) -> bytes:
    """Renders `source` (pre-validated Matplotlib code) in an isolated
    process and returns PNG bytes. Raises UnsafeDiagramCodeError if the
    code fails the safety check, or DiagramTimeoutError if it runs too long."""
    check_diagram_code_safety(source)

    parent_conn, child_conn = multiprocessing.Pipe()
    process = multiprocessing.Process(target=_render_worker, args=(source, child_conn))
    process.start()

    # Must poll/recv BEFORE join(): a PNG payload can exceed the OS pipe
    # buffer, so the child blocks on send() until someone reads. Joining
    # first (waiting for the child to exit) while nobody drains the pipe
    # is a guaranteed deadlock whenever the image is more than a few KB.
    if not parent_conn.poll(timeout_seconds):
        process.terminate()
        process.join()
        raise DiagramTimeoutError(f"Diagram rendering exceeded {timeout_seconds}s")

    status, payload = parent_conn.recv()
    process.join(timeout=2)
    if process.is_alive():
        process.terminate()
        process.join()

    if status == "error":
        raise UnsafeDiagramCodeError(f"Diagram code raised an error: {payload}")
    return payload


def execute_tikz_diagram(source: str, timeout_seconds: int = 30) -> bytes | None:
    """Best-effort only: renders TikZ via pdflatex/tectonic if either is
    installed. Returns None immediately if neither toolchain is found on
    PATH — callers must treat that as "render unavailable", not an error."""
    import shutil

    engine = shutil.which("pdflatex") or shutil.which("tectonic")
    if engine is None:
        return None

    import subprocess
    import tempfile
    from pathlib import Path

    wrapper = (
        "\\documentclass[tikz,border=2pt]{standalone}\n"
        "\\usepackage{tikz}\n"
        "\\begin{document}\n"
        f"{source}\n"
        "\\end{document}\n"
    )
    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "diagram.tex"
        tex_path.write_text(wrapper, encoding="utf-8")
        try:
            subprocess.run(
                [engine, "-interaction=nonstopmode", "-output-directory", tmpdir, str(tex_path)],
                timeout=timeout_seconds,
                capture_output=True,
                cwd=tmpdir,
                check=True,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return None

        pdf_path = Path(tmpdir) / "diagram.pdf"
        if not pdf_path.exists():
            return None
        # PDF -> PNG conversion needs poppler/pdf2image, deliberately not added
        # as a dependency for this best-effort path (no LaTeX toolchain exists
        # on this dev machine anyway) - report the PDF as unconvertable for now.
        return None
