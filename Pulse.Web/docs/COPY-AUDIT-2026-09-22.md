# Pulse copy audit: explanations an agent can say out loud

> **Status (2026-09-22):** everything below is applied on branch
> `copy-findings-structure` except the decisions listed under *Still open*.
> Findings now carry `recommendation` (the spoken body), `it`, `evidence` and
> `details`; `/api/network` returns the same records the Dashboard and Copy
> for ticket use, and the impact/label maps moved from app.js into main.py.
>
> **Decided 2026-09-22 (Ian):**
> 1. `uplink-on-camera-port` -> readiness **risk** (was unclassified, so info).
> 2. `tz-non-us` -> **critical** (readiness blocker).
> 3. Required ports -> **critical**: `port-required-blocked` is now a
>    blocker and its finding severity is critical, matching the Network card.
> 4. `gpu-anomaly` escalates to **Tier 3**.
>
> **Still open:** NTP uses the tile's claim ("can miss scheduled events"),
> not the code comment's stronger one. `wifi-disabled` stays unclassified
> (info). `tz-non-us` now stops readiness, but its only stated effect is logs
> that don't line up with events. If there is a bigger effect, the body
> should say it. A blocked LogMeIn *port* now fails readiness while a
> LogMeIn *filter block* (`lmi-ssl-blocked`, `tls-filtered-support`) stays
> info.

2026-09-22. Scope: every user-facing explanation in `app.js`, `main.py`,
`cloud_api.py`, `powershell.py` and the 58 collector scripts, extracted
mechanically (168 messages of 20+ words, 70 of 30+), then read by hand.
Line numbers are against branch `clarify-tls-copy` (origin/dev b9ddee7 plus
the SSL-inspection fix, ca5127d).

## Who reads this copy

Pulse finds the hard problem. A support agent then has to relay it, by phone
or email, to someone at the school (an AD, a coach, a custodian) and often,
through them, to venue IT. So every finding has to survive being read aloud to
a non-technical person, and still hand IT the exact thing to change.

"Copy for ticket" pastes each readiness finding's `title` + `recommendation`
verbatim (`app.js:2113-2119`). **The `main.py` recommendation strings are
the email.** They are the highest-leverage copy in the product.

## The standard

Every finding answers three questions, in this order, and nothing else goes
in the body.

| Part | Rule | Example (all streaming blocked) |
|---|---|---|
| **Title** | `<cause>, so <effect>`. Most titles already do this. | Streaming is blocked, so the VPU can't broadcast (today's title, keep it) |
| **Body: cause + effect** | One sentence. Name the thing, not the protocol. | The venue's network is blocking all three connections the VPU uses to send live video. |
| **Body: fix + owner** | One sentence. A step someone can do, and who does it. | Ask venue IT to open at least one. |
| **For venue IT** | Optional line. Ports, domains, lists. Protocol names live here and only here. | Outbound UDP 2088 and UDP 443 to prod-echo.pixellot.tv, and TCP 1935. Filters that match by destination must also allow *.pixellot.stream. |
| **How Pulse knows** | Optional, collapsed. Evidence, test method, file paths, VPU Manager equivalents. | - |

Body budget: 3 sentences, about 45 words. If the body needs more, the extra is
IT detail or evidence and belongs in one of the two lines under it.

## Scores

| # | Dimension | Score | Key finding |
|---|---|---|---|
| 1 | Cause stated plainly | 3 | Almost always present; in the Network lane it leads with the mechanism ("Zixi", "TLS handshake", "ICMP"). |
| 2 | Effect stated | 2 | Missing from ~10 bodies. For NTP and time zone the effect exists only in a code comment. |
| 3 | Action with an owner | 3 | Most end on a step and name venue IT. A few are circular or undoable ("escalate to support", "look at NIC buffer overflow"). |
| 4 | Sayable length | 1 | The findings agents relay most (streaming, LogMeIn, TLS, PoE) run 55-103 words and mix three audiences in one paragraph. |
| 5 | Consistency | 1 | 12 findings are written twice (ticket vs Network card) and have drifted; 5 terms have 2-8 names each. |
| | **Total** | **10/20** | **Acceptable: significant work needed** |

No P0 left on this branch. The P0 that prompted this audit (the SSL finding
naming `*.singular.live` when only `pixellot.tv` was intercepted, so an agent
sent IT the wrong domain) is fixed in ca5127d, which is **not yet on dev or in
1.3.0**.

