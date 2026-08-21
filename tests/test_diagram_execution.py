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
