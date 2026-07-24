# Runbook — WS-H: self-hosted web control plane (ADR-0039)

**Goal (MUSTAQIL WS-H):** operate DasLab from a browser on the tenant's own Ubuntu/macOS server — see the board and the real cockpit, and perform governed, audited actions — without breaking board-as-truth, never-auto-approve, or NOT-a-daemon.

**Status at merge (DAS-1604, AADL Stage-5 / GATE-5): `ws_h_control_plane` =
`false` in `config/features.yaml`.** No live control plane ships. The
default, always-available surface is the ADR-0028 static read cockpit
(read-only, dispatches nothing). Sections 0–6 below finalize the deploy
story — offline install, Founder-gated enable, degrade behavior, rollback.
This ticket documents that story; it does **not** flip the flag and does
**not** stand up the server (that stays a later, explicit Founder act). The
original PoC narrative (sections 7–9) is kept below as the verified spike
record.

## 0. What ships vs. what is documented-only

| | Ships at merge (this ticket) | Documented, Founder-executed later |
| --- | --- | --- |
| Feature flag | `ws_h_control_plane: false` (`config/features.yaml`) | Flipping to `true` is a separate, explicit Founder act |
| Optional process | Not installed, not enabled | `systemd`/`launchd` `.example` units, copied + edited + enabled by the Founder |
| RBAC / vault | `config/rbac.yaml` (SSOT, already governance-reviewed, Founder-only `gate.approve`/`run.trigger`/`config.edit.security`) | Tenant vault token map (`$DASLAB_CP_RBAC`) is provisioned per tenant at enable time |
| Default runtime surface | ADR-0028 static read cockpit | — (this stays the default whenever the flag is OFF or the process is absent) |

## 1. Offline install (CP-6)

Two-phase recipe: build the vendored-wheel closure on a network-connected
host, then install with `--no-index` on the offline tenant VM. The
control-plane deps (`fastapi`, `uvicorn`) live in
`tools/control_plane/requirements-control.txt` — **opt-in, not in core**
`requirements.txt`; a normal DasLab install never pulls them in.

### 1.1 Build the bundle (network host, once)

```bash
python3 tools/control_plane/install/build_offline_bundle.py \
  --wheels-dir tools/control_plane/.vendor/wheels \
  --site-packages-dir tools/control_plane/.vendor/site-packages
# prints the two pip commands (pip download --platform ... / pip install --no-index --target=)
# and runs them; omit --dry-run to execute for real
```

`build_offline_bundle.py`'s `plan()` / `build(dry_run=True)` never touch the
network or the filesystem — pure planning, safe to run anywhere first.

### 1.2 Verify the closure — before boot, every time

```bash
python3 tools/control_plane/install/verify_closure.py \
  --wheels-dir tools/control_plane/.vendor/wheels fastapi uvicorn
# [verify-closure] OK — full closure present
```

This checks the **real** `Requires-Dist` metadata (zipfile + email-header
parsing, no import, no pip) — it catches the class of gap where pip's
cross-platform resolver silently drops a marker-gated dependency (the
`exceptiongroup` case seen while building this bundle, see section 8). Run
this before every boot on a new offline target; a closure gap must fail
loudly here, not as a runtime `ImportError` on the tenant VM.

`tools/control_plane/.vendor/` is gitignored — it is a machine-specific
install cache, not source. The tracked artifacts are the two install scripts
plus `tools/control_plane/requirements-control.txt`.

### 1.3 Install on the offline tenant VM

```bash
cd /path/to/daslab
export PYTHONPATH="$(pwd)/tools/control_plane/.vendor/site-packages"
```

No `pip install`, no package-index reachability needed — `--no-index` already
populated `site-packages/` on the build host in step 1.1; the offline target
only needs the copied directory on `PYTHONPATH`.

(An online target may instead run `pip install -r
tools/control_plane/requirements-control.txt` directly and skip the vendored
bundle.)

## 2. NOT-a-daemon / degrade (CP-5) — the default path

On every launch attempt, `tools/control_plane/install/degrade.py` decides
whether the control plane is eligible to run or the surface degrades to the
static cockpit. This is the **ordinary** path, not an emergency fallback:

```bash
python3 tools/control_plane/install/degrade.py
```

