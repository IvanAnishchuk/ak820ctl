"""Run supply-chain audits locally (same checks as CI).

Fails with a non-zero exit code on any check failure.

Usage:
    uv run python scripts/audit.py
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console

console = Console()
REPO_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = REPO_ROOT / ".reports" / "audit"

TOTAL_STEPS = 5

# Load the sibling export helper in-process (scripts/ is not a package).
_regen_spec = importlib.util.spec_from_file_location(
    "regen_requirements", REPO_ROOT / "scripts" / "regen_requirements.py"
)
if _regen_spec is None or _regen_spec.loader is None:
    raise ImportError(name="regen_requirements")
regen = importlib.util.module_from_spec(_regen_spec)
_regen_spec.loader.exec_module(regen)


def step(n: int, msg: str) -> None:
    console.print()
    console.print(f"[bold blue]==>[/] [bold]{n}/{TOTAL_STEPS}: {msg}[/]")


def ok(msg: str) -> None:
    console.print(f"   [bold green]ok[/] {msg}")


def fail(msg: str) -> None:
    console.print(f"   [bold red]FAIL[/] {msg}")
    sys.exit(1)


def run_capture(cmd: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def _export_requirements(tmpdir: Path, *, include_dev: bool) -> Path:
    """Export one requirements set from uv.lock into tmpdir, return its path."""
    name = "requirements-dev.txt" if include_dev else "requirements.txt"
    dest = tmpdir / name
    dest.write_text(regen.export(include_dev=include_dev), encoding="utf-8")
    return dest


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
        fail("uv.lock is out of date -- run: uv lock")


VULN_IGNORE_FILE = REPO_ROOT / ".pip-audit-ignore"


def _pip_audit_cmd(req_file: Path) -> list[str]:
    cmd = ["uv", "run", "pip-audit", "--strict", "--desc", "--requirement", str(req_file)]
    if VULN_IGNORE_FILE.exists():
        for line in VULN_IGNORE_FILE.read_text().splitlines():
            vuln_id = line.split("#", 1)[0].strip()
            if vuln_id:
                cmd.extend(["--ignore-vuln", vuln_id])
    return cmd


def _audit_deps(n: int, label: str, req_file: Path, log_file: Path) -> None:
    step(n, f"pip-audit on {req_file.name} ({label})")
    code, out = run_capture(_pip_audit_cmd(req_file))
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
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        prod_req = _export_requirements(tmp, include_dev=False)
        dev_req = _export_requirements(tmp, include_dev=True)
        _audit_deps(2, "prod", prod_req, REPORTS_DIR / "pip-audit.log")
        _audit_deps(3, "prod + dev", dev_req, REPORTS_DIR / "pip-audit-dev.log")
        _generate_sbom(4, "prod", prod_req, REPORTS_DIR / "sbom.cdx.json")
        _generate_sbom(5, "prod + dev", dev_req, REPORTS_DIR / "sbom-dev.cdx.json")

    console.print()
    console.print("[bold green]All audits passed.[/]")
    console.print(f"Reports written to {REPORTS_DIR.relative_to(REPO_ROOT)}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