## Systemic patterns

1. **Three audiences in one paragraph.** The school contact, venue IT and the
   agent are all addressed in the same run of prose, so the agent has to edit
   before sending anything. Split into body / For venue IT / How Pulse knows.
2. **Pulse defends its verdict in customer copy.** "(Pulse checks for both)",
   "the signature of a firewall...", "That proves TCP/1935 is open by port,
   not that pixellot.stream itself is allowed", "VPU Manager reports this same
   fault as...". True, useful to engineers, noise on the phone. Move to How
   Pulse knows.
3. **The effect is in the code, not the copy.** `main.py:1458` says a drifting
   NTP source "breaks signed-URL streaming"; the copy doesn't mention it.
   `main.py:1562` explains why the time zone matters; the critical finding
   doesn't. The per-service impact maps (`TLS_DOMAIN_IMPACT`, the port-tile
   help) already hold the effects, but findings like "port X unreachable" don't
   use them.
4. **Every finding written twice.** `main.py` writes the version that goes to
   the Dashboard and the ticket; `_buildNetIssues` in `app.js` writes the
   Network-card version. A rewrite to one side misses the other (the
   Aug 27 sweep and the SSL fix both had to touch two files). Affected: camera-
   port uplink, Wi-Fi disabled, Wi-Fi uplink, all streaming blocked, fallback,
   backup only, SSL inspection, web filter, LogMeIn blocked, PoE Molex, slow
   link, D: full.
5. **The Aug 27 sweep couldn't fix this.** 8cea160 swapped punctuation and cut
   hedges. It never shortened a message, and splitting a dash-joined paragraph
   into more sentences made several longer. Length and audience need a
   structure, not a style pass.

## Glossary: one name per thing

| Thing | Names in use today | Use |
|---|---|---|
| The 4-port card the cameras plug into | camera NIC, 4-port NIC, 4-port camera card, camera card, PoE card, network card, camera bank, NIC hardware | **camera card** |
| The port the internet cable belongs in | motherboard network port, motherboard Ethernet port, uplink adapter, internet adapter | **motherboard network port** |
| The school's network people | venue IT, the venue's IT team, the venue's IT or network team, the venue's network admin | **venue IT** |
| The three streaming connections | Zixi, primary streaming connection, main path, backup path, last resort, emergency fallback, RTMP fallback | **main path / backup path / last resort** (the port tiles already use these) |
| What IT adds for SSL inspection | SSL decryption bypass/exemption list, bypass list, SSL bypass, SSL-decryption exemption | **SSL-decryption exemption** |

Also: `app.js:4225` says "whitelist"; everywhere else says allowlist.

---

## P1: fix before the next release

These are relayed most often, and most are pasted straight into tickets.

### 1. All streaming blocked (critical)
`main.py:2127` (ticket), `app.js:4150` (Network card). 63 and 67 words.
Cause and effect present; buried in protocol detail; IT spec mixed into the body.

> The venue's network is blocking all three connections the VPU uses to send live video, so the game can't broadcast. Ask venue IT to open at least one.
>
> **For venue IT:** outbound UDP 2088 and UDP 443 to prod-echo.pixellot.tv, and TCP 1935. Filters that match by destination must also allow *.pixellot.stream, because the streaming servers change for every event.

### 2. Running on the last-resort path (critical)
`main.py:2147`, `app.js:4165`. 57 and 60 words. "Zixi", "RTMP over TCP/1935", "packet-loss protection".

> The venue's network blocks both normal streaming connections, so games are using the last-resort path: they start about 4 minutes late and have no protection against network hiccups. Ask venue IT to open UDP 2088 and UDP 443.
>
> **For venue IT:** outbound UDP 2088 and UDP 443. Filters that match by destination must also allow *.pixellot.stream.

### 3. LogMeIn blocked (warning)
`main.py:2361` (96 words), `app.js:4100` (103 words). The longest copy in Pulse.
Effect ("support can't connect") is only in the title.

> The venue's firewall is cutting off LogMeIn, so our support team can't reach this VPU remotely. Ask venue IT to exempt LogMeIn from SSL inspection and from their web filter's blocked categories.
>
> **For venue IT:** *.logmein.com and logmein.com, on ports 443 and 80. Allowing only secure.logmein.com is not enough; the gateways are control.lmi-app*.logmein.com.
>
> **How Pulse knows:** {n} failed connections since {date} and no successful login, from LogMeIn's own log in C:\ProgramData\LogMeIn.

