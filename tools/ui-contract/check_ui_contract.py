#!/usr/bin/env python3
"""Static UI contract checks for the Pulse.Web SPA.

style.css carries an unusually explicit design contract -- in comments. The
text ramp block states "every tier must clear WCAG AA (4.5:1) for normal text
on BOTH --c-surface and --c-bg". The theme-invariant block explains that solid
brand fills carry white text so they must hold contrast in both themes. The
accent block records the double-tint compositing case by hand.

Nothing re-checks any of it. The repo has three CI guards (ps-ascii-check,
python-tests, launcher-sync) and none of them look at app/static/, while
web-auto-tag.yml fires on Pulse.Web/** -- so a frontend-only change runs zero
checks and then publishes a dev pre-release.

The drift the contract's own comments admit to:
  --c-dimmer is recorded as "4.8/4.3" in the same comment that requires 4.5.
This script is the arithmetic those comments were standing in for.

Checks, in the order they run:
  1  contrast      colour pairs below WCAG AA, per theme, alpha-composited
  2  dark-parity   a themed token with no html.dark counterpart
  3  icons         svgIcon()/sectionTitle() naming an icon that does not exist
  4  literals      raw hex/rgb outside the token blocks              (ratchet)
  5  fallbacks     var(--token, literal) -- a second, unreviewed value (ratchet)
  6  focus         outline:none with no :focus-visible replacement   (ratchet)
  7  classes       class referenced in JS with no rule anywhere      (warn)

A "ratchet" check fails only when the count rises above the baseline recorded
below. Lower the baseline as you clean up; never raise it.

Pure ASCII on purpose, same as ps-ascii-check.py: the CI runner's locale must
never be able to change what this prints.

Usage:
    python3 tools/ui-contract/check_ui_contract.py            # from repo root
    python3 tools/ui-contract/check_ui_contract.py --verbose  # list every hit
"""

import argparse
import os
import re
import sys

STATIC = os.path.join("Pulse.Web", "app", "static")

# ---------------------------------------------------------------------------
# Ratchet baselines. These are debts that predate the guard, not permissions.
# Lower each number when you pay one down; the guard fails if it goes up.
# ---------------------------------------------------------------------------
MAX_LITERALS = 46      # raw colour literals outside :root / html.dark
MAX_FALLBACKS = 13     # var(--token, <literal>) second values
MAX_BARE_OUTLINE = 9   # outline:none rules with no :focus-visible partner

# Tokens that live in the THEMED half of :root but are deliberately shared
# across light and dark. style.css says so directly at the camera-status block:
# "Vivid on purpose (status lights); shared across light/dark."
THEME_SHARED = {
    "--c-status-ok",
    "--c-status-warn",
    "--c-status-down",
    "--c-status-connecting",
}

# Non-text tokens: WCAG gives graphics and UI components 3:1, not 4.5:1.
NON_TEXT_HINTS = ("status", "dot", "led", "border", "ring", "divider", "track")

# Pairs the stylesheet does not co-declare on one selector but that the app
# renders anyway. Each entry cites where the pairing happens.
# (text_token, background_token, why)
EXTRA_PAIRS = [
    ("--c-on-accent", "--c-pill-critical", "severity pill, white on solid fill"),
    ("--c-on-accent", "--c-pill-warning", "severity pill, white on solid fill"),
    ("--c-on-accent", "--c-pill-info", "severity pill, white on solid fill"),
    ("--c-on-accent", "--c-btn-danger", "destructive button label"),
    ("--c-dimmer", "--c-bg", "text ramp, stated contract in style.css"),
    ("--c-dimmer", "--c-surface", "text ramp, stated contract in style.css"),
    ("--c-dimmer", "--c-deep-bg", "sidebar metadata"),
    ("--c-dim", "--c-bg", "text ramp, stated contract in style.css"),
    ("--c-dim", "--c-surface", "text ramp, stated contract in style.css"),
    ("--c-muted", "--c-bg", "text ramp, stated contract in style.css"),
    ("--c-muted", "--c-surface", "text ramp, stated contract in style.css"),
    ("--c-status-ok", "--c-surface", "port LED / status dot on a card"),
    ("--c-status-warn", "--c-surface", "port LED / status dot on a card"),
    ("--c-status-down", "--c-surface", "port LED / status dot on a card"),
    ("--c-status-connecting", "--c-surface", "port LED / status dot on a card"),
]

