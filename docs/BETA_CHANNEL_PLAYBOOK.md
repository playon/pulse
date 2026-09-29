# Beta Channel Playbook (RETIRED)

> **The beta channel was retired on 2026-09-21.** Pulse ships `dev` → `main`.
> Field validation happens on the dev channel, whose launcher tracks the
> branch tip, so a change can be exercised on a real VPU the moment it merges
> — which is what a beta cycle was for.
>
> This document is kept for two reasons. It is the record of how the plumbing
> worked if the channel ever needs reopening, and it explains why the `beta`
> branch is **frozen rather than deleted**: `runners/Pulse-Beta.bat` sits on
> testers' desktops and fetches its launcher from a `raw.githubusercontent.com`
> URL on that branch every run. On the frozen branch that launcher is a
> production redirect, so a remaining tester migrates to production silently.
> Delete the branch and a tester with a cold launcher cache gets a download
> failure and Pulse does not start at all.
>
> Nothing below should be acted on without deciding to reopen the channel.

How to open a Pulse beta test cycle when a large feature or fix needs real
field validation, and how to close it and route every tester back to
production when the cycle ends.

## How the channel plumbing works (read this first)

Three pieces decide which channel a VPU runs, and they behave differently:

1. **`Pulse-Beta.bat`** — the tiny share-once shim testers keep on their
   desktop. On **every run** it re-downloads
   `runners/run_pulse_beta.bat` from the **beta branch** and executes it.
   You control shim users remotely by changing that file on `beta`. The shim
   itself never needs to be re-shared.
2. **`C:\Pulse\Pulse.bat`** — a **frozen self-copy** of whichever channel
   launcher last ran from outside `C:\Pulse`. The Start Menu "Pulse"
   shortcut targets it, and it **never updates itself** — it keeps resolving
   its channel's newest release forever. Start-Menu-only users can only be
   moved by shipping them a release that swaps this file (see
   `_migrate_retired_beta` in `Pulse.Web/app/main.py`).
3. **The release feed** — `web-build.yml` publishes on tag push and
   **deletes older releases in the same channel**, so a channel's launchers
   can only ever resolve the newest tag. It also stamps the tag into the
   zip's `VERSION` file; the launcher re-stamps it on install. The exact-tag
   gate in `_RETIRED_BETA_TAGS` relies on this.

How the beta was closed (2026-08-04), for reference:
- PR #141 replaced `runners/run_pulse_beta.bat` on `beta` with a copy of the
  production launcher → every shim run now installs production and
  overwrites `C:\Pulse\Pulse.bat` with the production launcher.
- PR #142 shipped `web-beta-v1.0.6`, the final beta release: on startup it
  swaps `Pulse.bat` for the bundled production launcher
  (`Pulse.Web/launcher/run_pulse.bat`) and writes `CHANNEL=production`,
  showing a one-time "moved to production" notice in the UI.

## Opening a beta cycle

1. **Branch content.** Merge `dev` into `beta` (or cherry-pick just the
   feature that needs validation — prefer this when dev carries unrelated
   work you don't want field-tested).
2. **Restore the real beta launcher on `beta`.** The canonical copy lives on
   `dev`:

   ```bash
   git checkout origin/dev -- runners/run_pulse_beta.bat
   ```

3. **Check the retirement gate.** The new cycle's tags must NOT appear in
   `_RETIRED_BETA_TAGS` (`Pulse.Web/app/main.py`). Never remove existing
   entries — they migrate stragglers who skipped a cycle.
4. **Version + changelog.** Set `Pulse.Web/VERSION` to a clean semver ahead
   of main, rename the changelog `[Unreleased]` section to that version.
5. **Tag it:** push `web-beta-vX.Y.Z` on the beta tip. The workflow
   publishes the pre-release.
6. **Distribution — nothing to hand out.** Testers who still have
   `Pulse-Beta.bat` on their desktop just double-click it; it fetches the
   restored beta launcher and flips their install to the beta channel
   (`CHANNEL=beta`, `Pulse.bat` = beta launcher). Only brand-new testers
   need the shim (`runners/Pulse-Beta.bat`) shared once.

## Closing a beta cycle (forcing everyone back to production)

1. **Promote first.** Merge the validated `beta` into `main` and tag
   `web-vX.Y.Z` — the migration must never be a content downgrade.
2. **Ship the final migrating beta release.** On a branch off `beta`:
   - add the cycle's final tag (the one you're about to push, e.g.
     `web-beta-vX.Y.(Z+1)`) to `_RETIRED_BETA_TAGS`;
   - bump `Pulse.Web/VERSION`, add a "beta has wrapped up" changelog
     section;
   - confirm `Pulse.Web/launcher/run_pulse.bat` still matches
     `runners/run_pulse.bat` on `main` (it's the launcher installs get);
   - merge to `beta`, push the final `web-beta-v*` tag. The workflow deletes
     the older beta pre-releases, so frozen beta launchers can only resolve
     the migrating release.
3. **Re-close the shim path.** Replace `runners/run_pulse_beta.bat` on
   `beta` with the production launcher again (copy `runners/run_pulse.bat`,
   see PR #141 for the notice wording).
4. **Verify:** `gh release list` shows only the migrating beta pre-release
   in the beta channel; launch a beta VPU (or VPU2) and confirm the UI
   notice appears, `C:\Pulse\CHANNEL` reads `production`, and the next
   launch installs the latest `web-v*`.

## Pitfalls

- **Order matters when closing:** promote to main *before* tagging the
  migrating beta release (step 1 vs 2), or testers get downgraded content.
- **`Pulse.bat` is frozen.** Repo changes never reach it; only a shim run or
  a migrating release can replace it.
- **Offline VPUs migrate late.** The launcher's offline fast-path runs the
  installed build; stragglers migrate whenever they next launch online —
  that's why retired tags stay in `_RETIRED_BETA_TAGS` forever.
- **Beta and main version numbers have diverged** since 1.0.4 (beta's 1.0.4
  was the ScoreConnect panel; main's was the Wired Ports sort). Same number
  ≠ same content — compare tags, not versions.
- **Release bodies don't carry the changelog yet** (known workflow gap), so
  any tester-facing message must ship in the app UI, not release notes.
