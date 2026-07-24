# Runbook — WS-H: self-hosted web control plane PoC (ADR-0039)

**Goal (MUSTAQIL WS-H):** operate DasLab from a browser on the tenant's own Ubuntu/macOS server — see the board and the real cockpit, and perform governed, audited actions — without breaking board-as-truth, never-auto-approve, or NOT-a-daemon.

## What ships (PoC scope)

| File | Role |
| --- | --- |
| `tools/control_plane/app.py` | FastAPI app: RBAC auth (viewer < operator < founder), board read, **real cockpit embed**, audit tail, and the **one governed write** — submit a goal proposal |
| `tools/control_plane/requirements-control.txt` | Optional deps (`fastapi`, `uvicorn`) — kept OUT of core `requirements.txt` (CP-5: optional process, not core runtime) |
| `tests/test_ws_h_control_plane.py` | 7 tests: fail-closed, 401, RBAC deny/allow, goal file + audit, rank order, honest cockpit fallback, data-free HTML shell |

## How the ADR-0039 invariants are honored

- **CP-1** `/api/cockpit` runs the **real** `scripts/cockpit.py` via its own CLI (its argparse owns the defaults) and embeds the text output; if unavailable it returns an honest NODATA line. No panel is re-implemented. *(Verified live: `source: scripts/cockpit.py` with real panels.)*
- **CP-2** every data/action endpoint needs `Authorization: Bearer <token>` → role from `$DASLAB_CP_RBAC`. **Fail-closed:** unconfigured RBAC ⇒ 503 for everything except `/healthz` and the data-free HTML shell.
- **CP-3 (a only)** the single write is **goal proposal → `board/goal-inbox/<ts>-<slug>.md`** (`status: proposed`, `source: control-plane`). It creates no ticket, approves nothing, dispatches nothing — the goal awaits Founder discovery + explicit approval via `/daslab-plan` (Founder-Approved Goal Queue law). Every request/decision is appended to `board/.control-plane-audit.jsonl`. *Follow-up tickets:* CP-3b trigger-run (needs the WS-B runner, ADR-0034) and CP-3c approve-gate (Founder-identity only; must bind to the real gate machinery — never a PoC stub).
- **CP-4** all state = repo files (tickets read; goal-inbox + audit written). No parallel store.
- **CP-5** the server dispatches nothing on its own; loopback bind by default (`DASLAB_CP_BIND` to change — a deliberate tenant act); run it under systemd/launchd only if the Founder opts in.
- **CP-6** stdlib + FastAPI only; no external SaaS; single-file HTML with inline CSS/JS, no CDN.

## Run it (tenant server or laptop)

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

## Offline install bundle (`tools/control_plane/.vendor/`, added 2026-07-23)

Built once in a network-connected environment for the Founder's laptop (macOS arm64 → Cowork's Linux VM is `aarch64`, `cp310`):

```bash
pip download "fastapi>=0.110" "uvicorn>=0.29" \
  --platform manylinux2014_aarch64 --platform manylinux_2_17_aarch64 --platform manylinux_2_28_aarch64 \
  --python-version 3.10 --implementation cp --abi cp310 --only-binary=:all: \
  -d wheels/   # + exceptiongroup (anyio's py<3.11 marker isn't always resolved cross-platform — verify Requires-Dist by hand)
pip install --no-index --find-links=wheels --target=site-packages fastapi uvicorn
```

14 wheels, ~3 MB, all verified against the real `Requires-Dist` metadata (not just `pip`'s cross-platform resolution, which silently dropped `exceptiongroup` once — see below). `tools/control_plane/.vendor/` is gitignored: it is a machine-specific install cache, not source.

## Attempted a live launch via the Cowork device bridge (2026-07-23) — result

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

## Verified (container, 2026-07-23)

`ruff` clean · `pytest` **7/7** · live smoke: `/healthz` ok · no token → **401** · viewer reads board (counts correct) · viewer POST goal → **403** (audited deny) · operator POST goal → **201**, file in `board/goal-inbox/` with `status: proposed`, audited allow · founder reads audit · HTML shell leaks no data · `/api/cockpit` → **real cockpit output** (`source: scripts/cockpit.py`) once `scripts/` deps present, honest NODATA otherwise.

## Definition of Done (WS-H, toward the ADR-0039 gate)

PoC covers: RBAC + audit + board/cockpit read + CP-3a. Remaining for the full WS-H DoD: CP-3b (trigger run via ADR-0034 runner), CP-3c (Founder-identity gate approval bound to real gate machinery), feature-flag key in `config/features.yaml` (OFF), systemd unit example, and the ADR-0039 review against CP-1…CP-6. Also open: give the device bridge (or an equivalent) a real persistent-process story if remote-launched dashboards become a recurring need — today it's single-command-in-a-real-terminal only.
