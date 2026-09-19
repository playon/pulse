---
name: pulse-status-vocabulary
description: Keep one word and one colour per machine state across Pulse, from PowerShell collector through badge, chip and status dot. Use when adding or changing a status/level/state string in a collector, demo payload or main.py; when rendering a state badge, pill, chip, dot or LED; when adding a verdict word; when two tabs disagree about the same condition; or when a status renders grey, green or the wrong colour.
---

# Pulse status vocabulary

The display layer hard-codes a vocabulary the collectors were never told
about, and until now nothing checked the two agree. What that cost, verified
end to end on `dev@f594640`:

```
Get-DiskHealth.ps1:94   level = Critical | Error | Warning
app.js:5719             <td>${statusBadge(e.level)}</td>
statusBadge (app.js:314) had cases for critical and warning, none for "error"
                        -> fell through to badge(cap, "muted") = GREY
```

A disk **Error** rendered grey, calmer on screen than the amber **Warning**
beside it. Severity inverted in the middle tier, on the table a tech reads to
decide whether a drive is dying. Forty lines away, `severityChip` had always
mapped `error` to red — two helpers in one file disagreeing about one word.

`severityChip` had the worse bug: its fallback arm was `sev-chip-ok`, so an
**unrecognised severity rendered green**. A collector that started emitting a
new word degraded to *healthy*, not to unknown.

Neither was reachable in demo mode (`demo_data` emits no disk events), so no
amount of clicking would have found them.

Both are fixed. `tests/test_status_vocabulary.py` stops them coming back.

## Four helpers, not two

An inventory of what the collectors actually emit (457 status strings) found
two more renderers and three more bugs than the first pass:

| Helper | Was |
|---|---|
| `statusBadge` | no `error` case -> disk Error grey; no `unhealthy` -> failing SMART drive grey while the Dashboard called it critical |
| `severityChip` | fallback `sev-chip-ok` -> an unrecognised severity rendered GREEN |
| `levelChip` (Windows Events) | **Critical fell through to the info arm: blue, and relabelled "Information"** |
| `levelChip` (Pixellot Logs) | echoes the raw word -- the one that was already right |

The Windows Events one is the worst in Pulse's history of this bug class: it
did not merely mis-colour a row, it **replaced the word with its opposite**.
`Get-EventLogs.ps1:87` maps Windows Level 1 to `Critical`, and a Kernel-Power
41 ("rebooted without cleanly shutting down") displayed as routine
Information. The sidebar badge compounded it by counting only `error`.

That helper is nested inside `loadEvents()`, so the first version of the test
-- which parsed top-level functions -- could not see it. **Two of the four
renderers were unchecked, and the worst bug was in one of them.** When adding
a check here, enumerate the renderers first.

## The rules

1. **One condition, one display word.** A state may have synonyms in the
   producers (`running`/`up`/`ok` all mean healthy) but must reach the screen
   as one word. A tech should never see the same machine state called two
   things on two tabs.
2. **Unknown degrades to neutral, never to healthy.** Every helper's fallback
   is grey. If a word is not recognised, the honest rendering is "we do not
   know what this is", not a pass.
3. **Status fills take `--c-status-*`; text takes `--c-accent-*`.** Never
   crossed — `style.css` says so and `pulse-ui-contract` enforces the
   contrast half.
4. **No state by hue alone.** Every dot, LED and triangle carries a word,
   visible or `sr-only`. Two of the status tokens do not clear 3:1 on white,
   so colour is not doing the work you think it is.

## The canonical table

`CANONICAL` in `Pulse.Web/tests/test_status_vocabulary.py` is the source of
truth, kept as data so the test can enforce it:

| Condition | Producer words | Badge severity |
|---|---|---|
| healthy | `running` `up` `pass` `ok` `healthy` | `pass` (green) |
| broken | `stopped` `down` `fail` `critical` `error` | `fail` (red) |
| degraded | `warning` `warn` `degraded` | `warn` (amber) |
| genuinely unknown | `notfound` `unknown` | `muted` (grey) |

## What the test enforces

```bash
cd Pulse.Web && python3 -m unittest tests.test_status_vocabulary -v
```

Stdlib `unittest`, no pytest, same as the rest of the suite. It parses the
**real** helpers out of `app.js` and the **real** literals out of the
collectors, so it fails when they drift rather than when a doc goes stale.

| Test | Fails when |
|---|---|
| `test_every_canonical_word_has_an_explicit_case` | a word in the table has no case in `statusBadge` |
| `test_no_word_renders_at_the_wrong_severity` | a word maps to the wrong colour |
| `test_unknown_input_is_neutral_not_healthy` | `statusBadge`'s fallback stops being muted |
| `test_shared_words_map_to_the_same_severity` | `statusBadge` and `severityChip` disagree |
| `test_severity_chip_fallback_is_not_healthy` | `severityChip`'s fallback becomes green again |
| `test_badge_fed_fields_emit_only_canonical_words` | a badge-fed collector invents a new word |
| `test_no_unregistered_status_badge_call_site` | a new `statusBadge()` call appears unregistered |

## Adding a status word

1. Emit an existing word if one fits. Adding a synonym for a state that
   already has one is how the vocabulary drifted.
2. If the condition is genuinely new: add it to `CANONICAL` with its
   severity, add the case to `statusBadge` (and `severityChip` if it is a
   finding severity), and add it to `demo_data.py` so the state is reachable
   without a broken VPU.
3. Run the test. Then break it deliberately — remove your case from
   `statusBadge` — and confirm it fails. A check that has never failed has
   not been tested.

## Why the collector scan is narrow

`BADGE_FED` lists exactly four script/field pairs, derived by reading the
five `statusBadge()` call sites rather than guessing from field names.

Scanning every `status =` in every collector instead produces a wall of false
positives: `Test-TlsInspection` emits `blocked`/`filtered`/`intercepted`,
`Get-PixellotDependencies` emits `outdated`/`current`,
`Remove-CanopyLeaf` emits `removed`/`partial`. Those are real vocabularies
with their **own** renderers that never touch a badge. Widening the scan to
catch them would make the test noisy, and a check nobody trusts is a check
nobody reads.

The trade-off is that a *new* badge call site could introduce an unscanned
field — which is why `test_no_unregistered_status_badge_call_site` pins the
count at five and tells you to register the new one.

## Related

- `pulse-ui-contract` — the contrast and token half (two status colours do
  not clear 3:1 on white).
- `pulse-honest-states` — an unrecognised word is not the same failure as an
  unrun check; that skill covers the second.
