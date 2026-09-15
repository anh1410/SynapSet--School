import pytest

from app.services.diagram_execution import (
    DiagramTimeoutError,
    UnsafeDiagramCodeError,
    check_diagram_code_safety,
    execute_matplotlib_diagram,
)


def test_safe_code_passes_check():
    check_diagram_code_safety("plt.plot([0, 1], [0, 1])")  # must not raise


def test_disallowed_import_is_rejected():
    with pytest.raises(UnsafeDiagramCodeError):
        check_diagram_code_safety("import os\nos.system('echo hi')")


def test_import_from_is_rejected():
    with pytest.raises(UnsafeDiagramCodeError):
        check_diagram_code_safety("from subprocess import run")


def test_eval_call_is_rejected():
    with pytest.raises(UnsafeDiagramCodeError):
        check_diagram_code_safety("eval('1+1')")


def test_open_call_is_rejected():
    with pytest.raises(UnsafeDiagramCodeError):
        check_diagram_code_safety("open('/etc/passwd')")


def test_obfuscated_dangerous_token_is_rejected():
    # aliasing doesn't matter - the underlying module name is what's checked
    with pytest.raises(UnsafeDiagramCodeError):
        check_diagram_code_safety("import subprocess as sp")


def test_syntax_error_is_rejected_not_crashed():
    with pytest.raises(UnsafeDiagramCodeError):
        check_diagram_code_safety("this is not valid python (((")


def test_execute_renders_real_png():
    png = execute_matplotlib_diagram(
        "theta = np.linspace(0, 2*np.pi, 100)\nplt.plot(np.cos(theta), np.sin(theta))",
        timeout_seconds=30,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(png) > 100


def test_execute_rejects_unsafe_code_before_running():
    with pytest.raises(UnsafeDiagramCodeError):
        execute_matplotlib_diagram("import os", timeout_seconds=30)


def test_execute_times_out_on_infinite_loop():
    with pytest.raises(DiagramTimeoutError):
        execute_matplotlib_diagram("while True:\n    pass", timeout_seconds=3)


def test_execute_allows_matplotlib_patches_for_geometry():
    # matplotlib.patches (Circle/Polygon/Arc/...) is the standard way to draw
    # shapes for geometry diagrams and was previously rejected outright.
    png = execute_matplotlib_diagram(
        "import matplotlib.patches as patches\n"
        "ax = plt.gca()\n"
        "ax.add_patch(patches.Circle((0.5, 0.5), 0.3, fill=False))\n"
        "ax.set_xlim(0, 1)\n"
        "ax.set_ylim(0, 1)\n",
        timeout_seconds=30,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_execute_allows_common_builtins():
    # zip/round/min/max/etc are near-universal in plotting loops and were
    # previously missing from the sandboxed __builtins__, crashing with
    # NameError on completely ordinary diagram code.
    png = execute_matplotlib_diagram(
        "xs = [0.1, 0.4, 0.7]\n"
        "ys = [0.2, 0.5, 0.8]\n"
        "for x, y in zip(xs, ys):\n"
        "    plt.plot(x, y, marker='o')\n"
        "plt.title(f'max={round(max(ys), 2)}')\n",
        timeout_seconds=30,
    )
    assert png[:8] == b"\x89PNG\r\n\x1a\n"


def test_dangerous_builtins_still_blocked():
    for call in ("eval('1')", "exec('1')", "open('x')", "__import__('os')"):
        with pytest.raises(UnsafeDiagramCodeError):
            execute_matplotlib_diagram(call, timeout_seconds=10)