Degrade triggers, first match wins:

1. `ws_h_control_plane` feature flag OFF in `config/features.yaml` (the
   shipped default — true today).
2. Optional deps (`fastapi`/`uvicorn`) not importable (no vendored bundle on
   `PYTHONPATH`, no `pip install` done).
3. `--force-static` explicit override.

Any of these renders the ADR-0028 static read cockpit
(`board/.cockpit.html`, via `scripts/cockpit_html.py`, subprocess — no panel
re-implemented) and exits. **No server is started. Nothing is dispatched.**
`degrade.py` never execs uvicorn itself, even when it reports the control
plane "eligible" — starting the real process stays a separate, deliberate act
(section 3).

Since the flag ships OFF, `degrade.py` short-circuits on trigger 1 before
even probing whether fastapi/uvicorn are importable — a disabled control
plane never asks the dependency question.

## 3. Enable (Founder governance act — documented here, not executed by this ticket)

Enabling the control plane requires ALL of the following, each a deliberate,
Founder-performed step. None of them happens as a side effect of merging this
runbook.

### 3.1 Flip the feature flag

Edit `config/features.yaml`:

```yaml
ws_h_control_plane: true    # was: false
```

`config/features.yaml` is a `config.edit.security`-class change under
`config/rbac.yaml` — Founder-identity only (structural, not just
convention: `scripts/rbac.py` fail-closes on any grant that would let a
non-founder kind touch it).

### 3.2 Provision the tenant RBAC token map

```bash
cat > /secure/rbac.json <<'EOF'
{"tokens": {"CHANGE-ME-viewer":   {"user": "vera",  "role": "viewer"},
            "CHANGE-ME-operator": {"user": "omar",  "role": "operator"},
            "CHANGE-ME-founder":  {"user": "akmal", "role": "founder"}}}
EOF
```

Keep this file out of the repo (tenant vault, ADR-0038 TN-5); rotate by
editing the file in place — the app re-reads it per request, no restart
needed. `$DASLAB_CP_RBAC` points the process at it. Fail-closed by
construction: unconfigured RBAC means every data/action endpoint answers 503
except `/healthz` and the data-free HTML shell.

This vault token map is distinct from — and layered on top of —
`config/rbac.yaml`'s principal-kind grants (section 3.4): the token map binds
a bearer token to a `{user, role}` pair for this one process; `config/rbac.yaml`
is the org-wide SSOT for what each principal kind may do (`gate.approve`,
`run.trigger`, `board.mutate.routing`, `audit.read`, `config.edit.security`).

### 3.3 Stand up the optional process (systemd or launchd), Founder opt-in only

Nothing in DasLab installs, enables, or starts either unit automatically —
both ship with a `.example` suffix precisely so no unit scanner picks them up
on their own.

**Linux (systemd)** — `tools/control_plane/install/systemd/daslab-control-plane.service.example`:

```bash
sudo cp tools/control_plane/install/systemd/daslab-control-plane.service.example \
  /etc/systemd/system/daslab-control-plane.service
sudo $EDITOR /etc/systemd/system/daslab-control-plane.service   # fill in real repo path + RBAC path
sudo systemctl daemon-reload
sudo systemctl enable --now daslab-control-plane   # explicit opt-in, not automatic
```

**macOS (launchd)** — `tools/control_plane/install/launchd/com.daslab.control-plane.plist.example`:

```bash
cp tools/control_plane/install/launchd/com.daslab.control-plane.plist.example \
  ~/Library/LaunchAgents/com.daslab.control-plane.plist
$EDITOR ~/Library/LaunchAgents/com.daslab.control-plane.plist   # fill in real repo path + RBAC path
launchctl load ~/Library/LaunchAgents/com.daslab.control-plane.plist
```

Both unit files bind to `--host 127.0.0.1` — **loopback by default**. Binding
to a tenant network interface is a separate, deliberate act (edit the unit's
`ExecStart`/`ProgramArguments` host argument) — never the default.

Ad-hoc foreground run (no persistent unit), same loopback-default posture —
see section 7 for the exact command.

### 3.4 Deploy `config/rbac.yaml` + the governance invariants

