from __future__ import annotations

import hmac
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CREDENTIALS_PATH = ROOT / "config" / "a2a_credentials.yaml"

PLACEHOLDER_PRINCIPALS: frozenset[str] = frozenset(
    {"", "anonymous", "unknown", "none", "null", "nobody", "-"}
)

MIN_CREDENTIAL_CHARS = 24


class CredentialConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class CredentialRecord:

    credential_id: str
    principal_id: str
    secret: str


@dataclass(frozen=True)
class CallerIdentity:

    principal_id: str
    verified: bool
    credential_id: str = ""

    @property
    def kind(self) -> str:
        return "verified" if self.verified else "unverified"


def _as_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def parse_credential_registry(data: Any, *, origin: str) -> tuple[CredentialRecord, ...]:
    if data is None:
        return ()
    if not isinstance(data, dict):
        raise CredentialConfigError(f"{origin}: expected a mapping at the top level")
    entries = data.get("credentials")
    if entries is None:
        return ()
    if not isinstance(entries, list):
        raise CredentialConfigError(f"{origin}: 'credentials' must be a list")

    records: list[CredentialRecord] = []
    seen_ids: set[str] = set()
    for index, entry in enumerate(entries):
        where = f"{origin}: credentials[{index}]"
        if not isinstance(entry, dict):
            raise CredentialConfigError(f"{where} is not a mapping")
        credential_id = _as_text(entry.get("credential_id")).strip()
        principal_id = _as_text(entry.get("principal")).strip()
        secret = _as_text(entry.get("secret"))
        if not credential_id:
            raise CredentialConfigError(f"{where} has no credential_id")
        if credential_id in seen_ids:
            raise CredentialConfigError(f"{where} repeats credential_id {credential_id!r}")
        seen_ids.add(credential_id)
        if not principal_id or principal_id.lower() in PLACEHOLDER_PRINCIPALS:
            raise CredentialConfigError(
                f"{where} has no usable principal — a credential must name the "
                "identity it authenticates"
            )
        if len(secret.strip()) < MIN_CREDENTIAL_CHARS:
            raise CredentialConfigError(
                f"{where} secret is shorter than {MIN_CREDENTIAL_CHARS} characters"
            )
        records.append(
            CredentialRecord(
                credential_id=credential_id, principal_id=principal_id, secret=secret
            )
        )
    return tuple(records)


def load_credential_registry(path: Path | None = None) -> tuple[CredentialRecord, ...]:
    target = Path(path) if path is not None else DEFAULT_CREDENTIALS_PATH
    if not target.is_file():
        return ()
    try:
        import yaml
    except ImportError as exc:
        raise CredentialConfigError(
            f"cannot read {target}: PyYAML is not installed, so credentials "
            "cannot be verified and the endpoint fails closed"
        ) from exc
    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CredentialConfigError(f"cannot read {target}: {exc}") from exc
    return parse_credential_registry(data, origin=str(target))


def match_credential(
    presented: Any, registry: tuple[CredentialRecord, ...]
) -> CredentialRecord | None:
    if not isinstance(presented, str):
        return None
    offered = presented.strip().encode("utf-8", "surrogatepass")
    if not offered:
        return None
    matched: CredentialRecord | None = None
    for record in registry:
        expected = record.secret.strip().encode("utf-8", "surrogatepass")
        if hmac.compare_digest(offered, expected):
            matched = record
    return matched


def strip_bearer_prefix(presented: Any) -> str:
    text = presented if isinstance(presented, str) else ""
    stripped = text.strip()
    scheme, separator, rest = stripped.partition(" ")
    if separator and scheme.lower() == "bearer":
        return rest.strip()
    return stripped


def resolve_caller_identity(
    *,
    credential: Any,
    claimed_principal: Any,
    registry: tuple[CredentialRecord, ...],
) -> tuple[CallerIdentity | None, str]:
    if registry:
        offered = strip_bearer_prefix(credential)
        if not offered:
            return None, (
                "REFUSED: no credential presented — the A2A endpoint has a "
                "credential registry configured, so the caller-supplied principal "
                "is never accepted as an identity"
            )
        record = match_credential(offered, registry)
        if record is None:
            return None, (
                "REFUSED: the presented credential is not in the A2A credential "
                "registry — identity cannot be established"
            )
        return (
            CallerIdentity(
                principal_id=record.principal_id,
                verified=True,
                credential_id=record.credential_id,
            ),
            (
                f"identity {record.principal_id!r} derived from verified credential "
                f"{record.credential_id!r}; any caller-supplied principal was ignored"
            ),
        )

    claimed = str(claimed_principal or "").strip()
    if not claimed or claimed.lower() in PLACEHOLDER_PRINCIPALS:
        return None, (
            "REFUSED: no caller identity — no credential registry is configured "
            "and the caller supplied no usable principal"
        )
    return (
        CallerIdentity(principal_id=claimed, verified=False, credential_id=""),
        (
            f"identity {claimed!r} is UNVERIFIED: no credential registry is "
            f"configured at {DEFAULT_CREDENTIALS_PATH.name}, so the caller-supplied "
            "principal is taken at face value and charged the unverified quota"
        ),
    )