# Contrast debt that predates the guard: (theme, foreground, background) ->
# the ratio measured when the guard was added. A pair listed here is reported
# but does not fail the build; a pair NOT listed, or one that gets WORSE than
# its recorded ratio, fails. Delete a line when you fix it -- the guard tells
# you when a listed pair starts passing.
#
# Populated by the first run against dev @4b5496e. Every entry is a real AA
# failure, not a false positive; they are enumerated rather than counted so
# each one is visible in review. Fixing any of them means changing a token
# value that the whole app reads, which is a design call, not a guard change.
#
# The three accent-on-tint rows are the drift this guard was written for:
# style.css says the accents were chosen to clear 4.5:1 "against the DOUBLE
# -tinted worst case" and records 4.6:1 for red -- the arithmetic says 4.25.
# The same comment's "6.1:1 on a card" reproduces exactly, so the method is
# right and the double-tint figure was optimistic.
CONTRAST_BASELINE = {
    ("light", "#f59e0b", "#ffffff"): 2.15,  # 3.0:1 needed -- --c-status-warn on --c-surface
    ("light", "#22c55e", "#ffffff"): 2.28,  # 3.0:1 needed -- --c-status-ok on --c-surface
    ("light", "#ffffff", "#3b82f6"): 3.68,  # 4.5:1 needed -- --c-on-accent on --c-pill-info
    ("dark", "#ffffff", "#3b82f6"): 3.68,   # 4.5:1 needed -- --c-on-accent on --c-pill-info
    ("light", "#ffffff", "#ef4444"): 3.76,  # 4.5:1 needed -- --c-on-accent on --c-btn-danger
    ("dark", "#ffffff", "#ef4444"): 3.76,   # 4.5:1 needed -- --c-on-accent on --c-btn-danger
    ("light", "#2460e3", "rgba(37,99,235,0.12)"): 3.95,  # 4.5 -- .badge-info / .sev-chip-info
    ("light", "#64748b", "#e8eef5"): 4.07,  # 4.5:1 needed -- --c-dimmer on --c-deep-bg (sidebar)
    ("light", "#bf2121", "rgba(220,38,38,0.12)"): 4.25,  # 4.5 -- .badge-fail / .badge-stopped
    ("light", "#64748b", "#f1f5f9"): 4.34,  # 4.5:1 needed -- --c-dimmer on --c-bg
    ("light", "#137638", "rgba(22,163,74,0.12)"): 4.43,  # 4.5 -- .badge-pass / .badge-running
}


# ---------------------------------------------------------------------------
# colour maths
# ---------------------------------------------------------------------------
def parse_color(value):
    """Return (r, g, b, a) floats 0-255 / 0-1, or None if not a plain colour."""
    if value is None:
        return None
    v = value.strip().lower()
    m = re.fullmatch(r"#([0-9a-f]{3})", v)
    if m:
        h = m.group(1)
        return (int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), 1.0)
    m = re.fullmatch(r"#([0-9a-f]{6})", v)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
    m = re.fullmatch(r"#([0-9a-f]{8})", v)
    if m:
        h = m.group(1)
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) / 255.0)
    m = re.fullmatch(r"rgba?\(([^)]*)\)", v)
    if m:
        parts = [p.strip() for p in re.split(r"[,/\s]+", m.group(1)) if p.strip()]
        if len(parts) < 3:
            return None
        try:
            r, g, b = (float(parts[0]), float(parts[1]), float(parts[2]))
        except ValueError:
            return None
        a = 1.0
        if len(parts) > 3:
            try:
                a = float(parts[3].rstrip("%"))
                if parts[3].endswith("%"):
                    a = a / 100.0
            except ValueError:
                a = 1.0
        return (r, g, b, a)
    if v == "white":
        return (255, 255, 255, 1.0)
    if v == "black":
        return (0, 0, 0, 1.0)
    return None


