"""DasLab WS-D LENS — read-side observability adapter (ADR-0036 / DAS-1573).

Non-invasive, flag-gated (``ws_d_langfuse_lens``, OFF by default). Reads the
already-emitted ADR-0024 span stream, redacts it (ADR-0012), maps it to OTLP and
ships it to a self-host Langfuse — never wired into the dispatch/write path.
"""
