"""Run supply-chain audits locally (same checks as CI).

Fails with a non-zero exit code on any check failure.

Usage:
    uv run python scripts/audit.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

from rich.console import Console

console = Console()
REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / ".reports" / "audit"

PROD_REQ = REPO_ROOT / "requirements.txt"
DEV_REQ = REPO_ROOT / "requirements-dev.txt"

TOTAL_STEPS = 6


def step(n: int, msg: str) -> None:
    console.print()
    console.print(f"[bold blue]==>[/] [bold]{n}/{TOTAL_STEPS}: {msg}[/]")


def ok(msg: str) -> None:
    console.print(f"   [bold green]ok[/] {msg}")


def warn(msg: str) -> None:
    console.print(f"   [bold yellow]!![/] {msg}")


def fail(msg: str) -> None:
    console.print(f"   [bold red]FAIL[/] {msg}")
    sys.exit(1)


def file_sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_capture(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def load_sbom_components(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    return len(data.get("components", []))


def _check_lockfile() -> None:
    step(1, "uv.lock in sync with pyproject.toml")
    code, out = run_capture(["uv", "lock", "--check"])
    if code == 0:
        ok("uv.lock is up to date")
    else:
        console.print(out)
        fail("uv.lock is out of date -- run: uv run python scripts/regen_requirements.py")


def _check_requirements() -> None:
    step(2, "requirements*.txt in sync with uv.lock")
    prod_before = file_sha256(PROD_REQ)
    dev_before = file_sha256(DEV_REQ)
    code, out = run_capture([sys.executable, str(REPO_ROOT / "scripts" / "regen_requirements.py")])
    if code != 0:
        console.print(out)
        fail("Failed to regenerate requirements files")
    prod_after = file_sha256(PROD_REQ)
    dev_after = file_sha256(DEV_REQ)
    stale = False
    if prod_before != prod_after:
        warn(f"requirements.txt was stale ({prod_before[:12]} -> {prod_after[:12]})")
        stale = True
    if dev_before != dev_after:
        warn(f"requirements-dev.txt was stale ({dev_before[:12]} -> {dev_after[:12]})")
        stale = True
    if stale:
        fail("Files were regenerated. Review and commit them.")
    ok("requirements.txt and requirements-dev.txt are current")


def _audit_deps(n: int, label: str, req_file: Path, log_file: Path) -> None:
    step(n, f"pip-audit on {req_file.name} ({label})")
    code, out = run_capture(
        ["uv", "run", "pip-audit", "--strict", "--desc", "--requirement", str(req_file)]
    )
    log_file.write_text(out, encoding="utf-8")
    if code == 0:
        ok(f"No known vulnerabilities in {label} dependencies")
    else:
        console.print(out)
        fail(f"pip-audit found vulnerabilities in {label} -- see {log_file.relative_to(REPO_ROOT)}")


def _generate_sbom(n: int, label: str, req_file: Path, sbom_file: Path) -> None:
    step(n, f"CycloneDX SBOM ({label})")
    code, out = run_capture(
        [
            "uv",
            "tool",
            "run",
            "--from",
            "cyclonedx-bom",
            "cyclonedx-py",
            "requirements",
            str(req_file),
            "--output-format",
            "json",
            "--output-file",
            str(sbom_file),
        ]
    )
    if code != 0:
        console.print(out)
        fail(f"cyclonedx-py failed for {label}")
    components = load_sbom_components(sbom_file)
    ok(f"SBOM ({label}) with {components} components -> {sbom_file.relative_to(REPO_ROOT)}")


def main() -> int:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    _check_lockfile()
    _check_requirements()
    _audit_deps(3, "prod", PROD_REQ, REPORTS_DIR / "pip-audit.log")
    _audit_deps(4, "prod + dev", DEV_REQ, REPORTS_DIR / "pip-audit-dev.log")
    _generate_sbom(5, "prod", PROD_REQ, REPORTS_DIR / "sbom.cdx.json")
    _generate_sbom(6, "prod + dev", DEV_REQ, REPORTS_DIR / "sbom-dev.cdx.json")

    console.print()
    console.print("[bold green]All audits passed.[/]")
    console.print(f"Reports written to {REPORTS_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