def composite(fg, bg):
    """Flatten a translucent colour over an opaque one."""
    r1, g1, b1, a = fg
    r2, g2, b2, _ = bg
    return (r1 * a + r2 * (1 - a), g1 * a + g2 * (1 - a), b1 * a + b2 * (1 - a), 1.0)


def _chan(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb):
    return 0.2126 * _chan(rgb[0]) + 0.7152 * _chan(rgb[1]) + 0.0722 * _chan(rgb[2])


def contrast(fg, bg):
    l1, l2 = luminance(fg), luminance(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


# ---------------------------------------------------------------------------
# css parsing
# ---------------------------------------------------------------------------
def strip_comments(css):
    """Blank out /* */ comments, preserving newlines so line numbers hold."""
    out = []
    i = 0
    while i < len(css):
        if css.startswith("/*", i):
            j = css.find("*/", i + 2)
            if j == -1:
                j = len(css)
            out.append("".join(ch if ch == "\n" else " " for ch in css[i:j + 2]))
            i = j + 2
        else:
            out.append(css[i])
            i += 1
    return "".join(out)


def find_block(css, selector):
    """Return (body, start_offset) for the first `selector { ... }` block."""
    m = re.search(re.escape(selector) + r"\s*\{", css)
    if not m:
        return None, None
    depth = 1
    i = m.end()
    while i < len(css) and depth:
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
        i += 1
    return css[m.end():i - 1], m.end()


def parse_declarations(body):
    """[(prop, value)] from a declaration block, ignoring nested blocks."""
    out = []
    for raw in re.split(r";", body):
        if "{" in raw or "}" in raw:
            continue
        if ":" not in raw:
            continue
        prop, _, value = raw.partition(":")
        out.append((prop.strip(), value.strip()))
    return out


def load_themes(css_raw, css):
    """Token maps for light and dark, plus the themed/invariant split."""
    root_body, root_off = find_block(css, ":root")
    dark_body, _ = find_block(css, "html.dark")
    if root_body is None:
        return None, None, None, None
    light = {}
    for prop, value in parse_declarations(root_body):
        if prop.startswith("--"):
            light[prop] = value
    dark = dict(light)
    for prop, value in parse_declarations(dark_body or ""):
        if prop.startswith("--"):
            dark[prop] = value

    # The themed half of :root is everything BEFORE the file's own
    # "Theme-invariant UI tokens" marker comment.
    marker = css_raw.find("Theme-invariant UI tokens")
    themed = set()
    if marker != -1:
        head = css_raw[root_off:marker] if root_off and marker > root_off else ""
        themed = set(re.findall(r"(--[\w-]+)\s*:", strip_comments(head)))
    return light, dark, themed, set(re.findall(r"(--[\w-]+)\s*:", strip_comments(dark_body or "")))


def resolve(value, tokens, depth=0):
    """Resolve var() chains to a literal. Returns None if unresolvable."""
    if value is None or depth > 10:
        return None
    v = value.strip()
    m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*(?:,\s*(.*))?\)", v)
    if m:
        name, fallback = m.group(1), m.group(2)
        if name in tokens:
            return resolve(tokens[name], tokens, depth + 1)
        return resolve(fallback, tokens, depth + 1) if fallback else None
    return v


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------
def check_contrast(css_raw, css, light, dark, verbose):
    """Every (text, surface) pair we can prove the app renders."""
    failures = []

    # Pairs the stylesheet declares on a single selector.
    declared = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        sel, body = m.group(1).strip().splitlines()[-1].strip(), m.group(2)
        decls = dict(parse_declarations(body))
        fg = decls.get("color")
        bg = decls.get("background-color") or decls.get("background")
        if not fg or not bg:
            continue
        if bg.split()[0] in ("none", "transparent", "inherit", "initial", "unset"):
            continue
        # A shorthand `background` may carry more than a colour; take the head.
        declared.append((sel, fg, bg.split()[0] if " " in bg else bg, line_of(css, m.start())))

    for theme, tokens in (("light", light), ("dark", dark)):
        surface = parse_color(resolve("var(--c-surface)", tokens)) or (255, 255, 255, 1.0)

        def judge(fg_raw, bg_raw, label, where, non_text):
            fg_src, bg_src = resolve(fg_raw, tokens), resolve(bg_raw, tokens)
            fg, bg = parse_color(fg_src), parse_color(bg_src)
            if not fg or not bg:
                return
            # A translucent backdrop sits on the card; a translucent chip inside
            # an already-tinted row composites twice. style.css:24-27 documents
            # exactly this and says the accents were picked to clear AA against
            # the DOUBLE-tinted worst case, so that is what we measure.
            if bg[3] < 1.0:
                once = composite(bg, surface)
                bg_eff = composite(bg, once)
            else:
                bg_eff = bg
            fg_eff = composite(fg, bg_eff) if fg[3] < 1.0 else fg
            need = 3.0 if non_text else 4.5
            ratio = contrast(fg_eff, bg_eff)
            if ratio + 0.005 >= need:
                return
            # Key on the RESOLVED colours, not the selector: ~30 selectors in
            # this stylesheet are the same three accent-on-tint pairs, and
            # listing each one buries the four distinct defects.
            pair = (theme, fg_src.strip().lower(), bg_src.strip().lower(), round(need, 1))
            failures.append((pair, label, ratio, need, where, non_text))

        for fg_tok, bg_tok, why in EXTRA_PAIRS:
            if fg_tok not in tokens or bg_tok not in tokens:
                continue
            non_text = any(h in fg_tok for h in NON_TEXT_HINTS)
            judge("var(%s)" % fg_tok, "var(%s)" % bg_tok,
                  "%s on %s" % (fg_tok, bg_tok), why, non_text)

        for sel, fg_raw, bg_raw, ln in declared:
            non_text = any(h in (fg_raw + sel) for h in NON_TEXT_HINTS)
            judge(fg_raw, bg_raw, "%s {color}" % sel, "style.css:%d" % ln, non_text)

    # Collapse to one row per distinct resolved colour pair, carrying the
    # example selectors so the fix is still locatable.
    grouped = {}
    for pair, label, ratio, need, where, non_text in failures:
        g = grouped.setdefault(pair, {"ratio": ratio, "need": need, "sites": []})
        g["ratio"] = min(g["ratio"], ratio)
        if len(g["sites"]) < 3:
            g["sites"].append("%s (%s)" % (label, where))
    out = []
    for (theme, fg_src, bg_src, _), g in grouped.items():
        out.append((theme, fg_src, bg_src, g["ratio"], g["need"], g["sites"]))
    return sorted(out, key=lambda x: x[3])


