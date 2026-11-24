#!/usr/bin/env python3
"""Catch real Omp false refusals and primary-target regressions offline.

A local scripted provider selects fixed tool calls. Git, file tools, bash,
Python and pytest execute for real in disposable repositories. This checks
ordinary-accident protections, not arbitrary-program filesystem containment.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVIDER = "worktree-fixture"
MODEL = "worktree-fixture-model"


def git(path: Path, *args: str) -> str:
    """Run Git only in a named disposable fixture repository."""
    return subprocess.check_output(
        ["git", "-C", str(path), *args], stderr=subprocess.STDOUT, text=True,
    ).strip()


def snapshot(primary: Path) -> tuple:
    """Capture the primary branch, tip, index and pre-existing user files."""
    return (
        git(primary, "symbolic-ref", "HEAD"), git(primary, "rev-parse", "HEAD"),
        (primary / ".git/index").read_bytes(),
        (primary / "tracked.txt").read_bytes(), (primary / "untracked.txt").read_bytes(),
    )


def main() -> None:
    """Exercise expanded Python, eval, file diagnostics and branch recovery."""
    omp = shutil.which("omp")
    if not omp:
        raise RuntimeError("omp is required for actual-route worktree coverage")
    # Fail on missing setup, rather than claiming a skipped Python test passed.
    import pytest  # noqa: F401

    with tempfile.TemporaryDirectory(prefix="check-omp-worktree-") as directory:
        root = Path(directory)
        home = root / "home"
        primary = root / "dirty primary"
        task = root / "external placement" / "feature task"
        detached = root / "detached task"
        outside = root / "outside"
        for path in (home, primary, task.parent, outside):
            path.mkdir()
        git(primary, "init", "-b", "master")
        git(primary, "config", "user.name", "Worktree Fixture")
        git(primary, "config", "user.email", "fixture@example.invalid")
        (primary / "tracked.txt").write_text("committed\n")
        git(primary, "add", "tracked.txt")
        git(primary, "commit", "-m", "Initial fixture")
        git(primary, "worktree", "add", "-b", "feature/task", str(task))
        git(primary, "worktree", "add", "--detach", str(detached))
        (primary / "tracked.txt").write_text("dirty user work\n")
        (primary / "untracked.txt").write_text("existing untracked work\n")
        (task / "primary-link").symlink_to(primary, target_is_directory=True)
        (task / "test_feature.py").write_text("def test_feature():\n    assert 2 + 2 == 4\n")
        nested = task / "nested repository"
        nested.mkdir()
        git(nested, "init", "-b", "master")
        before = snapshot(primary)
        quote = shlex.quote
        calls = [
            ("feature-write", "write", {"path": str(task / "feature.txt"), "content": "feature edit\n"}, False),
            ("expanded-python", "bash", {"command": f'PYTHON={quote(sys.executable)}; "$PYTHON" -m pytest -q test_feature.py', "cwd": str(task)}, False),
            ("opaque-eval", "bash", {"command": 'script=\'printf "eval executed\\n" > eval.txt\'; eval "$script"', "cwd": str(task)}, False),
            ("opaque-script", "bash", {"command": 'script=\'printf "script executed\\n" > script.txt\'; bash -c "$script"', "cwd": str(task)}, False),
            ("primary-interpreter-data", "bash", {"command": "printf '%s\\n' bash eval sh", "cwd": str(primary)}, False),
            ("outside-interpreter-data", "bash", {"command": "env -u bash printf '%s\\n' sh", "cwd": str(outside)}, False),
            ("primary-shell-stdin", "bash", {"command": "sh </dev/null", "cwd": str(primary)}, True),
            ("task-shell-stdin", "bash", {"command": "sh </dev/null", "cwd": str(task)}, False),
            ("wrapped-primary-shell", "bash", {"command": f"env -u bash sh -c {quote('git -C ' + quote(str(primary)) + ' reset --hard HEAD')}", "cwd": str(task)}, True),
            ("primary-write", "write", {"path": str(primary / "forbidden.txt"), "content": "forbidden\n"}, True),
            ("symlink-write", "write", {"path": str(task / "primary-link/forbidden.txt"), "content": "forbidden\n"}, True),
            ("nested-primary", "write", {"path": str(nested / "forbidden.txt"), "content": "forbidden\n"}, True),
            ("later-primary-git", "bash", {"command": f'PROGRAM=printf; "$PROGRAM" harmless; git -C {quote(str(primary))} reset --hard HEAD', "cwd": str(task)}, True),
            ("literal-eval-primary", "bash", {"command": f'eval {quote("git -C " + quote(str(primary)) + " reset --hard HEAD")}', "cwd": str(task)}, True),
            ("detached-write", "write", {"path": str(detached / "recovered.txt"), "content": "recoverable edit\n"}, False),
            ("recover-branch", "bash", {"command": "git switch -c feature/recovered && git add recovered.txt && git commit -m 'Recovered fixture edit'", "cwd": str(detached)}, False),
            ("outside-write", "write", {"path": str(outside / "ordinary.txt"), "content": "non-repository work\n"}, False),
        ]
        results: dict[str, str] = {}

        class ScriptedModel(BaseHTTPRequestHandler):
            """Return fixed calls without contacting an external model service."""

            def log_message(self, *_args) -> None:
                pass

            def do_POST(self) -> None:
                request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                messages = request.get("messages", [])
                count = sum(len(message.get("tool_calls", [])) for message in messages if message.get("role") == "assistant")
                if count:
                    tool_result = next((message for message in reversed(messages)
                                        if message.get("role") == "tool"
                                        and message.get("tool_call_id") == calls[count - 1][0]), None)
                    if tool_result is not None:
                        results[calls[count - 1][0]] = str(tool_result.get("content", ""))
                if count < len(calls):
                    label, name, arguments, _blocked = calls[count]
                    delta = {"role": "assistant", "tool_calls": [{
                        "index": 0, "id": label, "type": "function",
                        "function": {"name": name, "arguments": json.dumps(arguments)},
                    }]}
                    finish = "tool_calls"
                else:
                    delta = {"role": "assistant", "content": "Worktree fixture complete."}
                    finish = "stop"
                chunks = [
                    {"id": "worktree", "object": "chat.completion.chunk", "model": MODEL,
                     "choices": [{"index": 0, "delta": delta}]},
                    {"id": "worktree", "object": "chat.completion.chunk", "model": MODEL,
                     "choices": [{"index": 0, "delta": {}, "finish_reason": finish}],
                     "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2}},
                ]
                data = ("".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n").encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        server = ThreadingHTTPServer(("127.0.0.1", 0), ScriptedModel)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            agent = home / ".omp/agent"
            agent.mkdir(parents=True)
            (agent / "config.yml").write_text("""compaction:
  enabled: false
