---
name: pulse-ui-contract
description: Run and interpret Pulse's static UI contract checks over Pulse.Web/app/static (colour contrast per theme, design-token coverage, dark-mode parity, icon names, focus rings, dead CSS classes). Use before committing or merging a change to style.css, app.js markup or index.html; when adding a colour token, CSS class family or icon; when asked whether a colour is accessible or why a class or icon is not showing up; and when a contrast or dark-mode question comes up about the Pulse palette.
---

# Pulse UI contract

`Pulse.Web/app/static/style.css` states its own design contract in comments —
the text ramp "must clear WCAG AA (4.5:1) on BOTH `--c-surface` and `--c-bg`",
the theme-invariant fills "carry white text, so their background must keep
contrast in BOTH themes", the accents were chosen against "the DOUBLE-tinted
worst case". Nothing re-checked any of it, and it drifted: the ramp comment
records a 4.3 in the same breath as requiring 4.5.

This skill is the arithmetic those comments were standing in for.

## Run it

```bash
python3 tools/ui-contract/check_ui_contract.py            # from the repo root
python3 tools/ui-contract/check_ui_contract.py --verbose  # every hit, not a sample
python3 tools/ui-contract/check_ui_contract.py --self-test  # colour maths only
```

Exit 0 = contract holds. Exit 1 = something to fix before merging. It reads
four files and writes nothing, so it is always safe to run.

CI runs the same script on any PR touching `Pulse.Web/app/static/**`
(`.github/workflows/ui-contract.yml`).

## What it checks, and what to do when each fails

| Check | Fails when | Fix |
|---|---|---|
| `contrast` | a colour pair is below WCAG AA and is **not** in `CONTRAST_BASELINE`, or a baselined pair got worse | change the token value, or pick a different token — see below |
| `dark-parity` | a token in the themed half of `:root` has no `html.dark` value | add the dark value, or move the token below the "Theme-invariant UI tokens" marker if it genuinely should not change |
| `icons` | `svgIcon("x")` / `sectionTitle("x", ...)` names an icon that is not in the map | fix the name, or add the icon to the map in `app.js` |
| `literals` | more raw hex/rgb outside the token blocks than the baseline | use an existing `--c-*` token; add a new one only if no token fits |
| `fallbacks` | more `var(--token, literal)` than the baseline | drop the fallback — the token always exists, and the literal is a second unreviewed value |
| `focus` | more `outline: none` without a `:focus-visible` partner than the baseline | pair it with a `:focus-visible` rule using `--c-focus-ring` |
| `classes` (warn) | a class is referenced in JS/HTML with no rule anywhere | add the rule, or delete the dead reference |

### Contrast failures

The script reports the **resolved colours**, not the selector, because ~30
selectors in this stylesheet are the same three accent-on-tint pairs. It
prints up to three example sites per pair so the fix stays locatable.

Two thresholds, per WCAG: **4.5:1** for text, **3:1** for non-text UI
(anything whose token name contains `status`, `dot`, `led`, `border`, `ring`,
`divider`, `track`).

Translucent backgrounds are composited **twice** — a tinted chip inside an
already-tinted row is the worst case, and `style.css` says the accents were
picked to survive it. That is not pessimism; it is the stated contract.

`CONTRAST_BASELINE` holds the 11 pairs that were already failing when the
guard was added. They are enumerated, not counted, so each is visible in
review. **Do not add to it to make a new failure go away** — a new entry means
shipping text a tech cannot read. Delete entries as they are fixed; the guard
tells you when a baselined pair starts passing.

### Ratchets

`literals`, `fallbacks` and `focus` fail only when the count rises above the
`MAX_*` baseline at the top of the script. Lower a baseline when you pay debt
down. Raising one is allowed but must happen in the same commit as the change
that needs it, so the increase gets reviewed rather than absorbed.

## Adding a colour token

1. Put it in `:root`, above the `Theme-invariant UI tokens` marker if it
   should change with the theme, below it if it should not.
2. If it is above the marker, add the `html.dark` value too, or the
   `dark-parity` check fails.
3. Run the script. If the new token is used as text or a fill, `contrast`
   will already know — the pairs come from selectors that set both `color`
   and `background`, plus the explicit `EXTRA_PAIRS` list.
4. If the pair is real but the script does not see it (no single selector
   declares both), add it to `EXTRA_PAIRS` with a note saying where the app
   renders it.

## Things that will trip you up

- **Status fills take `--c-status-*`; text takes `--c-accent-*`.** They are
  not interchangeable: the status tokens are vivid on purpose (they are
  lights) and two of them do not clear 3:1 on white.
- **The `classes` check is warn-only and deliberately conservative.** It
  requires a hyphen and rejects camelCase, because `app.js` builds class
  lists in template literals and an interpolation containing its own quotes
  spills JS variable names into any naive scan. The cost is that a missing
  single-word class is not reported.
- **A blank icon is silent.** `svgIcon` returns an empty glyph for an unknown
  name — no console error, nothing in demo mode. Only this check catches it.
- **The guard is pure ASCII on purpose**, matching `ps-ascii-check`: the CI
  runner's locale must not be able to change what it prints.

## What this skill is not

It is static analysis. It cannot tell you whether a layout breaks at 900px
inside a LogMeIn window, whether a collector failure renders as a green PASS,
or whether a tab is usable by keyboard. Those need the page actually rendered.
