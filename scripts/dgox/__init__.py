"""DGO-X control-plane package — DasLab Tier-B (v2.0.0).

Phase 1 implements the graph_state typed schema (state.py) and the append-only
event store (events.py, DAS-1377) in SHADOW mode: state is mirrored and events
are emitted, but NO dispatch behaviour is changed.  /daslab-cycle is unaffected.

See ADR 0010 (adopt DGO-X) and ADR 0011 (Phase-1 data contracts) for the
authoritative design decisions this package builds against.
"""
