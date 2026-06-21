# Design: stop committing `requirements*.txt`, generate them on demand

- **Date:** 2026-06-20
- **Status:** approved (pending written-spec review)
- **Scope:** Fix A (decommit requirements) for ak820ctl. This is **Phase 1 /
  proving ground** of the broader three-fix scaffolding fan-out program —
  orchestration, repo matrix, and Fixes B/C live in
  `python-project-templates/docs/superpowers/specs/2026-06-20-scaffolding-fanout-program.md`.
- **Also in ak820ctl's Phase 1 PR:** Fix B (one-line `restrictions: null` in
  `.github/settings.yml`) is bundled here too — see the Fix B note below.

## Problem

Dependabot's `uv` ecosystem updates `pyproject.toml` + `uv.lock` but cannot run
post-update commands. To keep the committed `requirements.txt` /
`requirements-dev.txt` in sync, a companion workflow
(`.github/workflows/dependabot-regen.yml`) regenerates them and **pushes the
result back to the PR branch** using `GITHUB_TOKEN`.

By GitHub design, a push made with `GITHUB_TOKEN` does **not** re-trigger
workflows. So when the regen produces a non-empty diff, the regenerated
requirements land on the PR branch **without** CI (notably `pip-audit`) ever
running against them. It only bites when the regen diff is non-empty, so it
looked fine for a long time; it was caught when PR #57 had to be
closed/reopened to force `pip-audit` to actually run.

The obvious "fix" — give the workflow a long-lived push-capable PAT / GitHub
App token so its push re-triggers CI — is **rejected**: a push-capable secret
sitting in every repo's Dependabot secret store is a worse security trade-off
than dropping committed `requirements*.txt` for the few legacy tools that still
want them.

## Goals

- `uv.lock` is the single committed source of truth for dependencies.
- `requirements.txt` / `requirements-dev.txt` are **generated on demand**, never
  committed, never written to the project root.
- Remove the regen-and-commit-back machinery entirely (root cause gone).
- No new long-lived secrets anywhere.
- Preserve every existing guarantee: prod-only vs prod+dev `pip-audit`, prod vs
  prod+dev SBOMs, release artifacts, OSV scanning.

## Non-goals

- Changing the Dependabot config (the `uv` ecosystem already updates
  `pyproject.toml` + `uv.lock` directly — no companion step needed once we stop
  committing derived files).
- Changing `osv-scan.yml` — it scans `uv.lock` directly and is unaffected.
- Phases 2 and 3 (below) are captured here but implemented later.

## Approach (chosen)

**Ephemeral export.** `uv.lock` stays committed; `requirements*.txt` become
on-demand build outputs produced by one shared exporter. Considered and
rejected: (2) auditing the synced environment directly — loses the clean
prod-vs-prod+dev split and diverges from how `release.yml` already works;
(3) fixing the regen trigger with a PAT/App token — rejected on security
grounds above.

## Model

`scripts/regen_requirements.py` is the **single export definition**. Every
consumer goes through it; persistence is chosen per-site, not globally.

| Consumer | Mode | Output location (all git-ignored) | Persisted? |
|---|---|---|---|
| `scripts/audit.py` | stream (`--stdout`) | a `tempfile` dir, auto-deleted | no |
| `meson` `requirements` target | file (`--output-dir`) | build dir | yes (build/release artifact) |
| `.github/workflows/release.yml` | stream (`--stdout`, prod-only default) | runner workdir → `requirements-release.txt` | yes (uploaded artifact) |

Nothing is ever written to the project root, so **no `.gitignore` entry is
added** — the tree stays clean by construction, not by ignore rule.

## Component changes (Phase 1 — ak820ctl)

### `scripts/regen_requirements.py` (kept, generalized)

Refactor the export into one reusable core and expose two CLI modes:

- **Core:** `export(*, include_dev: bool) -> str` runs
  `uv export --format requirements-txt --no-emit-project [--no-dev]` and returns
  the text. (`include_dev=False` ⇒ pass `--no-dev` ⇒ prod-only.)
