from ecrivez.tools import run_shell


def test_run_shell_success():
    output = run_shell("echo hello")
    assert output == "hello"


def test_run_shell_failure():
    out = run_shell(["bash", "-c", "exit 2"])
    assert "exit code" in out