# Runbook — Cockpit live serve during live ops (R7)

Operator runbook for keeping the DasLab operator cockpit available as a live,
regenerate-on-request page during autonomous ("live") operation, so the Founder
can answer interrupt cards from the **Action Console** in well under 60 s.

> Binding contract: **ADR-0028** (cockpit form factor) D-3 + **ADR-0027** SI-1.
> The cockpit `--serve` process is **operator-invoked, loopback-only, and NOT a
> daemon**. Its cadence lives in an **external** OS scheduler entry the Founder
> owns — never inside the process, and **nothing in this repo installs it**.

## What it is

- `python3 scripts/cockpit_html.py --serve` binds `http.server` on
  `127.0.0.1:8765` (loopback only) and re-renders the cockpit on every GET.
- It is **read-only**: it surfaces state (KPIs, run feed, Action Console) and
  never dispatches, answers, or mutates anything (SI-7).
- The **Action Console** panel lists each `board/interrupts/<id>.json` card with a
  copy-paste `resume:<option>` stub; the Founder answers by writing that line into
  the interrupted ticket's body. The next `/daslab-cycle` wave detects it
  (`scripts/interrupt_roundtrip.py`) and resumes the parked work.

## Run it manually (interactive)

```bash
cd /path/to/daslab
python3 scripts/cockpit_html.py --serve          # foreground; Ctrl-C to stop
# then open http://127.0.0.1:8765/ in a browser
```

The static, no-server form (`python3 scripts/cockpit_html.py` → `board/.cockpit.html`)
is the canonical zero-infra fallback and needs no port.

## Keep it up during live ops (external OS entry — operator installs, not the repo)

Install **one** of the following as a deliberate, one-time operator act. Both are
loopback-only and removable at any time (removal disables the live page instantly;
it does not touch the loop).

### macOS — launchd (`~/Library/LaunchAgents/com.daslab.cockpit.plist`)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.daslab.cockpit</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>/path/to/daslab/scripts/cockpit_html.py</string>
    <string>--serve</string>
  </array>
  <key>KeepAlive</key><true/>
  <key>RunAtLoad</key><false/>
  <key>WorkingDirectory</key><string>/path/to/daslab</string>
  <!-- To capture logs to a file, add StandardOutPath / StandardErrorPath keys with an
       absolute, user-writable path (pre-created) — a per-user agent cannot write /var/log. -->
</dict>
</plist>
```

```bash
launchctl load   ~/Library/LaunchAgents/com.daslab.cockpit.plist   # start
launchctl unload ~/Library/LaunchAgents/com.daslab.cockpit.plist   # stop (disable live page)
```

> By default launchd sends the job's output to the unified system log. To capture it
> to a file, add `StandardOutPath`/`StandardErrorPath` keys with an absolute,
> user-writable path (pre-created) — a per-user LaunchAgent runs as you and cannot
> write root-owned `/var/log`.

### Linux — systemd user unit (`~/.config/systemd/user/daslab-cockpit.service`)

```ini
[Unit]
Description=DasLab cockpit (loopback, live ops)
[Service]
WorkingDirectory=/path/to/daslab
ExecStart=/usr/bin/python3 scripts/cockpit_html.py --serve
Restart=on-failure
[Install]
WantedBy=default.target
```

```bash
systemctl --user enable --now daslab-cockpit.service    # start
systemctl --user disable --now daslab-cockpit.service   # stop
```

## Safety notes

- **Loopback only.** Never expose the cockpit on a routable interface — it
  surfaces internal org state. The bind is hardcoded to `127.0.0.1` (D-3); do not
  change it, and do not front it with a public reverse proxy.
- **Read-only / no auto-answer.** The cockpit never writes a `resume:` value on
  the Founder's behalf. Interrupt gates always wait for a human (SI-7).
- **Not the scheduler.** This serves the *view*. The heartbeat `--tick` cadence is
  a separate, also-external, Founder-owned entry (see `board/schedule.yaml`).
- **Removal is the off switch.** Unload/disable the entry to stop the live page;
  no code change needed.