`config/rbac.yaml` is the org-wide RBAC SSOT (ADR-0038 TN-3 / FR-001) and
ships already in the repo, already governance-reviewed — this step is
confirming it is in force on the tenant, not authoring it fresh. Its two
load-bearing rows are Founder-identity only, enforced structurally
(`scripts/rbac.py` refuses to load any `rbac.yaml` that grants a
founder-only permission to a non-founder kind; `decide()` default-denies
anything not explicitly granted):

- `gate.approve` — closing a never-auto-approve AADL gate (QONUN-5
  categories: `new_goal`, `security_sensitive`, `schema_migration`,
  `gate5_deployment`, `governance_or_policy`, `permission_change`,
  `secret_change`).
- `run.trigger` — starting a headless run (ADR-0034).

A control-plane `agent:<role>` principal or the `orchestrator` mechanism
kind can never hold either permission — the exclusion is structural (no
role string, ticket field, or dashboard action promotes an agent into
`founder`). Concretely: **a control action never bypasses an AADL gate** — a
GATE-5-open deployment stays machine-blocked regardless of any dashboard
click.

### 3.5 Audit ledger

Every governed write (goal proposal, RBAC deny/allow, gate/trigger attempts)
is appended to `board/.control-plane-audit.jsonl`, redacted per ADR-0012. On
the tenant VM this file should be:

- owned by a **non-agent uid** (a human/service account distinct from any
  agent-run identity) — no agent process should hold write access to its own
  audit trail;
- readable by the `audit-team` principal kind (`audit.read: allow`,
  read-only — no approve/trigger/mutate), per `config/rbac.yaml`;
- included in the tenant's backup/retention plan (it is the evidentiary
  record for gate-approval and trigger events, not a scratch log).

## 4. Rollback

Rollback is symmetric with enable and is the cheap, default-safe direction:

1. **Flip `ws_h_control_plane` back to `false`** in `config/features.yaml`
   (or leave it — it ships `false`). `degrade.py`'s trigger 1 fires
   immediately on the next launch attempt: the surface degrades to the
   ADR-0028 static read cockpit, no server involved.
2. **Stop the optional process**, if one was ever started:
   - systemd: `sudo systemctl disable --now daslab-control-plane`
   - launchd: `launchctl unload ~/Library/LaunchAgents/com.daslab.control-plane.plist`
   - ad-hoc foreground run: Ctrl-C / kill the uvicorn process.
3. Either step alone is sufficient to remove the live control plane from the
   picture — the flag gates the intended surface, the process being stopped
   removes the running instance. Doing both is the clean state for a tenant
   that decides not to use WS-H at all.

No data migration, no schema rollback: all state is repo files (tickets
read-only; `board/goal-inbox/` + the audit ledger are the only writes), so
rollback never touches board-as-truth outside of ordinary git history.

## 5. FR-006 / CP-5 acceptance check (this ticket)

- `config/features.yaml` → `ws_h_control_plane: false` — confirmed at merge.
- The optional process is not default-enabled anywhere in the repo (no
  script installs/enables/starts the systemd or launchd unit; both ship as
  `.example`).
- Flag-off / process-absent surface is byte-identical to pre-merge: nothing
  in `tools/control_plane/` is imported by any core path (`app.py` and its
  install helpers are only ever invoked explicitly, never from
  `scripts/cockpit.py`, `scripts/diagnostics.py`, or dispatch code) — merging
  this runbook + the existing PoC code changes no dispatch behavior.
- WS-G PROOF "shipped" evidence (ADR-0037): this runbook + the flag-OFF
  merge is the documented deploy decision; the "deployed to tenant VM" leg of
  that proof is the Founder's enable act (section 3), performed later — not
  claimed as done here.

## 6. Definition of Done cross-reference (ADR-0039 CP-1…CP-6)

CP-1..CP-6 are honored as described in section 7 (`How the ADR-0039
invariants are honored`) below, plus the install/enable/degrade/rollback
detail in sections 1–4 above. CP-3b (trigger-run via the ADR-0034 runner) and
CP-3c (Founder-identity gate-approve bound to the real gate machinery) remain
explicitly out of scope for this PoC — tracked as follow-up tickets, not
silently assumed done.

---

## 7. What ships (PoC scope, spike record)

## What ships (PoC scope)

