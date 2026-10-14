# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

PlayOn support agents diagnosing a Pixellot VPU (the on-site video processing unit) remotely over LogMeIn, usually while on the phone with school staff who are standing next to the equipment. The agent reads Pulse and relays physical checks and fixes to a non-technical person on site. Secondary: field techs running Pulse on the VPU in person.

## Product Purpose

Pulse is a diagnostic web app that runs on the VPU itself (FastAPI + vanilla JS, launched from `run.bat`) and tells the agent whether the unit is ready to stream a game, and if not, what is broken and what to say to fix it. Success means the agent finds the fault and gets it fixed on one call, without escalating to Pixellot.

## Positioning

Pulse runs on the box and reads the box directly: cameras, network, ScoreConnect, audio, PoE, Pixellot software, and Windows state, collected by PowerShell scripts on the unit. Pixellot's VPU Manager reports its own view; Pulse checks that view against the machine's actual state.

## Operating Context

- Viewed through a LogMeIn remote-desktop session, at RDP window widths, in light or dark theme.
- Fleet is Windows 10 LTSC 1809 with Windows PowerShell 5.1; demo mode runs on macOS/Linux for development.
- The agent often cannot see the equipment. Physical facts (which cable, which scoreboard controller) come from the school contact.
- Gen-3 Linux VPUs have no shell access; never propose commands for them.

## Capabilities and Constraints

- Lanes: Camera Connectivity, ScoreConnect, Network, System, Setup, Audio, Pixellot Cloud (plus streaming, events, disks, updates).
- Every finding states the cause, the effect, and a step the agent can say out loud to a school. `main.py` is the single source for finding copy.
- A check that never ran must never read as a pass: loading, empty, collector-failed, and stale states each look different.
- One word and one colour per machine state across the app.
- Score comes from ONE source: an OCR camera or ScoreConnect. Warnings judge only the source the unit actually uses.
- ScoreConnect: Pulse can measure SC III service state, the ScoreLink USB device, configured vendor/sport/connection type, and live raw scoreboard data. It cannot detect which cable, extension, or controller is physically connected.

## Brand Commitments

Product name "Pulse". Plain, direct language written for a field tech, not a developer. An existing design system is catalogued on claude.ai/design.

## Evidence on Hand

- Real field incidents recorded in project notes (e.g. Armstrong IL, Bradwell GA, Red Lodge) inform findings.
- Bench units VPU2 and vpu-home for validation.
- ScoreConnect hardware imagery and the cable-to-controller chart are to be supplied by Ian; do not fabricate cable compatibility.

## Product Principles

1. Point to the broken part, not just the symptom.
2. Every recommendation is something a non-technical person on site can do or confirm.
3. Measured and assumed facts never look the same.
4. Judge the configuration the unit actually uses, not every possible one.
5. Validate on a real VPU before production; demo mode proves layout, not collectors.

## Accessibility & Inclusion

Legible over compressed remote-desktop video: contrast-checked palette in both themes (WCAG AA), no meaning carried by colour alone.
