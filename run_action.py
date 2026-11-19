"""Select the consumer's PR delta and run the pinned MipCode wheel."""

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def git(workspace: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(workspace), *args], capture_output=True, text=True
    )
    if result.returncode:
        raise ValueError(
            "Cannot resolve the Git checkout or comparison history. "
            "Use actions/checkout with fetch-depth: 0 and check the base-ref."
        )
    return result.stdout.strip()


def resolve_root(workspace: Path, raw: str) -> Path:
    if Path(raw).is_absolute():
        raise ValueError("root must be a directory relative to the checkout.")
    root = (workspace / raw).resolve()
    if not root.is_relative_to(workspace) or not root.is_dir():
        raise ValueError("root must name an existing directory inside the checkout.")
    if Path(git(root, "rev-parse", "--show-toplevel")).resolve() != workspace:
        raise ValueError("root must belong to the checked-out repository.")
    return root


def commit(workspace: Path, ref: str) -> str:
    return git(workspace, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}")


def resolve_baseline(
    workspace: Path, event_name: str, base_ref: str, pr_base: str, pr_head: str
) -> str:
    if event_name != "pull_request":
        if not base_ref:
            raise ValueError("Set base-ref explicitly when running outside a pull_request event.")
        return commit(workspace, base_ref)

    if not all(re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", sha) for sha in (pr_base, pr_head)):
        raise ValueError("The pull_request event must identify both the base and head commits.")
    head = commit(workspace, "HEAD")
    if head != pr_head:
        parents = git(workspace, "show", "-s", "--format=%P", head).split()
        if parents != [pr_base, pr_head]:
            raise ValueError(
                "Check out the event's PR merge commit or PR head with fetch-depth: 0."
            )
    if base_ref:
        return commit(workspace, base_ref)
    # For GitHub's merge checkout this is the base parent. For a checkout
    # of the contributor's branch it excludes changes unique to the base branch.
    return git(workspace, "merge-base", pr_base, head)


def run() -> int:
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve()
    root = resolve_root(workspace, os.environ["MIPCODE_ROOT"])
    baseline = resolve_baseline(
        workspace, os.environ["GITHUB_EVENT_NAME"], os.environ["MIPCODE_BASE_REF"],
        os.environ["MIPCODE_PR_BASE"], os.environ["MIPCODE_PR_HEAD"],
    )
    strict = os.environ["MIPCODE_FAIL"].lower()
    if strict not in {"true", "false"}:
        raise ValueError("fail-on-findings must be true or false.")
    print(f"MipCode baseline {baseline}, checkout {commit(workspace, 'HEAD')}", flush=True)

    requirements = Path(__file__).with_name("requirements.txt")
    with tempfile.TemporaryDirectory(dir=os.environ["RUNNER_TEMP"]) as tmp:
        env_dir = Path(tmp) / "venv"
        subprocess.run([sys.executable, "-I", "-m", "venv", str(env_dir)], cwd=tmp, check=True)
        python = env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        subprocess.run(
            [python, "-I", "-m", "pip", "--isolated", "--disable-pip-version-check",
             "install", "--index-url", "https://pypi.org/simple", "--require-hashes",
             "--only-binary=:all:", "--no-deps", "-r", requirements],
            cwd=tmp, check=True,
        )
        args = [python, "-I", "-m", "mipdelta.cli", "--root", str(root),
                "--check-git", "--base-ref", baseline, "--format", "github"]
        if strict == "true":
            args.append("--fail-on-findings")
        return subprocess.run(args, cwd=workspace).returncode


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"MipCode setup failed: {error}", file=sys.stderr)
        sys.exit(2)
