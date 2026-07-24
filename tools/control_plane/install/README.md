# WS-H control-plane install path (DAS-1602, ADR-0039 CP-5/CP-6, SPEC-008 FR-006/FR-008)

This directory is the **install-path decision layer** for the optional WS-H
control plane. It does not own `tools/control_plane/app.py` (DAS-1600/1601) —
it owns two things:

1. **Offline install (FR-008 / CP-6).** Build and verify a vendored-wheel
   dependency closure so a no-network in-tenant server can install and boot
   the control plane without reaching any package index.
2. **Degrade-to-static (FR-006 / CP-5).** Decide, on every launch attempt,
   whether the control plane is eligible to run or the surface degrades to
   the ADR-0028 static read cockpit — the always-available base case.

## Files

| File | Role |
| --- | --- |
| `build_offline_bundle.py` | Builds the two-phase pip recipe (`pip download` on a network host, `pip install --no-index --target=` on the offline target). `plan()`/`build(dry_run=True)` never touch the network or the filesystem — pure planning. |
| `verify_closure.py` | Verifies a built bundle's REAL `Requires-Dist` closure (zipfile + `email` header parsing, no import, no pip) — catches the class of gap where pip's cross-platform resolver silently drops a marker-gated dependency (`exceptiongroup`). |
| `degrade.py` | The NOT-a-daemon routing decision: flag OFF, or optional deps not importable, or `--force-static` ⇒ degrade to the ADR-0028 static cockpit (via `scripts/cockpit_html.py`, subprocess, no re-implemented panel). Otherwise reports the control plane eligible — it never execs uvicorn itself. |
| `systemd/daslab-control-plane.service.example` | Opt-in systemd unit example (Linux tenant). `.example` suffix so no scanner picks it up automatically; Founder copies + edits + enables it deliberately. |
| `launchd/com.daslab.control-plane.plist.example` | Opt-in launchd unit example (macOS tenant), same opt-in posture. |

## Why a distinct zone from `app.py`

`zone: tools/control_plane/install` (this ticket, DAS-1602) is intentionally
separate from `tools/control_plane` root (DAS-1600/1601's `app.py` hardening)
so the two can proceed in the same wave without a merge collision. Neither
`app.py`, `requirements-control.txt`, nor any script outside this directory is
touched here.

## Build the offline bundle (network-connected build host, once)

```bash
python3 tools/control_plane/install/build_offline_bundle.py \
  --wheels-dir tools/control_plane/.vendor/wheels \
  --site-packages-dir tools/control_plane/.vendor/site-packages
# prints the two pip commands and runs them (omit --dry-run to execute)
```

Then verify the closure against the REAL `Requires-Dist` graph, not just
"pip said so":

```bash
python3 tools/control_plane/install/verify_closure.py \
  --wheels-dir tools/control_plane/.vendor/wheels fastapi uvicorn
# [verify-closure] OK — full closure present
```

`tools/control_plane/.vendor/` is gitignored — it is a machine-specific
install cache. The tracked artifacts are this recipe plus
`tools/control_plane/requirements-control.txt` (the closure input, owned
outside this zone).

## Boot with no network (offline target)

```bash
cd /path/to/daslab
export PYTHONPATH="$(pwd)/tools/control_plane/.vendor/site-packages"
DASLAB_ROOT="$(pwd)" DASLAB_CP_RBAC=/secure/rbac.json \
  python3 -m uvicorn tools.control_plane.app:app --host 127.0.0.1 --port 8899
```

No `pip install`, no package-index fetch — `--no-index` was already used to
populate `site-packages/` on the build host; the offline target only needs the
copied directory on `PYTHONPATH`.

## Degrade-to-static

```bash
python3 tools/control_plane/install/degrade.py
```

With `ws_h_control_plane` OFF in `config/features.yaml` (the shipped default),
or with fastapi/uvicorn not importable, this renders the ADR-0028 static read
cockpit (`board/.cockpit.html`) and exits — no server is started, nothing is
dispatched. This is the **ordinary** path, exercised on every flag-OFF run, not
an emergency fallback (ADR-0028 D-1 / D-5).

## Optional, Founder-enabled process — never installed automatically

Neither this directory nor any DasLab script installs, enables, or starts the
`systemd`/`launchd` unit. The `.example` file suffix is deliberate: standing up
a persistent process is always a Founder act, performed on the real tenant
machine.
