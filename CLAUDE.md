## Branch naming

Follow [Conventional Branch](https://conventional-branch.github.io/) — no initials prefix.

Format: `<type>/<description>` where `<type>` is one of `feature`, `bugfix`, `hotfix`, `release`, `chore`. Lowercase, hyphens. No issue numbers in branch names — issue traceability lives in PR descriptions and commit messages.

Examples:
- `feature/accept-script`
- `bugfix/symlink-clobber-detection`
- `chore/update-readme`

## Quickstart

- Tests: `uv run pytest`
- Runtime floor: Python 3.9 (matches stock macOS Xcode CLT). Each script begins with `from __future__ import annotations`.
- No third-party runtime deps — stdlib + `git` only. `pytest` is dev-only.
- Direct script invocation: `python3 scripts/install.py <args>` (no package context required).

## Architecture

Self-contained scripts (`install.py`, `migrate.py`, `relink.py`, `doctor.py`) sharing one `scripts/sync_skills.py`, which is also the helper dispatcher `SKILL.md` calls. The layout is in #53.