### 4. Secure connections failing, cause unknown (warning)
`app.js:4052`. 68 words. Spends a clause on what it *isn't*.

> Something between the VPU and the internet is breaking its secure connections to the services below. If graphics or uploads fail while video streams, this is why. Ask venue IT what sits in that path on port 443 and have these domains exempted from it.
>
> **How Pulse knows:** it is not a blocked category or a substituted certificate; Pulse tests for both separately.

### 5. Internet plugged into a camera port (critical)
`main.py:1328`, `app.js:3882`. 57 and 58 words. Restates the cause twice ("must connect to the motherboard port", "the 4-port NIC is for cameras only").

> The internet cable is plugged into the camera card, so cameras may not be found and streaming can fail. Move it to the motherboard network port and make sure that port is enabled. Leave Wi-Fi on; the Pixellot Connect app needs it.

### 6. Wi-Fi turned off (warning)
`main.py:1366`. 58 words. The last sentence is about a different finding (uplink placement).

> The VPU's Wi-Fi is turned off, so the Pixellot Connect app can't find this unit. Turn it on in Windows: Network Connections, right-click the Wi-Fi adapter, Enable.

### 7. Camera card missing its extra power (critical)
`main.py:3214` (57 words), `app.js:5536` (69 words). Leads with wattage; effect is only in the app.js version.

> The camera card isn't getting its extra power, so it can't run a full set of cameras. Its Molex power lead is most likely unplugged. Power the VPU down, reseat that lead, then check again.
>
> **How Pulse knows:** the card reports a {x} W budget; a healthy card reports {y} W. VPU Manager shows the same fault as a failed POE Power Test.

### 8. Wrong time source (warning): effect missing
`main.py:1472`. Cause and fix, no effect; the fix is a `w32tm` command no school contact can run.
**Needs your call:** the effect ("a drifting clock breaks signed-URL streaming") is only in the code comment at `main.py:1458`. If it's accurate:

> The VPU is taking its time from {source} instead of the approved servers. If that clock drifts, streams can fail to start. A remote tech can fix this in a minute.
>
> **Fix (remote tech):** `w32tm /config /manualpeerlist:"0.us.pool.ntp.org 1.us.pool.ntp.org 2.us.pool.ntp.org 3.us.pool.ntp.org" /syncfromflags:manual /update`, then restart the Windows Time service.

### 9. Non-US time zone (critical): effect missing
`main.py:1575`. Critical severity, zero effect in the copy. The comment at `main.py:1562` says the only consequence is logs that don't line up with field events.
**Needs your call:** either surface an effect that justifies critical, or drop it to a warning. An agent can't explain a critical that has no stated consequence.

### 10. Required port blocked (warning): effect missing
`main.py:2224`. "This is a required Pixellot endpoint" is not an effect. The port-tile help already says what stops working for each port; the finding should reuse it.

> {Service} can't be reached on port {port}, so {impact from the port help map}. Ask venue IT to open it.

---

## P2: next pass

