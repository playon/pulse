---
name: Pulse
description: Calm, flat, status-led diagnostics for a support agent reading a VPU over remote desktop.
colors:
  page-bg: "#f1f5f9"
  surface: "#ffffff"
  sidebar-bg: "#e8eef5"
  border: "#e2e8f0"
  text: "#1e293b"
  text-muted: "#475569"
  text-dim: "#5b6980"
  text-dimmer: "#5d6b80"
  ok: "#137638"
  critical: "#bf2121"
  warning: "#9b4708"
  info: "#2460e3"
  teal: "#0f766e"
  purple: "#7c3aed"
  page-bg-dark: "#0f1117"
  surface-dark: "#1c1f2e"
  surface-2-dark: "#161822"
  sidebar-bg-dark: "#161822"
  border-dark: "#2a2d3e"
  text-dark: "#e2e8f0"
  text-muted-dark: "#94a3b8"
  text-dim-dark: "#8593a6"
  text-dimmer-dark: "#7b899e"
  ok-dark: "#22c55e"
  critical-dark: "#f16161"
  warning-dark: "#eab308"
  info-dark: "#60a5fa"
  teal-dark: "#2dd4bf"
  purple-dark: "#a78bfa"
  led-ok: "#22c55e"
  led-warn: "#f59e0b"
  led-down: "#64748b"
  led-connecting: "#3b82f6"
  fill-critical: "#dc2626"
  fill-warning: "#b45309"
  fill-info: "#3b82f6"
  fill-danger-button: "#ef4444"
  on-accent: "#ffffff"
  board-bg: "#0f1419"
  board-text: "#e8ecf1"
  board-muted: "#728193"
  board-ok: "#22c55e"
  board-bad: "#ef4444"
  board-accent: "#f97316"
typography:
  body:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
  data:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
  nav:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.9rem"
    fontWeight: 500
  label:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.7rem"
    fontWeight: 600
    letterSpacing: "0.08em"
  badge:
    fontFamily: "ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.7rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.04em"
rounded:
  xs: "3px"
  sm: "4px"
  md: "6px"
  lg: "8px"
  xl: "12px"
  pill: "999px"
spacing:
  card: "1.25rem"
  stack: "1.25rem"
  row-y: "0.5rem"
  row-x: "0.75rem"
components:
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.text}"
    rounded: "{rounded.lg}"
    padding: "{spacing.card}"
  button-solid:
    textColor: "{colors.on-accent}"
    rounded: "{rounded.md}"
    padding: "0.5rem 1rem"
    typography: "{typography.body}"
  button-outline:
    backgroundColor: "transparent"
    textColor: "{colors.info}"
    rounded: "{rounded.md}"
    padding: "5px 12px"
  badge:
    textColor: "{colors.ok}"
    rounded: "{rounded.pill}"
    padding: "2px 9px"
    typography: "{typography.badge}"
  nav-item:
    textColor: "{colors.text-muted}"
    padding: "9px 16px"
    typography: "{typography.nav}"
  nav-item-active:
    textColor: "{colors.info}"
  finding-row:
    textColor: "{colors.text}"
    rounded: "{rounded.md}"
    padding: "8px 10px"
---

# Design System: Pulse

## Overview

**Creative North Star: "The Instrument Panel"**

Pulse is read, not browsed. An agent has it open in a LogMeIn window, compressed and often narrow, while talking to someone standing next to a rack. The look follows from that: flat surfaces, thin borders, small type, and colour spent almost entirely on machine state. A glance should answer "can this unit stream tonight" before any text is read.

The system is quiet on purpose. Structure comes from a 1px border and a half-step of background tone, not from shadow or decoration. Brand lives in precision: one word and one colour per state, contrast checked in both themes, and no meaning carried by colour alone. Controls are small and low-chrome, because they sit beside the facts and must not compete with them.

**Key Characteristics:**
- Flat by default. Cards are bordered, not elevated.
- Colour means state. Blue is the only non-status accent, used for the selected item and links.
- Dense but ranked. Many small rows, one clear verdict per card.
- Two themes, both contrast-checked. Light is the default; dark follows the system or a saved choice.
- Monospace for measured values (IPs, ports, byte strings, timestamps).

## Colors

A cool slate neutral ramp carries all structure. Six semantic accents carry state. Every token is defined once for light on `:root` and remapped for dark on `html.dark`.

### Primary
- **Signal Blue** (`#2460e3` light, `#60a5fa` dark): the selected nav item, focus outlines, links, the info badge and the outline-blue button. It is the only accent that does not mean a machine state.

### Secondary
- **Pass Green** (`#137638` light, `#22c55e` dark): healthy, running, passed.
- **Fault Red** (`#bf2121` light, `#f16161` dark): failed, stopped, critical.
- **Caution Amber** (`#9b4708` light, `#eab308` dark): warning, degraded, risk.

