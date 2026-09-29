# Scoreboard controllers: what connects to a ScoreLink, and how

Source: NFHS Network support article "Scoreboard Controllers" (Mar 18, 2026,
support.nfhsnetwork.com/s/article/Scoreboard-Controllers), exported to PDF by
Ian 2026-09-29. This digest is the source for `SC_CONSOLES` in `app/main.py`;
change the two together. Bench check: Daktronics All Sport 5000 on the gray
tip, J-port, SC III "Daktronics Auto Detect", data present (vpu-home,
2026-09-29).

## The cable

One **multi-tip serial adapter cable**. The 9-pin (DB9) end (#4) plugs into the
ScoreLink's SCOREBOARD port. The other end splits into three tips; only one is
plugged into the console:

| # | Tip | Used by |
|---|-----|---------|
| 1 | Red 1/4" | Fair-Play (MP-50, MP-69, MP-70), Spectrum MSX/MSX5 and All-American 3000 after a jack modification |
| 2 | Gray 1/4" | Daktronics (1600, 3000, 4000, 5000, 5500, Pro Series 1, MX-1), Electro-Mech |
| 3 | Black BNC | Nevco tabletop controllers (MPC-5/6/7, MPCW) |

Custom cables (not the multi-tip) are used by All-American 8000/9000 (PlayOn
RJ45 + DB9), Eversan 9700 (made to length), OES ISC 9000 (4-pin XLR to DB9, or
DB9 null modem), Varsity-family LCD controllers (PlayOn, DIN), and the
Daktronics All Sport CG (straight-through M/F serial, no null adapter).

Extensions: the 1/4" tips take a 1/4" TRS (stereo) extension. Nevco takes
**50-ohm** coax only; 75-ohm video cable looks the same and must not be used.
Custom cables are made to length and have no extensions. A legacy Electro-Mech
wireless receiver sits next to the VPU and uses no extension.

## By brand and model

**Daktronics** (gray tip, J ports on the back)
- All Sport 1600: J1 or J2. Baseball and football. Models ending R6 (e.g. 1610R6) can use a wireless ScoreLink.
- All Sport 2000: **not compatible**. Options: upgrade the console, a PiP camera, or manual scoring in Console.
- All Sport 3000: J1, J2 or J3. Football only.
- All Sport 4000: J1, J2 or J3. Baseball, basketball, football, hockey, volleyball.
- All Sport 5000: J1, J2 or J3. All versions. R6 on the model sticker above the power cable means wireless-capable; otherwise a Wireless Link.
- All Sport 5500: J1, J2 or J3. Basketball only (a gym usually uses OCR).
- All Sport CG: connects to the ScoreLink with a straight-through M/F serial cable into the CG's Control port; SC III "All Sport CG" settings. Pairs to the main console by broadcast group and channel.
- All Sport Pro: Series 1 has J ports (gray tip, TRS extensions); Series 2 needs a Daktronics wireless ScoreLink (its 1/4" jack does not work). Regular Daktronics codes.
- All Sport MX-1: interface box, gray tip through Daktronics' optional signal cable and an F TRS coupler, or wireless (R6 radio). Use All Sport 5000 codes.
- RC-100, RC-200 handhelds: **not compatible**. Upgrade (All Sport 5000, MX-1, Pro) or PiP.
- Wireless setup: the console asks for radio settings after a sport-code change (ENTER keeps, CLEAR edits). Default Broadcast Group 1, Channel 01. A scoreboard shows its settings at power-up as "bX CY" (X group, Y channel) in the clock or score digits, with radio controllers nearby switched off.

**Electro-Mech** (gray tip, TRS extension)
- Outputs on the back labelled Scoreboards, usually 2 or 4. One output only: try a splitter, or Electro-Mech adds one ($80 plus shipping).
- ScoreLink SL-400 sticker on the bottom: wireless-capable; use Electro-Mech Wireless presets.
- Legacy wireless receivers SL400/SL350/SL330 only (SL300, SL200 are not compatible).

**Fair-Play** (red tip)
- MP-70 (MP-71/72/73): the most common. Scoreboard port 1 or 2. Software 3.0 or higher (shown at boot) can use a Fair-Play wireless ScoreLink; lower needs a Wireless Link.
- MP-50 (MP-51/52/53): treat as MP-70.
- MP-69: football and baseball only; MP-69 codes.
- MP-80 and MP-60: wireless only, no data outputs. Wireless ScoreLink, "Fairplay MP80" settings. A Rainey Electronics wired adapter exists but is legacy (Fairplay Auto Detect; two USB cables).

**Nevco** (black BNC tip, 50-ohm coax)
- MPC-5, MPC-6, MPC-7 and wireless MPCW tabletop models: Nevco settings. MPC-7 Soccer uses the MPC-7 Football code.
- MPC-X, MPCX2 handhelds: **not compatible** (MPCX2 has had unofficial success with MPC-7 settings; do not recommend).

**Other brands**
- All-American 3000 / MP3000: needs a SportzCast 1/4" jack modification ($175), then the red tip. Football only; legacy ScoreConnect 3.4.5.0.
- All-American 8000 (Scoreboard port) and 9000 (Hardwire port): PlayOn custom cable.
- Colorado Time Systems: treat as not supported (no pool score graphics); lane timers use PiP.
- Eversan 9700: custom cable into a DATA port; no extensions.
- OES ISC 9000: 4-pin XLR GAME OUT with OES (RS422) settings, or DB9 with OES (RS232) and a null modem cable.
- Spectrum MS250: **not compatible**. MSX and MSX5: need a 1/4" jack modification ($175), then the red tip; never the "(RS232)" settings. Data that cycles through test values means TEST MODE: restart the console and start a new game.
- Varsity, All-Star, Sportable, BSN (one LCD controller): PlayOn custom cable into DIN1 or DIN2; Varsity settings. No wireless.
- Software scoreboards: ScoreVision and PCScoreboards over the network (same subnet as the VPU). Major Display: **not compatible**, use OCR.