| File | Role |
| --- | --- |
| `tools/control_plane/app.py` | FastAPI app: RBAC auth (viewer < operator < founder), board read, **real cockpit embed**, audit tail, and the **one governed write** — submit a goal proposal |
| `tools/control_plane/requirements-control.txt` | Optional deps (`fastapi`, `uvicorn`) — kept OUT of core `requirements.txt` (CP-5: optional process, not core runtime) |
| `tests/test_ws_h_control_plane.py` | 7 tests: fail-closed, 401, RBAC deny/allow, goal file + audit, rank order, honest cockpit fallback, data-free HTML shell |

### 7.1 How the ADR-0039 invariants are honored

- **CP-1** `/api/cockpit` runs the **real** `scripts/cockpit.py` via its own CLI (its argparse owns the defaults) and embeds the text output; if unavailable it returns an honest NODATA line. No panel is re-implemented. *(Verified live: `source: scripts/cockpit.py` with real panels.)*
- **CP-2** every data/action endpoint needs `Authorization: Bearer <token>` → role from `$DASLAB_CP_RBAC`. **Fail-closed:** unconfigured RBAC ⇒ 503 for everything except `/healthz` and the data-free HTML shell.
- **CP-3 (a only)** the single write is **goal proposal → `board/goal-inbox/<ts>-<slug>.md`** (`status: proposed`, `source: control-plane`). It creates no ticket, approves nothing, dispatches nothing — the goal awaits Founder discovery + explicit approval via `/daslab-plan` (Founder-Approved Goal Queue law). Every request/decision is appended to `board/.control-plane-audit.jsonl`. *Follow-up tickets:* CP-3b trigger-run (needs the WS-B runner, ADR-0034) and CP-3c approve-gate (Founder-identity only; must bind to the real gate machinery — never a PoC stub).
- **CP-4** all state = repo files (tickets read; goal-inbox + audit written). No parallel store.
- **CP-5** the server dispatches nothing on its own; loopback bind by default (`DASLAB_CP_BIND` to change — a deliberate tenant act); run it under systemd/launchd only if the Founder opts in.
- **CP-6** stdlib + FastAPI only; no external SaaS; single-file HTML with inline CSS/JS, no CDN.

### 7.2 Run it (tenant server or laptop)

```bash
pip install -r tools/control_plane/requirements-control.txt
cat > /secure/rbac.json <<'EOF'
{"tokens": {"CHANGE-ME-viewer":   {"user": "vera",  "role": "viewer"},
            "CHANGE-ME-operator": {"user": "omar",  "role": "operator"},
            "CHANGE-ME-founder":  {"user": "akmal", "role": "founder"}}}
EOF
DASLAB_ROOT=/path/to/daslab DASLAB_CP_RBAC=/secure/rbac.json \
  python3 -m uvicorn tools.control_plane.app:app --host 127.0.0.1 --port 8899
# open http://127.0.0.1:8899  → paste a token → Load
```

Port 8899 (8787 is taken by the ArcRift claude-bridge). Tokens are secrets: keep the RBAC file out of the repo (tenant vault, ADR-0038 TN-5); rotate by editing the file — no restart needed (it is re-read per request).

**No internet on the target machine?** `tools/control_plane/.vendor/` ships an offline wheel bundle (fastapi/uvicorn + full dependency closure, arm64+cp310 — see below). Skip `pip install` and instead:

```bash
cd /path/to/daslab
export PYTHONPATH="$(pwd)/tools/control_plane/.vendor/site-packages"
DASLAB_ROOT=/path/to/daslab DASLAB_CP_RBAC=/secure/rbac.json \
  python3 -m uvicorn tools.control_plane.app:app --host 127.0.0.1 --port 8899
```

## 8. Offline install bundle spike details (`tools/control_plane/.vendor/`, added 2026-07-23)

Built once in a network-connected environment for the Founder's laptop (macOS arm64 → Cowork's Linux VM is `aarch64`, `cp310`):

```bash
pip download "fastapi>=0.110" "uvicorn>=0.29" \
  --platform manylinux2014_aarch64 --platform manylinux_2_17_aarch64 --platform manylinux_2_28_aarch64 \
  --python-version 3.10 --implementation cp --abi cp310 --only-binary=:all: \
  -d wheels/   # + exceptiongroup (anyio's py<3.11 marker isn't always resolved cross-platform — verify Requires-Dist by hand)
pip install --no-index --find-links=wheels --target=site-packages fastapi uvicorn
```

