from __future__ import annotations
import base64, json
from .core import *
from .tools_files import safe_path


def _remote_edit(settings, node, code, params):
    """Run a bounded Python edit script on a managed node via sudo -n."""
    payload = json.dumps({"code": code, "params": params})
    token = base64.b64encode(payload.encode("utf-8")).decode("ascii")
    argv = [
        "python3",
        "-c",
        "import base64,json;_d=json.loads(base64.b64decode(%r));exec(_d['code'])"
        % token,
    ]
    return {"raw": run_ssh(settings, node, argv, privileged=True)}


_INSERT_CODE = (
    "import io, time, os, re, shlex\n"
    "p = _d['params']\n"
    "path, text = p['path'], p['text']\n"
    "anchor, position = p.get('anchor'), p.get('position')\n"
    "with io.open(path, 'r', encoding='utf-8', errors='replace') as f:\n"
    "    lines = f.readlines()\n"
    "block = text.splitlines(keepends=True)\n"
    "if position == 'top':\n"
    "    out = block + lines\n"
    "elif position == 'bottom':\n"
    "    out = lines + block\n"
    "elif anchor is None:\n"
    "    raise SystemExit('anchor_pattern is required for before/after insert')\n"
    "else:\n"
    "    idx = next((i for i, l in enumerate(lines) if re.search(anchor, l)), -1)\n"
    "    if idx < 0:\n"
    "        raise SystemExit('anchor pattern not found in file')\n"
    "    if position == 'before':\n"
    "        out = lines[:idx] + block + lines[idx:]\n"
    "    else:\n"
    "        out = lines[:idx + 1] + block + lines[idx + 1:]\n"
    "if p.get('create_backup', True):\n"
    "    os.system('cp -p %s %s.%d' % (shlex.quote(path), shlex.quote(path), int(time.time())))\n"
    "with io.open(path, 'w', encoding='utf-8') as f:\n"
    "    f.writelines(out)\n"
    "print('inserted %d lines (%s)' % (len(block), position))\n"
)


_REPLACE_CODE = (
    "import io, time, os, re, shlex\n"
    "p = _d['params']\n"
    "path, pattern, replacement = p['path'], p['pattern'], p['replacement']\n"
    "count = max(int(p.get('max_replacements', 0)), 0)\n"
    "with io.open(path, 'r', encoding='utf-8', errors='replace') as f:\n"
    "    content = f.read()\n"
    "new, n = re.subn(pattern, replacement, content, count=count)\n"
    "if p.get('create_backup', True):\n"
    "    os.system('cp -p %s %s.%d' % (shlex.quote(path), shlex.quote(path), int(time.time())))\n"
    "with io.open(path, 'w', encoding='utf-8') as f:\n"
    "    f.write(new)\n"
    "print('replaced %d occurrence(s)' % n)\n"
)


def register(mcp, settings):
    @mcp.tool()
    def insert_text_block(
        server_id: str | None = None,
        tags: list[str] | None = None,
        path: str = "",
        text_block: str = "",
        anchor_pattern: str | None = None,
        position: str = "after",
        dry_run: bool = True,
        create_backup: bool = True,
    ) -> dict:
        """Insert a bounded text block in a sandboxed configuration file."""
        path = safe_path(settings, path)
        if not text_block or position not in {"before", "after", "top", "bottom"}:
            raise GatewayError("INVALID_ARGUMENT", "text_block or position is invalid")
        if dry_run:
            return envelope(
                "dry_run_preview",
                "single" if server_id else "multi_tag",
                server_id=server_id,
                matching_nodes=None if server_id else [],
                dry_run=True,
                data={
                    "path": path,
                    "position": position,
                    "create_backup": create_backup,
                    "note": "Preview only; run with dry_run=false to apply",
                },
            )
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: _remote_edit(
                settings,
                n,
                _INSERT_CODE,
                {
                    "path": path,
                    "text": text_block,
                    "anchor": anchor_pattern,
                    "position": position,
                    "create_backup": create_backup,
                },
            ),
        )

    @mcp.tool()
    def replace_text_regex(
        server_id: str | None = None,
        tags: list[str] | None = None,
        path: str = "",
        pattern: str = "",
        replacement: str = "",
        max_replacements: int = 1,
        dry_run: bool = True,
        create_backup: bool = True,
    ) -> dict:
        """Replace text in a sandboxed configuration file."""
        path = safe_path(settings, path)
        if not pattern or len(pattern) > 16384 or max_replacements < 0:
            raise GatewayError(
                "INVALID_ARGUMENT", "pattern or max_replacements is invalid"
            )
        if dry_run:
            return envelope(
                "dry_run_preview",
                "single" if server_id else "multi_tag",
                server_id=server_id,
                dry_run=True,
                data={
                    "path": path,
                    "max_replacements": max_replacements,
                    "create_backup": create_backup,
                    "note": "Preview only; run with dry_run=false to apply",
                },
            )
        return read_only(
            settings,
            server_id,
            tags,
            lambda n: _remote_edit(
                settings,
                n,
                _REPLACE_CODE,
                {
                    "path": path,
                    "pattern": pattern,
                    "replacement": replacement,
                    "max_replacements": max_replacements,
                    "create_backup": create_backup,
                },
            ),
        )
