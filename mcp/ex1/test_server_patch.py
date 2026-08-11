import pytest

import server_patch


@pytest.fixture
def code_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(server_patch, "CODE_DIR", tmp_path)
    return tmp_path


class TestServerPatch:
    def test_apply_code_patch_writes_file(self, code_dir):
        result = server_patch.apply_code_patch(
            "db_config.json", '{"connection_timeout_ms": 5000}'
        )
        assert result == (
            "Successfully applied patch to db_config.json "
            f"at path: {code_dir / 'db_config.json'}"
        )
        assert (code_dir / "db_config.json").read_text() == '{"connection_timeout_ms": 5000}'

    def test_apply_code_patch_overwrites_existing(self, code_dir):
        (code_dir / "db_config.json").write_text("old")
        server_patch.apply_code_patch("db_config.json", "new content")
        assert (code_dir / "db_config.json").read_text() == "new content"

    def test_apply_code_patch_nested_file(self, code_dir):
        (code_dir / "sub" / "dir").mkdir(parents=True)
        server_patch.apply_code_patch("sub/dir/app.py", "print('hi')")
        assert (code_dir / "sub" / "dir" / "app.py").read_text() == "print('hi')"

    def test_apply_code_patch_rejects_path_traversal(self, code_dir):
        with pytest.raises(
            ValueError, match="Security violation: Attempted write outside source directory."
        ):
            server_patch.apply_code_patch("../evil.py", "payload")

    def test_apply_code_patch_rejects_absolute_path(self, code_dir):
        with pytest.raises(ValueError):
            server_patch.apply_code_patch("/etc/passwd", "payload")

    def test_resolve_safe_path_valid(self, code_dir):
        path = server_patch._resolve_safe_path("app.py")
        assert path == code_dir / "app.py"

    def test_resolve_safe_path_rejects_traversal(self, code_dir):
        with pytest.raises(ValueError):
            server_patch._resolve_safe_path("../../etc/passwd")

    def test_apply_code_patch_exposes_mcp_tool(self, code_dir):
        tools = [t.name for t in server_patch.mcp._tool_manager.list_tools()]
        assert "apply_code_patch" in tools
