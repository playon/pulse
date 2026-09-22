# CLAUDE.md

## Project

Pulse — diagnostic tools for Pixellot VPU field support.

- **Pulse.Web** (`Pulse.Web/`) — Python + vanilla JS web app (FastAPI + Uvicorn). **This is the product** — the only thing built, shipped, and supported.
- **Pulse.WPF** (`Pulse.WPF/`) — the **deprecated** gen-2 C#/WPF desktop app. Not built or shipped; source kept for reference/provenance only. Ignore it unless explicitly reviving the line. (WPF = Windows Presentation Foundation, a Windows desktop-UI framework — unrelated to Pixellot cameras or the stream pipeline.)

## Multi-Session Etiquette

Several Claude sessions often share **one** checkout of this repo — the same `.git`, working tree, staging index, and HEAD on `dev`. Every session's changes are interleaved with yours at all times. Left unmanaged this causes: staged files swept into another session's commit, a commit message landing on unrelated files, uncommitted edits wiped by another session's `checkout`/`restore`, and the shared `dev` HEAD detached or rebased mid-edit.

### Best fix — one worktree per session

Before working, isolate yourself:

```bash
git worktree add ../pulse-<task> -b <task> origin/dev
```

Work there, commit, `git push origin <task>`, open a PR. Separate tree + index + HEAD = zero collisions. Prefer this for anything beyond a quick one-file edit.

### If you share the checkout

1. **Never stage broadly.** No `git add -A`, `git add .`, or `git commit -am` — they grab every session's WIP.
2. **Commit only your files, by path, in one command:** `git commit <path1> <path2> -m "msg"`. A pathspec commit ignores the shared index, so a parallel `git commit` can't race in between (it *will* if you `git add` then commit as separate steps). Caveat: if another session edited the *same* file, you still co-commit their lines — so claim your lane.
3. **One file = one session at a time.** Hazard files everyone reaches for: `Pulse.Web/app/static/app.js`, `Pulse.Web/app/main.py`, `Pulse.Web/app/demo_data.py`, `Pulse.Web/app/static/style.css`. Don't edit one another session is in.
4. **Commit small and often.** Uncommitted work gets clobbered by another session's checkout/restore; committed work is safe.
5. **Verify before *and* after committing:** `git show --stat HEAD` (or `git diff --cached --stat`) must list only *your* files. If others' appear, you swept them.

### Never run tree-wide or history commands on the shared checkout

`git checkout -- .` · `git restore .` · `git reset --hard` · `git stash` (without a pathspec) · `git rebase` · `git pull --rebase` · `git checkout <branch>`. They discard or rewrite other sessions' work and move HEAD under everyone. (`git pull --rebase` also replays other sessions' unpushed commits and drops you into *their* conflicts — which is why it's no longer the recommended pre-push step here.) And never rewrite pushed `dev` history — no `commit --amend`, `rebase`, or force-push on `dev`.

### Pushing through someone else's conflict

If a push is rejected over a conflict in another session's commit, **do not resolve their conflict.** Cherry-pick *your* commit onto `origin/dev` in a throwaway worktree and push that:

```bash
git worktree add --detach /tmp/wt origin/dev
git -C /tmp/wt cherry-pick <your-sha>
git -C /tmp/wt push origin HEAD:dev && git worktree remove --force /tmp/wt
```

**Lanes:** Camera Connectivity · ScoreConnect · Network · System · Setup · Audio · Pixellot Cloud. Edit your area's render function and scripts; treat the others' as read-only.

## Build

```bash
# Pulse.Web — no build step. On a VPU, just run the launcher:
cd Pulse.Web && run.bat
# On macOS/Linux it auto-runs in demo mode: python3 app/main.py
```

## PowerShell 5.1 Portability (fleet image)

Every script in `Pulse.Web/scripts/` runs under **Windows PowerShell 5.1** on
the fleet image (Win10 LTSC 1809). Demo mode and pwsh 7 hide 5.1-only
failures, so a collector can pass every local test and be silently broken on
every real VPU. Each rule below comes from a real field failure:

1. **Never cast COM objects in PS script code.** Script-level casts to COM
   interfaces fail on 5.1. Put COM work in the compiled C# Api inside
   `_AudioInterop.ps1` (keep it C#5/CodeDom-compatible). (PR #112)
2. **Cast scriptblocks to their delegate type explicitly** (e.g.
   `[RemoteCertificateValidationCallback]`). Implicit conversion inside
   `New-Object` fails silently on 5.1. (PR #117)
3. **Pin `SslProtocols` explicitly** to `Tls, Tls11, Tls12` (never Tls13).
   .NET Framework's parameterless `AuthenticateAsClient` defaults to
   SSL3/TLS 1.0 — OS-default negotiation is .NET Core behavior. (PR #118)
4. **Never `Sort-Object`/`Group-Object` on hashtables.** 5.1 can't resolve
   hashtable keys as properties (pwsh 7 can), so grouping and dedup silently
   collapse. Emit `[pscustomobject]` instead. (PR #124)
5. **Pure ASCII in `.ps1` files.** Em-dashes and smart quotes break parsing
   and mangle console output under the OEM codepage. (`a54f85f`)
6. **Assign unwanted method returns to `$null`.** Stray returns land on
   stdout ahead of the JSON payload and trip the noisy-stdout recovery.
   (PR #124)
7. **Never put an `@(...)`-wrapped Generic List in a `[pscustomobject]`
   literal.** On 5.1 `[pscustomobject]@{ x = @($someList) }` dies with
   "Argument types do not match" (pwsh 7 is fine). Call `.ToArray()` on the
   list instead — safe for empty and populated lists. (disk-cleanup bench
   test)

Before merging a collector change, run it on a real VPU under 5.1 (e.g. the
`tools/vpu-smoke/` sweep over the dev SSH access, where available).

## Branches & Releases

Code flows `dev` → `main`. Each branch has CI builds; tags create releases on `playon/pulse` (the single source + distribution repo).

| App | Dev tag | Production tag |
|-----|---------|----------------|
| Pulse.Web | `web-dev-v*` | `web-v*` |

Dev tags create pre-releases. Production tags create full releases.

Launchers in `runners/` are per-channel: `run_pulse.bat` (production → latest `web-v*` release) and `run_pulse_dev.bat` (dev → latest commit on the `dev` branch; pass a branch name to test another). Both install to `C:\Pulse` (one channel at a time) and auto-update every launch. (The old Pulse.WPF launchers + `install*.ps1` were removed when WPF was deprecated.)

**The beta channel is retired** (2026-09-21). Validation happens on `dev` — the dev launcher tracks the branch tip, so a change can be exercised on a real VPU the moment it merges, which is what the beta cycle was for. Promote `dev` straight to `main` when it is good to go.

The `beta` branch and its launchers are **deliberately left in place, frozen**, and must not be deleted: `runners/Pulse-Beta.bat` sits on beta testers' desktops and fetches its launcher from
`https://raw.githubusercontent.com/playon/pulse/beta/runners/run_pulse_beta.bat`
every run. That URL only resolves while the branch exists. On the frozen branch that launcher is a production redirect, so any remaining tester silently migrates to production; delete the branch and a tester with a cold launcher cache gets a download failure and Pulse does not start at all. `docs/BETA_CHANNEL_PLAYBOOK.md` is kept as the record of how the channel worked, should it ever need reopening.

### Versioning

Pulse.Web uses semver (`MAJOR.MINOR.PATCH`) with a two-channel pipeline. Dev stays roughly one version ahead of main.

| Channel | Version format | Tag example | Audience |
|---------|---------------|-------------|----------|
| Main | `X.Y.Z` | `web-v0.3.0` | Production VPUs |
| Dev | `X.Y.Z-dev` | `web-dev-v0.4.0-dev-abc1234` | Internal testing + field validation |

**Version example at a point in time:**
- Main: `0.2.0` (current stable)
- Dev: `0.3.0-dev` (next release, auto-tagged with commit SHA)

**Version source of truth:** `Pulse.Web/VERSION`.

#### Promotion workflow

1. **Validate on dev.** The dev launcher tracks the branch tip, so exercise the change on a real VPU from `dev` before promoting. This is the step the beta cycle used to be.
2. **Dev → Main:** Update the version source on `dev` to a clean semver (e.g. `0.2.0`), merge `dev` into `main`, and push the production tag.
3. **Bump dev:** After promoting, set the version source on `dev` to the next version with the `-dev` suffix (e.g. `0.3.0-dev`). Subsequent dev pushes auto-tag with commit SHA.

#### Rules

- Version bumps are manual — decide whether to increment minor or major when starting a new dev cycle.
- Dev auto-tags on push (via `web-auto-tag.yml`). Main tags are pushed manually.
- Only promote to main what has actually run on a real VPU from the dev channel. Retiring beta removed the ceremony, not the validation.

#### Changelog (shown to testers on update)

`Pulse.Web/CHANGELOG.md` is the source for the "what's new" notes the in-app **Check for Update** displays. **When you ship a user-facing change, add a one-line bullet under `## [Unreleased]`** (Added / Changed / Fixed), written for a field tech, not a developer. At a promotion to main, rename `[Unreleased]` to the version — that section becomes the release notes the mirror release publishes. Dev builds surface the current `[Unreleased]` list automatically, so there's no per-push curation. The release workflow reads the top changelog section; don't hand-edit release bodies.

## CI Workflows

- `.github/workflows/web-build.yml` — Zips `Pulse.Web/`, triggers on web tags
- `.github/workflows/web-auto-tag.yml` — auto-tags `dev` pushes

They publish releases directly to `playon/pulse` using the workflow's built-in `GITHUB_TOKEN` — no separate PAT or mirror step required. (The old `wpf-pilot-build.yml` was removed with the WPF deprecation.)

## Key Directories

- `runners/` — `.bat` launchers for all channels
- `Pulse.Web/scripts/` — PowerShell data-collection + action scripts (WMI/CIM)
- `Pulse.Web/app/` — FastAPI backend (`main.py`, `powershell.py`) + SPA frontend (`static/`)
- `Pulse.WPF/` — deprecated gen-2 desktop app, kept for reference only (not built/shipped)

## MCP Tools

Claude in Chrome is **not enabled** for this org. Do not attempt to use browser automation MCP tools (`mcp__Claude_in_Chrome__*`). Use `mcp__Claude_Preview__*` for UI previewing instead. Preferably ask the user if they are running local dev server first, then proceed with running local servier if they are not running it already.
