from types import SimpleNamespace

from ecrivez.nvim_api import apply_diff


class FakeBuffer(list):
    pass


class FakeNvim(SimpleNamespace):
    def __init__(self, lines):
        super().__init__()
        self.current = SimpleNamespace(buffer=FakeBuffer(lines))
        self.commands = []

    def command(self, cmd):  # noqa: D401 – fake API
        self.commands.append(cmd)


def test_apply_diff_add_and_remove():
    nv = FakeNvim(["a", "b", "c"])

    diff = """
+foo
-bar
+c
"""
    apply_diff(nv, diff)

    assert nv.current.buffer == ["a", "b", "c", "foo", "c"]
    assert "write" in nv.commands