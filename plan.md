# Next Session Plan

## Immediate: PR #20 (fix/dependabot-regen-trigger)

- [ ] Install CodeRabbit: https://github.com/apps/coderabbitai → select ak820ctl
- [ ] Install Gemini Code Assist: https://github.com/apps/gemini-code-assist → select ak820ctl
- [ ] Re-request reviews: `@coderabbitai review` and `@gemini-code-assist review` on PR #20
- [ ] Address any feedback from reviewers
- [ ] Merge PR #20
- [ ] Close PR #18 (broken idna bump) with `@dependabot recreate`

## Dependabot: remaining PRs

- [ ] PR #17 (grouped GH Actions bump) — review and merge
- [ ] PR #19 (hatchling bump) — review and merge
- [ ] Verify dependabot recreates uv/pre-commit PRs correctly after config fix

## Branch protection

- [ ] Set up branch protection on main (via GH UI or API)
- [ ] Required status checks: Test, Lint, Type check (all 3), Security lint, Dependency audit, pre-commit
- [ ] Require PR reviews before merging
- [ ] No force pushes, no deletions
- [ ] Install probot/settings app if using settings.yml: https://github.com/apps/settings

## Merge feat/read-commands branch

- [ ] PR the STATUS.md and COMMANDS.md from feat/read-commands into main

## Implement features (issues)

- [ ] #16 — Fix info command (firmware version LE uint16 parsing)
- [ ] #11 — Read current lighting config (CMD 0x12)
- [ ] #15 — Clock watch daemon (periodic re-sync)
- [ ] #12 — Per-key custom RGB (CMD 0x23 / 0xF5 / 0x22)
- [ ] #13 — LCD image/GIF upload (CMD 0x72)
- [ ] #14 — Dump/restore settings

## Docs

- [ ] Set up zensical docs site
- [ ] mkdocs-typer2 for CLI reference
- [ ] Expand protocol documentation

## Style issues to address

- [ ] Debug the LED color command further if user reports issues
- [ ] Review all noqa comments — remove any that are no longer needed