- **File mode:** `--output-dir DIR` writes both `requirements.txt` (prod) and
  `requirements-dev.txt` (prod+dev) into `DIR`. Default `DIR =
  .reports/requirements/` (ignored) so a bare manual run never dirties root.
- **Stream mode:** `--stdout` writes **one** set to stdout; `--include-dev`
  (default off) selects prod+dev. This is the `regen | …` pipe.

Notes:
- The uv header comment differs between `--output-file` and stdout output. That
  no longer matters: nothing is committed or byte-compared, so header stability
  is not a requirement (the old byte-for-byte rationale is retired).
- `--output-file` is run from inside the target dir with a bare filename only to
  keep file-mode output tidy; not load-bearing anymore.

### `scripts/audit.py`

- **Remove** the requirements-staleness step (`_check_requirements`, old step 2)
  — with nothing committed there is nothing to drift. `uv.lock`-vs-`pyproject`
  is still verified by step 1 (`uv lock --check`). `TOTAL_STEPS`: 6 → 5.
- Drop the module-level `PROD_REQ` / `DEV_REQ` root paths.
- For each set (prod, prod+dev): invoke `regen_requirements.py --stdout`
  (with/without `--include-dev`) as a subprocess, capture stdout, write it to a
  path inside a `tempfile.TemporaryDirectory()`, hand that path to both
  `pip-audit` and `cyclonedx-py`, then let the temp dir evaporate. The prod vs
  prod+dev split, the `--ignore-vuln` handling, and the report/SBOM outputs to
  `.reports/audit/` are otherwise unchanged.
- Update the step-1 failure hint (currently "run … regen_requirements.py") to
  point at `uv lock`.

New step numbering: 1 `uv lock --check`, 2 pip-audit prod, 3 pip-audit prod+dev,
4 SBOM prod, 5 SBOM prod+dev.

### `meson.build` `requirements` target (kept)

Already writes into the build dir with declared outputs. Route it through the
helper for a single export definition: replace the inlined two `uv export` lines
with `uv run python scripts/regen_requirements.py --output-dir <build_dir>`.
Outputs (`requirements.txt`, `requirements-dev.txt`) and the
release-artifact role are unchanged.

### `.github/workflows/release.yml` (kept, two changes)

- Route the export through the helper: replace the inlined
  `uv export … > requirements-release.txt` with
  `uv run python scripts/regen_requirements.py --stdout > requirements-release.txt`.
- **Fix (open item a, resolved):** make the release SBOM **prod-only** — the
  stream defaults to prod-only (no `--include-dev`), dropping dev dependencies
  from the published release SBOM. (Previously omitted `--no-dev`, so the
  release SBOM shipped dev deps — treated as a latent bug, fixed here.)
- **Dev deps are still audited.** Prod-only applies *only* to the released
  SBOM artifact. `audit.py` continues to run `pip-audit` on the prod+dev set
  (step 3) and to generate a prod+dev SBOM into `.reports/audit/` (step 5);
  those just aren't shipped as a release artifact. No loss of dev-dependency
  vulnerability coverage.

### `.github/workflows/dependabot-regen.yml` (deleted)

The entire regen-and-commit-back workflow is removed — this is the root cause of
the unchecked-requirements bug, and there is nothing left to regen-and-commit.
**This is the only deletion.**

### `.pre-commit-config.yaml`

- **Remove** the local `regen-requirements` hook (it existed solely to keep the
  committed files in sync with `uv.lock`; nothing to sync now).
- **Keep** `uv-lock` (keeps `uv.lock` synced with `pyproject.toml`) and the
  pre-push `audit` hook (`audit.py` now self-exports).

### Committed files

`git rm requirements.txt requirements-dev.txt`.

### `.github/settings.yml` (Fix B — bundled into this PR)

Add `restrictions: null` under the branch-protection block so the Probot
Settings app actually applies the scaffolded protection. One line; bundled into
the Phase 1 fixes PR per the program decision. (Part of the broader Fix B
fan-out — see the program doc.)

### Open Dependabot PR #59 (dev-deps group, 12 updates)

