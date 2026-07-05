"""
Brian AI Assistant — Git Agent
Handles Git operations via voice: commit, push, pull, clone, status, log, branch.
"""

import os
import subprocess
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default repo path — used when user doesn't specify
DEFAULT_REPO = Path("E:/deepseek")


def _run_git(args: list, cwd: str, timeout: int = 30) -> dict:
    """Run a git command in the specified directory."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        success = result.returncode == 0
        if not success:
            logger.warning(f"git {' '.join(args)} failed: {stderr}")
        return {
            "success": success,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Git command timed out"}
    except FileNotFoundError:
        return {"success": False, "error": "git is not installed or not in PATH"}
    except Exception as e:
        logger.error(f"git agent error: {e}")
        return {"success": False, "error": str(e)}


def _resolve_repo(repo_path: str) -> str:
    """Resolve the repo directory — use default if empty."""
    if not repo_path:
        # Try to detect a git repo near the default path
        for candidate in [str(DEFAULT_REPO), str(Path.cwd())]:
            res = subprocess.run(["git", "-C", candidate, "rev-parse", "--show-toplevel"],
                                 capture_output=True, text=True)
            if res.returncode == 0:
                return res.stdout.strip()
        return str(DEFAULT_REPO)
    return repo_path


def git_operation(
    operation: str,
    repo_path: str = "",
    message: str = "",
    branch: str = "",
    url: str = "",
) -> dict:
    """
    Execute a git operation.
    Supported: status, add, commit, push, pull, clone, branch, log, diff
    """
    cwd = _resolve_repo(repo_path)
    logger.info(f"[git_agent] op={operation}, repo={cwd}")

    op = operation.lower()

    # ── status ──────────────────────────────────────────────────────────────
    if op == "status":
        res = _run_git(["status", "--short", "--branch"], cwd)
        if res["success"]:
            output = res["stdout"] or "Working tree clean."
            return {"success": True, "action": f"Git status:\n{output}", "output": output}
        return {"success": False, "error": res.get("stderr", "status failed")}

    # ── add ──────────────────────────────────────────────────────────────────
    elif op == "add":
        res = _run_git(["add", "-A"], cwd)
        if res["success"]:
            return {"success": True, "action": "All changes staged (git add -A)"}
        return {"success": False, "error": res.get("stderr", "add failed")}

    # ── commit ───────────────────────────────────────────────────────────────
    elif op == "commit":
        if not message:
            message = "Auto-commit by Brian"
        # Stage all first
        _run_git(["add", "-A"], cwd)
        res = _run_git(["commit", "-m", message], cwd)
        if res["success"]:
            return {"success": True, "action": f"Committed: {message}", "output": res["stdout"]}
        if "nothing to commit" in res.get("stderr", "") or "nothing to commit" in res.get("stdout", ""):
            return {"success": True, "action": "Nothing to commit — working tree is already clean."}
        return {"success": False, "error": res.get("stderr", "commit failed")}

    # ── push ─────────────────────────────────────────────────────────────────
    elif op == "push":
        args = ["push"]
        if branch:
            args += ["origin", branch]
        res = _run_git(args, cwd, timeout=60)
        if res["success"]:
            return {"success": True, "action": f"Pushed to remote{' branch ' + branch if branch else ''}.", "output": res["stdout"]}
        return {"success": False, "error": res.get("stderr", "push failed")}

    # ── pull ─────────────────────────────────────────────────────────────────
    elif op == "pull":
        args = ["pull"]
        if branch:
            args += ["origin", branch]
        res = _run_git(args, cwd, timeout=60)
        if res["success"]:
            return {"success": True, "action": f"Pulled latest changes{' from ' + branch if branch else ''}.", "output": res["stdout"]}
        return {"success": False, "error": res.get("stderr", "pull failed")}

    # ── clone ─────────────────────────────────────────────────────────────────
    elif op == "clone":
        if not url:
            return {"success": False, "error": "A repository URL is required to clone"}
        dest = repo_path if repo_path else str(DEFAULT_REPO / Path(url).stem)
        res = _run_git(["clone", url, dest], str(Path(dest).parent), timeout=120)
        if res["success"]:
            return {"success": True, "action": f"Cloned {url} into {dest}", "output": res["stdout"]}
        return {"success": False, "error": res.get("stderr", "clone failed")}

    # ── branch ────────────────────────────────────────────────────────────────
    elif op == "branch":
        if branch:
            # Create and switch to branch
            res = _run_git(["checkout", "-b", branch], cwd)
            if res["success"]:
                return {"success": True, "action": f"Created and switched to branch: {branch}"}
            # Maybe branch already exists — try just switching
            res2 = _run_git(["checkout", branch], cwd)
            if res2["success"]:
                return {"success": True, "action": f"Switched to branch: {branch}"}
            return {"success": False, "error": res.get("stderr", "branch operation failed")}
        else:
            # List all branches
            res = _run_git(["branch", "-a"], cwd)
            return {"success": True, "action": f"Branches:\n{res['stdout']}", "output": res["stdout"]}

    # ── log ───────────────────────────────────────────────────────────────────
    elif op == "log":
        res = _run_git(["log", "--oneline", "-10"], cwd)
        if res["success"]:
            output = res["stdout"] or "No commits yet."
            return {"success": True, "action": f"Last 10 commits:\n{output}", "output": output}
        return {"success": False, "error": res.get("stderr", "log failed")}

    # ── diff ──────────────────────────────────────────────────────────────────
    elif op == "diff":
        res = _run_git(["diff", "--stat"], cwd)
        if res["success"]:
            output = res["stdout"] or "No changes."
            return {"success": True, "action": f"Diff summary:\n{output}", "output": output}
        return {"success": False, "error": res.get("stderr", "diff failed")}

    else:
        return {"success": False, "error": f"Unknown git operation: {op}"}