| Where | Problem | Proposed |
|---|---|---|
| `main.py:2173`, `app.js:4184` Backup path only | Protocol names; 34-41 words | The main streaming connection is blocked, so the VPU is using its backup. Tonight's stream is fine, but one more block would force the slower last-resort path. Ask venue IT to open UDP 2088. |
| `app.js:4114` LogMeIn recovered | 54 words; "consistent with the venue disabling packet inspection" | LogMeIn was blocked here until {time}, then connected, so the venue likely changed its filter. Remote support works now. If this VPU drops out of LogMeIn again, check the venue's web filter first. |
| `main.py:1639` Windows support ending | 37 words to reach "no action needed" | No action needed. {Windows} leaves mainstream support on {date}, but VPUs run the IoT Enterprise edition, which gets security updates until {date}. Also consider keeping info-only items out of the ticket. |
| `app.js:3919` Gateway ignores ping | 46 words explaining away a **red** gateway test | No action needed. The gateway ignores ping, as many routers do, but traffic is getting through it. **And** stop showing that test red: the copy is apologising for the indicator. |
| `main.py:1915` KeepAgentUp down | "can't self-heal a process failure" | The watchdog that restarts Pixellot's software after a crash isn't running, so a crash would stay down until someone restarts it. Click Restart Agent + Coordinator on the Services page, or reboot the VPU. |
| `main.py:1685` Unknown GPU | "Escalate to support" when the reader *is* support | Name the destination (Pixellot support? Tier 2?). |
| `main.py:1090` Other remote-access tools | "compete with LogMeIn for ports / system tray. Confirm with field operations before relying on these." | Only LogMeIn is approved for remote access, and other tools can interfere with it. Check with field operations before using them. |
| `Start-NetworkCapture.ps1:598, 606` Resets / drops | Lists causes, no effect, "Look at NIC buffer overflow" is not a step anyone on the call can take | Connections are being cut off. Check Network Test for a web filter or SSL inspection finding first; if there's none, capture again during an event and escalate. |
| `Start-NetworkCapture.ps1:323` Can't capture packets | 64 words; "original October 2018 release" | This VPU's Windows is too old to record individual packets, so resets, retransmissions and the endpoint list aren't available. The totals above are accurate. The fix is the missing Windows update on the Software Updates card. |
| `app.js:3461` Last-resort tile help | 59 words; test method in the tooltip | Last-resort streaming path, used only when both main connections are blocked. Games start about 4 minutes late on it. If this is blocked too, the game can't broadcast. (Move the "tested against a public RTMP host" caveat to How Pulse knows.) |
| `app.js:3459` Backup path tile help | "(Zixi over UDP/443, the same streaming protocol as UDP/2088, not HTTPS)" | Backup live-video connection. This or the main path alone gives a full-quality stream; with both blocked the game drops to the last-resort path. |
| `app.js:4225` DNS filtering | No effect; "whitelist" | The venue's DNS is failing to look up Pixellot services, so the VPU can't reach them. Switch the VPU's DNS to 8.8.8.8 / 8.8.4.4, or ask venue IT to allow these hostnames. |
| `app.js:4240` DNS redirected internally | Mechanism first | The venue's DNS is sending Pixellot addresses to an internal server, which usually means a login page or an inspection proxy is in the way. Ask venue IT to bypass inspection for these hosts. |
| `app.js:1156` Venue ID missing | Leads with a file path | Pulse couldn't find this unit's Pixellot venue ID, so it can't look up its events in the cloud. This happens on a freshly imaged unit or after the logs rotate. (Path to How Pulse knows.) |
| `app.js:1391` Camera identity note | Shows the camera admin credential ("Admin:1234") in UI text, which ends up in screenshots like the one that prompted this audit | Drop the credential from visible copy. |

## P3: polish

- Apply the glossary above across both files.
- `app.js:1150`: "Cloud evidence reflects right now. Local recording facts are from the event itself." Unclear; say which columns are live and which are historical.
- `main.py:1671` / `1712` GPU findings: put the effect first ("No NVIDIA card was found, so this VPU can't encode video.").

## What's working (keep it)

- **Titles.** Most already read `<cause>, so <effect>`: "Wi-Fi card is disabled, so the Pixellot Connect app can't reach this VPU". An agent can say most titles as they are.
- **Confirm dialogs** (`app.js:9591`, `9613`, `6420`): name the action, the consequence and the recovery ("Pulse won't come back on its own. Reopen it from the desktop shortcut").
- **Fault Isolator verdicts** (`app.js:9133`, `9189`, `9204`): conclusion first, then the next step, with honesty about what wasn't confirmed.
- **Ownership stated plainly** where it matters: "That is a publishing issue on our side, not a problem with this VPU or its network" (`main.py:4955`); "Pixellot support has to direct" (`app.js:6762`).
- **ScoreConnect recovery help** (`app.js:8407-8408`): one cause, one effect, 21-27 words.
- **Per-service impact lines** (`TLS_DOMAIN_IMPACT`): exactly the effect sentences findings should reuse.

## Recommended actions

1. **[P1] `/impeccable shape`**: give findings structured fields (`cause_effect`, `fix`, `it_detail`, `evidence`) and render them as body / For venue IT / How Pulse knows, on screen and in Copy for ticket. Make `main.py` the single source and have the Network card render those records instead of writing its own copy. This removes pattern 4 and makes pattern 1 impossible to reintroduce.
2. **[P1] `/impeccable clarify`**: apply the ten P1 rewrites above (8 and 9 need your call on the effect first).
3. **[P2] `/impeccable clarify`**: the P2 table and the glossary.
4. **[P2] `/impeccable harden`**: stop the gateway-ping test showing red for a non-fault, and remove the camera credential from visible text.
5. **`/impeccable polish`**: final read of the Network and Dashboard cards at remote-desktop widths.