#59 conflicts in `requirements-dev.txt` — the exact file this PR deletes.
**Decision:** fold it into Phase 1 — bring the 12 dev-dependency bumps into
`uv.lock` on the Phase 1 branch (apply #59's `pyproject.toml`/`uv.lock` delta, or
`uv lock --upgrade` the affected group), then **close #59 as superseded** once
Phase 1 merges. No throwaway `requirements-dev.txt` regen.

### `CHANGELOG.md`

`[Unreleased]` entries: Removed (committed `requirements*.txt`, the
`dependabot-regen` workflow, the `regen-requirements` pre-commit hook);
Changed (`audit.py` exports ephemerally; `regen_requirements.py` gains
stdout/output-dir modes; release SBOM is prod-only).

### Docs

Update `CLAUDE.md` (the `scripts/` description and any "regen requirements"
mention) and `docs/` references that describe committed `requirements*.txt` or
the dependabot-regen workflow.

## Data flow

```
uv.lock  ──(committed source of truth)
   │
   └─> regen_requirements.py ──┬─ --stdout [--include-dev] ─> audit.py ─> tempfile ─> pip-audit + cyclonedx ─> .reports/audit/
                               ├─ --stdout (prod-only)     ─> release.yml ─> requirements-release.txt ─> SBOM + uploaded artifact
                               └─ --output-dir <build>     ─> meson build outputs ─> release artifacts
```

## Error handling

- A non-zero `uv export` (bad lock, uv missing) aborts the caller with the
  exporter's stderr surfaced.
- `audit.py`'s `tempfile.TemporaryDirectory()` is used as a context manager so
  temp exports are cleaned up even when a downstream tool fails.
- `pip-audit` / `cyclonedx` failures keep today's behavior (`fail()` with the
  log path).

## Testing strategy

No existing test references the requirements files, the regen script, or the
audit script (the only byte-identical fixture test covers `examples/perkey/`,
untouched here). Verification is manual + CI:

1. `uv run python scripts/audit.py` → 5 steps pass; **no** files appear at repo
   root; exports happen under a temp dir (and `.reports/audit/` holds the
   logs/SBOMs as before).
2. `uv run python scripts/regen_requirements.py --stdout` → prints prod set to
   stdout; `--stdout --include-dev` → prod+dev; `--output-dir <tmp>` → two files
   in `<tmp>`, nothing at root.
3. `uv run pre-commit run --all-files` → passes with the `regen-requirements`
   hook gone; working tree stays clean.
4. `meson` `requirements` target → artifacts land in the build dir only.
5. Green PR CI (audit + osv unaffected).
6. *(Optional, if cheap)* a light unit test for the helper's stream vs
   file modes.

## Phase 2 — upstream to `python-project-templates` (captured, later)

Port the same change into the scaffolding (generalized `regen_requirements.py`,
ephemeral `audit.py`, no committed `requirements*.txt`, no `dependabot-regen`
workflow, no `regen-requirements` hook). Write the canonical `MIGRATION.md`
there describing the before/after and the mechanical steps. Reference it from
the global `~/.claude/CLAUDE.md` so the pattern applies to future projects.

## Phase 3 — fan-out migration (captured, later)

For every affected repo (those carrying this committed-requirements +
dependabot-regen pattern, especially project-templates-scaffolded Python
projects): a **per-repo migration PR** doing the actual change, each linking the
canonical `MIGRATION.md`. Tracked by a **checklist issue** listing the repos.
Repo discovery happens at Phase 3 start (the prior session already noted
`geek42` carries the identical latent bug).

## Resolved decisions

- **Spec scope:** full arc, phased; Phase 1 implemented now.
- **Fan-out:** canonical doc in templates + per-repo PR, tracked by a checklist
  issue.
- **meson + release DRY:** route both through the helper (single export
  definition).
- **Release SBOM:** prod-only, fixed in this PR.
- **Root `.gitignore`:** none added; generators target ignored locations.

## Risks / watch-items

- `regen_requirements.py` is invoked from three contexts (local, meson, CI).
  Keep its CLI stable; meson and release pin to its flags.
- Removing `requirements*.txt` may surprise any external/legacy tool that
  expected them in-repo. Accepted trade-off; `MIGRATION.md` (Phase 2) documents
  the replacement (`uv export` / release artifact).
```