def check_dark_parity(themed, dark_names):
    return sorted(t for t in themed if t not in dark_names and t not in THEME_SHARED)


def check_icons(js):
    m = re.search(r"function svgIcon\([^)]*\)\s*\{.*?\n  \};", js, re.S)
    if not m:
        return None, []
    known = set(re.findall(r'^\s{4}["\']?([\w-]+)["\']?\s*:', m.group(0), re.M))
    used = []
    for pat in (r'svgIcon\(\s*"([\w-]+)"', r'sectionTitle\(\s*"([\w-]+)"'):
        for mm in re.finditer(pat, js):
            used.append((mm.group(1), line_of(js, mm.start())))
    missing = sorted({(n, ln) for n, ln in used if n not in known})
    return known, missing


def check_literals(css, light_off_ranges):
    hits = []
    pat = re.compile(r"(#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\))")
    for m in pat.finditer(css):
        off = m.start()
        if any(a <= off < b for a, b in light_off_ranges):
            continue
        hits.append((line_of(css, off), m.group(0)))
    return hits


def check_fallbacks(css):
    hits = []
    for m in re.finditer(r"var\(\s*--[\w-]+\s*,\s*([^)]+)\)", css):
        hits.append((line_of(css, m.start()), m.group(0).strip()))
    return hits