### Tertiary
- **Teal** (`#0f766e` / `#2dd4bf`) and **Violet** (`#7c3aed` / `#a78bfa`): minor category accents (for example a type of data source). They never stand for a verdict.

### Neutral
- **Page Slate** (`#f1f5f9` / `#0f1117`): the page background.
- **Card White** (`#ffffff` / `#1c1f2e`): cards and raised rows.
- **Rail Slate** (`#e8eef5` / `#161822`): the sidebar, a half-step darker than the page so navigation reads as subordinate.
- **Hairline** (`#e2e8f0` / `#2a2d3e`): borders and table rules.
- **Ink** (`#1e293b` / `#e2e8f0`): body text. Three quieter tiers follow, `text-muted`, `text-dim`, `text-dimmer`, each measured to 4.5:1 on the darkest surface it lands on.
- **Port LEDs** (`led-ok`, `led-warn`, `led-down`, `led-connecting`): vivid status-light colours shared by both themes, for port lamps, tile dots and the legend.
- **Solid fills** (`fill-critical`, `fill-warning`, `fill-info`, `fill-danger-button`): the only backgrounds allowed behind white text. They do not remap per theme.
- **Scoreboard Board** (`board-*`): a fixed near-black panel that stays dark in both themes. Anything drawn on it uses `board-ok`, `board-bad` or `board-accent`, never the `accent` tokens.

### Named Rules
**The Colour Means State Rule.** A status colour is a verdict. Never use red, amber or green for decoration, and never show a state in colour alone: pair it with a word or a glyph.

**The Text-Colour Accent Rule.** The six semantic accents are text and glyph colours only. A solid fill behind white text uses a `fill-*` token, because a colour light enough to read on a card is too light to carry white.

**The Darkest Surface Rule.** Check a text tier against the darkest light surface it lands on (the sidebar), and the lightest dark surface (the card), not against the page body.

## Typography

**Body Font:** the system sans stack (`ui-sans-serif, system-ui, sans-serif`). No web fonts are loaded, which keeps the first paint fast on a VPU and over a remote session.
**Data Font:** a system monospace stack (`ui-monospace`, Cascadia Mono, Menlo, Consolas) for measured values.

**Character:** Neutral and mechanical. The system fonts are chosen for reliability on a Windows 10 LTSC image, not for personality.

### Hierarchy
- **Body** (400, 0.875rem): page prose, table cells, finding titles.
- **Nav** (500, 0.9rem): sidebar labels. The active item is the same size, tinted blue.
- **Data** (400, ~0.75rem, monospace): IPs, ports, byte strings, timestamps, log lines.
- **Label** (600, 0.7rem, 0.08em tracking, uppercase): card section labels and table headers. Short, never a sentence.
- **Badge** (600, 0.7rem, 0.04em tracking, uppercase): status tokens only (PASS, RUNNING, NOT FOUND).

The scale is dense and clustered: roughly a dozen sizes between 0.65rem and 0.95rem, with 0.7 to 0.85rem carrying most of the screen. Metadata at 10 to 12px is normal here, so its colour contrast matters more than usual.

### Named Rules
**The Short Caps Rule.** Uppercase and tracking belong to labels and status tokens of a word or two. Never set a sentence in capitals.

**The Say-It-In-Words Rule.** Copy is written for a field tech to read aloud to a school. A collector's raw string is never UI copy; it goes through the state vocabulary first (see the `pulse-status-vocabulary` skill).

## Layout

A fixed 14rem (`w-56`) sidebar of grouped navigation on the left, a single scrolling content column on the right. Content is a vertical stack of cards separated by `1.25rem`; summary grids sit inside cards and collapse by container width. The app is built for remote-desktop window widths, not for phones, though it collapses: the sidebar becomes a horizontal bar at 767px, and layout breakpoints sit at 520, 600, 640, 700, 768, 900 and 1100px.

Rhythm is tight and consistent: card padding `1.25rem`, table cells `0.5rem 0.75rem`, finding rows `8px 10px`. Density is high on purpose. Tables and key-value lists carry the page, and the verdict sits above them.

### Named Rules
**The Verdict-First Rule.** Each page opens with its verdict (state and one sentence), then evidence. A reader who stops after the first card should still know what to do.

**The No Horizontal Scroll Rule.** A card never overflows its container at RDP widths. Wide tables scroll inside their own `overflow-x: auto` wrapper. Check with the `pulse-render-sweep` skill.

## Elevation & Depth

Flat by default. Depth is carried by tone and border, not shadow: the sidebar is a half-step darker than the page, cards are a step lighter, and a 1px `border` draws every edge. State rings are drawn as inset box-shadows (`inset 0 0 0 1px` in the state colour), which is an outline, not elevation.