14 wheels, ~3 MB, all verified against the real `Requires-Dist` metadata (not just `pip`'s cross-platform resolution, which silently dropped `exceptiongroup` once — see below). `tools/control_plane/.vendor/` is gitignored: it is a machine-specific install cache, not source.

## 9. Attempted a live launch via the Cowork device bridge (2026-07-23) — result

Tried to start the server on the Founder's Mac through the remote device bridge (not a real Terminal) and leave it running for the browser. Verified real, non-fabricated signals along the way:

- The vendored wheels import clean on-device: `fastapi 0.139.2`, `uvicorn 0.51.0`, `starlette 1.3.1`, `pydantic 2.13.4` — proves the arm64/cp310 wheel bundle is correct for this machine.
- The real `app.py`, run against the real repo (not a synthetic fixture), booted and answered `GET /healthz` → `{"ok":true,"rbac_configured":true}`, confirmed both by the HTTP response and the server's own stdout log (`Uvicorn running on http://127.0.0.1:8899`, `"GET /healthz HTTP/1.1" 200 OK`).

**Hard limitation found:** the bridge cannot host a long-running process. Each remote command runs in its own sandboxed namespace (`bwrap --unshare-pid --die-with-parent`); backgrounding with `nohup`/`disown` does not survive it — the OS tears down every process in that namespace the instant the command finishes, confirmed empirically (server answered `/healthz` inside the launching call, then `Connection refused` on the very next call, with the uvicorn process gone from `ps` and no error in its log — i.e. reaped, not crashed). Files written during the call (the vendored wheels, this doc) persist fine; only backgrounded processes don't. There is no remaining workaround from this side that doesn't mean fighting the sandbox's process isolation, which is intentional and shouldn't be circumvented.

**Conclusion:** the deploy path is proven end-to-end and de-risked (no network needed anymore either), but actually *keeping the dashboard open* is a one-command step only the Founder can do, in a real Terminal on the Mac (or a proper background service — e.g. `launchd` — which also needs to be installed natively, not through this bridge):

```bash
cd ~/DasLab
export PYTHONPATH="$(pwd)/tools/control_plane/.vendor/site-packages"
cat > /tmp/daslab-cp-rbac.json <<'EOF'
{"tokens": {"CHANGE-ME-viewer":   {"user": "vera",  "role": "viewer"},
            "CHANGE-ME-operator": {"user": "omar",  "role": "operator"},
            "CHANGE-ME-founder":  {"user": "akmal", "role": "founder"}}}
EOF
DASLAB_ROOT="$(pwd)" DASLAB_CP_RBAC=/tmp/daslab-cp-rbac.json \
  python3 -m uvicorn tools.control_plane.app:app --host 127.0.0.1 --port 8899
# then open http://127.0.0.1:8899 in the browser and paste a token
```

## 10. Verified (container, 2026-07-23)

`ruff` clean · `pytest` **7/7** · live smoke: `/healthz` ok · no token → **401** · viewer reads board (counts correct) · viewer POST goal → **403** (audited deny) · operator POST goal → **201**, file in `board/goal-inbox/` with `status: proposed`, audited allow · founder reads audit · HTML shell leaks no data · `/api/cockpit` → **real cockpit output** (`source: scripts/cockpit.py`) once `scripts/` deps present, honest NODATA otherwise.

## 11. Definition of Done (WS-H, spike-era note — superseded by sections 5–6)

PoC covered: RBAC + audit + board/cockpit read + CP-3a. What was open at spike
time — feature-flag key in `config/features.yaml` (now present, OFF),
systemd/launchd unit examples (now present under `tools/control_plane/install/`),
and the ADR-0039 review against CP-1…CP-6 (now sections 1–6 above) — is closed
by this ticket (DAS-1604). Still deliberately deferred: CP-3b (trigger run via
ADR-0034 runner), CP-3c (Founder-identity gate approval bound to real gate
machinery). Also open: give the device bridge (or an equivalent) a real
persistent-process story if remote-launched dashboards become a recurring
need — today it's single-command-in-a-real-terminal (or the opt-in
systemd/launchd unit) only.