completion:
  notify: false
error:
  notify: false
""")
            (agent / "models.yml").write_text(json.dumps({"providers": {PROVIDER: {
                "baseUrl": f"http://127.0.0.1:{server.server_address[1]}/v1",
                "api": "openai-completions", "auth": "none", "models": [{
                    "id": MODEL, "name": MODEL, "api": "openai-completions",
                    "contextWindow": 131072, "maxTokens": 1024,
                    "cost": {"input": 0, "output": 0, "cacheRead": 0, "cacheWrite": 0},
                }],
            }}}))
            env = {key: os.environ[key] for key in ("PATH", "TMPDIR", "LANG", "LC_ALL", "TERM") if key in os.environ}
            env["HOME"] = str(home)
            for key in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME", "XDG_CACHE_HOME"):
                env[key] = str(home / key.lower())
            linked = subprocess.run([omp, "plugin", "link", str(ROOT)], cwd=task, env=env, capture_output=True, text=True, timeout=60)
            if linked.returncode:
                raise RuntimeError(f"plugin link failed: {linked.stdout}\n{linked.stderr}")
            completed = subprocess.run([
                omp, "--mode", "json", "--print", "--no-title", "--no-rules", "--no-skills",
                "--no-context-files", "--no-lsp", "--tools", "write,bash", "--thinking", "off",
                "--model", f"{PROVIDER}/{MODEL}", "--max-time", "120",
                "Exercise the fixed offline worktree fixture.",
            ], cwd=task, env=env, capture_output=True, text=True, timeout=150)
            if completed.returncode:
                raise RuntimeError(f"Omp fixture failed: {completed.stdout}\n{completed.stderr}")
            for label, _name, _arguments, blocked in calls:
                result = results.get(label)
                if result is None:
                    raise AssertionError(f"missing actual tool result: {label}\n{completed.stdout}")
                expected = "commands from redirected input" if label == "primary-shell-stdin" else "blocked"
                if blocked and expected not in result.lower():
                    raise AssertionError(f"protected route was not blocked: {label}: {result}")
                if not blocked and "blocked" in result.lower():
                    raise AssertionError(f"ordinary feature operation was refused: {label}: {result}")
            assert "1 passed" in results["expanded-python"], results["expanded-python"]
            assert (task / "feature.txt").read_text() == "feature edit\n"
            assert (task / "eval.txt").read_text() == "eval executed\n"
            assert (task / "script.txt").read_text() == "script executed\n"
            assert "bash" in results["primary-interpreter-data"], results["primary-interpreter-data"]
            assert "sh" in results["outside-interpreter-data"], results["outside-interpreter-data"]
            assert (outside / "ordinary.txt").read_text() == "non-repository work\n"
            assert git(detached, "symbolic-ref", "HEAD") == "refs/heads/feature/recovered"
            assert git(detached, "show", "HEAD:recovered.txt") == "recoverable edit"
            assert not (primary / "forbidden.txt").exists()
            assert not (nested / "forbidden.txt").exists()
            assert snapshot(primary) == before, "primary branch/index/user data changed"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    print("check-omp-worktree-live: actual expanded Python/pytest, eval, scripts, file guards, branch recovery and dirty-primary preservation passed")


if __name__ == "__main__":
    main()