### Shadow Vocabulary
- **Modal lift** (`box-shadow: 0 20px 60px rgba(0, 0, 0, 0.45)`): modals and floating layers only. A scrim (`rgba(8, 10, 16, 0.82)`) sits behind them.
- **Soft raise** (`0 2px 6px -3px`, colour `--c-shadow-lift`): a small offset shadow under raised camera tiles.
- **Focus ring** (`0 0 0 3px rgba(59, 130, 246, 0.35)`): keyboard focus on splash and theme controls. Elsewhere focus is a 2px solid `info` outline.

### Named Rules
**The Flat-At-Rest Rule.** Surfaces carry no shadow at rest. A shadow appears only on layers that float above the page.

**The No Glow Rule.** No coloured halos. A coloured zero-offset shadow reads as decoration, and in this product colour is reserved for state.

## Shapes

Small, practical radii. Cards use 8px; buttons, finding rows and most controls use 6px; inline chips and code use 3 to 4px; status badges and counters are full pills (999px); LEDs and dots are circles. Edges are 1px solid in `border`. There are no clipped corners or custom silhouettes beyond the camera and VPU diagrams, which draw physical hardware.

## Components

Every component is quiet and legible: small, low-chrome, and never louder than the fact beside it.

### Buttons
- **Shape:** gently rounded (6px).
- **Solid (`.btn`):** `0.5rem 1rem`, 0.875rem at weight 500, white text on a `fill-*` token. Hover dims to 85% opacity; disabled drops to 40%.
- **Outline (`.btn-outline` + `.btn-ol-*`):** transparent, `5px 12px`, 0.75rem. A 1px border and text in the state colour (green, blue, amber, red, or muted grey). Hover fills with that colour's tint. This is the default action button.
- **Destructive:** red outline or `fill-danger-button`, always with a confirm that names the real consequence.

### Chips (badges)
- **Style:** pill, `2px 9px`, 0.7rem at weight 600, uppercase, 0.04em tracking, tint background with a text-colour accent (`.badge-pass`, `-fail`, `-warn`, `-info`, `-muted`, plus `-running`, `-stopped`, `-notfound`).
- **Rule:** short status tokens only. A badge states a verdict; it never holds a sentence.

### Cards / Containers
- **Corner Style:** 8px.
- **Background:** `surface`, with a 1px `border`.
- **Shadow Strategy:** none (see Elevation).
- **Internal Padding:** `1.25rem`. Section labels use the Label style at the top.

### Inputs / Fields
- **Style:** native inputs and selects on `surface` with a `border`.
- **Focus:** a 2px solid `info` outline, 1 to 2px offset. Never remove it.

### Navigation
- **Style:** grouped items, 0.9rem, an 18px icon, 11px gap, `9px 16px`. Default text is `text-muted`.
- **Active:** `info` text, a faint blue tint, a 3px left rule, weight 500.
- **Health flag:** a right-aligned 14px warning triangle in amber or red when a lane has a finding. It must carry an accessible name, because it is a colour-only cue today.
- **Mobile:** below 767px the sidebar becomes a full-width horizontal bar.

### Finding row
The signature component. A full-width disclosure button (`8px 10px`, 6px radius): a state dot, a verdict word, the title, and a chevron. Opening it shows the cause, the effect and the step to say to the school. Keyboard focus is a 2px `info` outline, inset.

### Status LED and tile
Round lamps in the `led-*` colours, shared by port LEDs, camera tiles and the legend, so one state is one shade everywhere.

### Scoreboard board
A fixed-dark panel (`board-*`) that mimics a stadium board. It stays dark in both themes and uses its own status colours.

## Do's and Don'ts

### Do:
- **Do** route every state through the shared vocabulary: one word and one colour per state, from collector to badge to dot.
- **Do** make loading, empty, failed and stale look different, and never let an unrun check read as a pass.
- **Do** put the verdict first, then the evidence, then the raw value in monospace.
- **Do** pair every status colour with a word or glyph.
- **Do** clear 4.5:1 for any text, including 10 to 12px metadata, in both themes.
- **Do** use `fill-*` tokens behind white text and `accent` tokens for text and glyphs.
- **Do** add new colours as `--c-*` tokens with a dark remap, then run the `pulse-ui-contract` skill.

### Don't:
- **Don't** add a drop shadow, glow or gradient to a card, button or badge.
- **Don't** use a status colour decoratively, or the same colour for two states.
- **Don't** put a sentence in a badge or capitals.
- **Don't** show a collector's raw string, a bare port number, a filename or an unexpanded acronym as primary UI copy.
- **Don't** animate `width`, `height` or `max-height`; use `transform`, `opacity` or `grid-template-rows`.
- **Don't** load web fonts or CDN assets. Pulse must run on a VPU with no guaranteed internet.
- **Don't** let a card overflow at RDP widths, or hide the only plain-English meaning in a hover tooltip.