def check_focus(css):
    focus_sel = set()
    for m in re.finditer(r"([^{}]+):focus-visible[^{}]*\{", css):
        focus_sel.add(m.group(1).strip().splitlines()[-1].strip())
    hits = []
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        body = m.group(2)
        if not re.search(r"outline\s*:\s*none", body):
            continue
        sel = m.group(1).strip().splitlines()[-1].strip()
        base = sel.split(":")[0].strip()
        if any(base and base in f for f in focus_sel):
            continue
        hits.append((line_of(css, m.start()), sel))
    return hits


def check_classes(css, js, html):
    """Classes referenced in JS/HTML with no rule in either stylesheet.

    Conservative on purpose. app.js builds class lists inside template
    literals, so a naive pass reports dozens of phantoms. Anything adjacent to
    an interpolation is treated as a PREFIX and skipped -- `badge-${type}`
    proves nothing about `badge-pass`.
    """
    defined = set(re.findall(r"\.(-?[_a-zA-Z][\w-]*)", css))
    referenced = set()
    for source in (js, html):
        for m in re.finditer(r'class="([^"]*)"', source):
            for tok in m.group(1).split():
                if not _looks_like_class(tok):
                    continue
                referenced.add(tok)
    # classList.add("x") / .toggle("x", cond) are unambiguous references.
    for m in re.finditer(r'classList\.(?:add|toggle|remove)\(\s*"([\w-]+)"', js):
        if _looks_like_class(m.group(1)):
            referenced.add(m.group(1))
    return sorted(referenced - defined)


def _looks_like_class(tok):
    """Is this token a CSS class name, or a JS identifier that leaked in?

    app.js builds class lists in template literals, and an interpolation
    containing its own quotes -- class="a ${x ? "b" : "c"}" -- truncates a
    naive attribute match, spilling variable names into the token stream.
    Pulse class names and Tailwind utilities are kebab-case, so requiring a
    hyphen and rejecting camelCase removes every one of those spills.

    Trade-off: a genuinely undefined single-word class (.card) is not
    reported. That is why this check is a warning, not a failure.
    """
    if "${" in tok or "}" in tok or "-" not in tok:
        return False
    if re.search(r"[a-z][A-Z]", tok):   # rowCls, statusCls, camLabelCls
        return False
    return bool(re.fullmatch(r"[a-z0-9][\w-]*", tok))


# ---------------------------------------------------------------------------
def self_test():
    """Check the colour maths against values that can be verified by hand.

    Everything this guard asserts rests on contrast(); if someone "simplifies"
    the luminance curve the whole check silently passes everything. The last
    case is style.css's own recorded figure ("6.1:1 on a card"), so the
    stylesheet and this script have to keep agreeing.
    """
    cases = [
        ("black on white", (0, 0, 0, 1.0), (255, 255, 255, 1.0), 21.00),
        ("white on white", (255, 255, 255, 1.0), (255, 255, 255, 1.0), 1.00),
        # #767676 and #595959 are the canonical grey values that sit exactly on
        # the WCAG AA (4.5) and AAA (7.0) thresholds against white.
        ("#767676 on white (AA boundary)", parse_color("#767676"), parse_color("#ffffff"), 4.54),
        ("#595959 on white (AAA boundary)", parse_color("#595959"), parse_color("#ffffff"), 7.00),
        ("--c-accent-red on a card", parse_color("#bf2121"), parse_color("#ffffff"), 6.08),
    ]
    bad = 0
    for name, fg, bg, expected in cases:
        got = contrast(fg, bg)
        ok = abs(got - expected) < 0.02
        print("  %-34s %6.2f:1  expected %5.2f  %s" % (name, got, expected, "ok" if ok else "MISMATCH"))
        bad += 0 if ok else 1
    # Compositing: a 12% tint over white, then over itself.
    once = composite(parse_color("rgba(220,38,38,0.12)"), (255, 255, 255, 1.0))
    twice = composite(parse_color("rgba(220,38,38,0.12)"), once)
    got = contrast(parse_color("#bf2121"), twice)
    ok = abs(got - 4.25) < 0.02
    print("  %-34s %6.2f:1  expected %5.2f  %s"
          % ("accent-red on double tint", got, 4.25, "ok" if ok else "MISMATCH"))
    bad += 0 if ok else 1
    print("")
    print("self-test: %s" % ("FAILED" if bad else "all %d cases pass" % (len(cases) + 1)))
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true", help="list every hit")
    ap.add_argument("--self-test", action="store_true",
                    help="verify the colour maths and exit")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    need = ["style.css", "app.js", "index.html", "tailwind-min.css"]
    paths = {n: os.path.join(STATIC, n) for n in need}
    for n, p in paths.items():
        if not os.path.isfile(p):
            print("FAIL: %s not found -- has the layout moved?" % p)
            return 1

    css_raw = open(paths["style.css"], encoding="utf-8").read()
    css = strip_comments(css_raw)
    tw = strip_comments(open(paths["tailwind-min.css"], encoding="utf-8").read())
    js = open(paths["app.js"], encoding="utf-8").read()
    html = open(paths["index.html"], encoding="utf-8").read()

    light, dark, themed, dark_names = load_themes(css_raw, css)
    if light is None:
        print("FAIL: no :root block in style.css -- has the token layout moved?")
        return 1

    hard = 0
    soft = 0
    print("Pulse UI contract -- %d tokens (%d themed), %d dark overrides"
          % (len(light), len(themed), len(dark_names)))
    print("")

    # 1 -- contrast
    bad = check_contrast(css_raw, css, light, dark, args.verbose)
    regressions, known, improved = [], [], []
    for theme, fg, bg, ratio, need_ratio, sites in bad:
        base = CONTRAST_BASELINE.get((theme, fg, bg))
        if base is None:
            regressions.append((theme, fg, bg, ratio, need_ratio, sites))
        elif ratio + 0.005 < base:
            regressions.append((theme, fg, bg, ratio, need_ratio, sites))
        else:
            known.append((theme, fg, bg, ratio, need_ratio, sites))
    still = {(t, f, b) for t, f, b, _, _, _ in bad}
    for key in CONTRAST_BASELINE:
        if key not in still:
            improved.append(key)

    if regressions:
        hard += len(regressions)
        print("FAIL  contrast: %d NEW pair(s) below the WCAG minimum" % len(regressions))
        for theme, fg, bg, ratio, need_ratio, sites in regressions:
            print("        [%-5s] %-9s on %-22s %.2f:1  (needs %.1f:1)"
                  % (theme, fg, bg, ratio, need_ratio))
            for s in sites:
                print("                  %s" % s)
            print("::error file=%s::New contrast failure %.2f:1 (needs %.1f:1) in %s theme -- %s on %s"
                  % (paths["style.css"], ratio, need_ratio, theme, fg, bg))
    else:
        print("OK    contrast: no new pair below WCAG AA")
    if known:
        print("      %d known pair(s) still failing (listed in CONTRAST_BASELINE):" % len(known))
        for theme, fg, bg, ratio, need_ratio, sites in known:
            print("        [%-5s] %-9s on %-22s %.2f:1  (needs %.1f:1)  e.g. %s"
                  % (theme, fg, bg, ratio, need_ratio, sites[0]))
    if improved:
        print("      %d baseline pair(s) now pass -- delete them from CONTRAST_BASELINE:"
              % len(improved))
        for theme, fg, bg in improved:
            print("        [%-5s] %s on %s" % (theme, fg, bg))

    # 2 -- dark parity
    orphans = check_dark_parity(themed, dark_names)
    if orphans:
        hard += len(orphans)
        print("FAIL  dark-parity: %d themed token(s) with no html.dark value" % len(orphans))
        for t in orphans:
            print("        %s" % t)
            print("::error file=%s::Themed token %s has no html.dark counterpart"
                  % (paths["style.css"], t))
    else:
        print("OK    dark-parity: every themed token has a dark counterpart")

    # 3 -- icons
    known, missing = check_icons(js)
    if known is None:
        print("WARN  icons: could not locate the svgIcon map -- check skipped")
    elif missing:
        hard += len(missing)
        print("FAIL  icons: %d reference(s) to an icon that does not exist" % len(missing))
        for name, ln in missing:
            print("        app.js:%d  \"%s\" renders blank" % (ln, name))
            print("::error file=%s,line=%d::Icon \"%s\" is not in the svgIcon map -- renders blank"
                  % (paths["app.js"], ln, name))
    else:
        print("OK    icons: all %d references resolve" % len(known))

    # 4 -- literals (ratchet)
    root_body, root_off = find_block(css, ":root")
    dark_body, dark_off = find_block(css, "html.dark")
    skip = []
    if root_off is not None:
        skip.append((root_off, root_off + len(root_body)))
    if dark_off is not None:
        skip.append((dark_off, dark_off + len(dark_body)))
    lits = check_literals(css, skip)
    soft += ratchet("literals", "raw colour literal(s) outside the token blocks",
                    lits, MAX_LITERALS, paths["style.css"], args.verbose)

    # 5 -- var() fallbacks (ratchet)
    fbs = check_fallbacks(css)
    soft += ratchet("fallbacks", "var(--token, literal) second value(s)",
                    fbs, MAX_FALLBACKS, paths["style.css"], args.verbose)

    # 6 -- focus rings (ratchet)
    fos = check_focus(css)
    soft += ratchet("focus", "outline:none rule(s) with no :focus-visible partner",
                    fos, MAX_BARE_OUTLINE, paths["style.css"], args.verbose)

    # 7 -- class coverage (warn only)
    orphan_cls = check_classes(css + "\n" + tw, js, html)
    if orphan_cls:
        print("WARN  classes: %d class(es) referenced with no rule anywhere" % len(orphan_cls))
        for c in orphan_cls[:20] if not args.verbose else orphan_cls:
            print("        .%s" % c)
        if not args.verbose and len(orphan_cls) > 20:
            print("        ... and %d more (--verbose for all)" % (len(orphan_cls) - 20))
    else:
        print("OK    classes: every referenced class has a rule")

    print("")
    if hard:
        print("FAIL: %d hard violation(s)." % hard)
        print("")
        print("These are defects a tech sees on a real VPU: text that does not")
        print("meet the contrast style.css itself requires, a token that has no")
        print("dark value, or a blank icon. Fix them, or -- for a contrast pair")
        print("that is genuinely unfixable -- add it to CONTRAST_ALLOW with a")
        print("comment saying why.")
        print("")
        print("Reproduce locally:")
        print("  python3 tools/ui-contract/check_ui_contract.py --verbose")
        return 1
    if soft:
        print("FAIL: a ratchet baseline was exceeded (see above).")
        print("Either fix the new occurrence, or -- if it is genuinely correct --")
        print("raise the matching MAX_* in tools/ui-contract/check_ui_contract.py")
        print("in the same commit, so the increase is reviewed.")
        return 1
    print("OK: Pulse UI contract holds.")
    return 0


def ratchet(name, noun, hits, limit, path, verbose):
    n = len(hits)
    if n > limit:
        print("FAIL  %-11s %d %s (baseline %d -- this change adds %d)"
              % (name + ":", n, noun, limit, n - limit))
        for ln, what in (hits if verbose else hits[:15]):
            print("        style.css:%-5d %s" % (ln, what))
        if not verbose and n > 15:
            print("        ... and %d more (--verbose for all)" % (n - 15))
        print("::error file=%s::%d %s -- baseline is %d" % (path, n, noun, limit))
        return 1
    if n < limit:
        print("OK    %-11s %d %s (baseline %d -- lower it to %d)"
              % (name + ":", n, noun, limit, n))
    else:
        print("OK    %-11s %d %s (at baseline)" % (name + ":", n, noun))
    return 0


if __name__ == "__main__":
    sys.exit(main())
