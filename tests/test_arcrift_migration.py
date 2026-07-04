"""test_arcrift_migration.py — shadow-SQLite validation of the ArcRift trust_score/ttl
migration (E-004 R-13 / ADR-010).

This is Prisma's shadow-database discipline AND the ADR-005 rollback drill, run against a
DISPOSABLE SQLite file in a temp dir — it never touches the live ~/ArcRift database. It is
skipped when Alembic is absent (local dev) and runs in CI (requirements-dev.txt installs it).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("alembic")
pytest.importorskip("sqlalchemy")

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"

# ArcRift's `facts` table exactly as the live backend creates it
# (backend/src/services/sqlite.ts), INCLUDING its FK + both indexes — the migration ADDS
# columns to this pre-existing table, so the shadow DB must start from a FAITHFUL baseline.
# The UNIQUE index (idx_facts_unique) is a correctness constraint (no duplicate facts) and
# the FK is referential integrity; a downgrade that silently dropped either would be a real
# defect, so the round-trip asserts both survive.
_BASELINE_COLUMNS = {
    "id", "sessionId", "subject", "subjectType",
    "relation", "object", "objectType", "timestamp",
}
_BASELINE_INDEXES = {"idx_facts_session", "idx_facts_unique"}
_FACTS_BASELINE = """
CREATE TABLE sessions (id TEXT PRIMARY KEY);
CREATE TABLE facts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  sessionId TEXT NOT NULL,
  subject TEXT NOT NULL,
  subjectType TEXT,
  relation TEXT NOT NULL,
  object TEXT NOT NULL,
  objectType TEXT,
  timestamp TEXT,
  FOREIGN KEY(sessionId) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX idx_facts_session ON facts(sessionId);
CREATE UNIQUE INDEX idx_facts_unique ON facts(sessionId, subject, relation, object);
"""


def _cfg(db_path: Path) -> Config:
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def _columns(db_path: Path) -> set:
    con = sqlite3.connect(db_path)
    try:
        return {row[1] for row in con.execute("PRAGMA table_info(facts)")}
    finally:
        con.close()


def _fact_count(db_path: Path) -> int:
    con = sqlite3.connect(db_path)
    try:
        return con.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
    finally:
        con.close()


def _indexes(db_path: Path) -> set:
    con = sqlite3.connect(db_path)
    try:
        return {row[1] for row in con.execute("PRAGMA index_list(facts)")}
    finally:
        con.close()


def _fk_on_delete(db_path: Path) -> str | None:
    """The ON DELETE action of the facts->sessions FK (None if the FK is absent).
    Reflection should preserve CASCADE through the batch rebuild — a lost CASCADE would
    orphan facts when a session is deleted, so the round-trip asserts it survives."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("PRAGMA foreign_key_list(facts)").fetchall()
        return rows[0][6] if rows else None
    finally:
        con.close()


@pytest.fixture()
def shadow_db(tmp_path):
    """A disposable SQLite seeded with ArcRift's pre-migration facts table + one row."""
    db = tmp_path / "shadow_arcrift.db"
    con = sqlite3.connect(db)
    try:
        con.executescript(_FACTS_BASELINE)
        con.execute(
            "INSERT INTO facts (sessionId, subject, relation, object) VALUES (?,?,?,?)",
            ("sess-1", "daslab", "uses", "arcrift"),
        )
        con.commit()
    finally:
        con.close()
    return db


def test_upgrade_adds_trust_score_and_ttl_without_data_loss(shadow_db):
    assert _columns(shadow_db) == _BASELINE_COLUMNS  # baseline before the migration
    command.upgrade(_cfg(shadow_db), "head")
    cols = _columns(shadow_db)
    assert "trust_score" in cols and "ttl" in cols
    # additive => no data loss: the seeded fact survives with the neutral default + NULL ttl
    con = sqlite3.connect(shadow_db)
    try:
        row = con.execute(
            "SELECT subject, relation, object, trust_score, ttl FROM facts"
        ).fetchone()
    finally:
        con.close()
    assert row == ("daslab", "uses", "arcrift", 0.5, None)


def test_upgrade_preserves_indexes_and_fk(shadow_db):
    """Adding columns must not disturb the UNIQUE constraint (no duplicate facts) or the FK."""
    command.upgrade(_cfg(shadow_db), "head")
    assert _indexes(shadow_db) >= _BASELINE_INDEXES
    assert _fk_on_delete(shadow_db) == "CASCADE"


def test_downgrade_is_reversible_rollback_drill(shadow_db):
    command.upgrade(_cfg(shadow_db), "head")
    assert {"trust_score", "ttl"} <= _columns(shadow_db)
    command.downgrade(_cfg(shadow_db), "base")  # the ADR-005 rollback drill
    cols = _columns(shadow_db)
    assert "trust_score" not in cols and "ttl" not in cols
    # rollback drops the two columns but preserves the original schema, indexes, FK + rows —
    # batch_alter_table recreates the table, so this guards against silent index/FK loss.
    assert cols == _BASELINE_COLUMNS
    assert _indexes(shadow_db) >= _BASELINE_INDEXES
    assert _fk_on_delete(shadow_db) == "CASCADE"  # FK + its CASCADE action survive the rebuild
    assert _fact_count(shadow_db) == 1


def test_downgrade_preserves_autoincrement_pk(shadow_db):
    """The batch rebuild in downgrade() must keep `facts.id` AUTOINCREMENT. SQLAlchemy
    reflection silently drops the keyword, degrading the PK to a plain rowid that REUSES a
    freed max id after delete+insert — so an external fact-id reference could rebind to a
    different fact once the Founder runs the rollback drill on the live DB."""
    command.upgrade(_cfg(shadow_db), "head")
    command.downgrade(_cfg(shadow_db), "base")
    con = sqlite3.connect(shadow_db)
    try:
        ddl = con.execute("SELECT sql FROM sqlite_master WHERE name='facts'").fetchone()[0]
        assert "AUTOINCREMENT" in ddl.upper()
        # behavioral proof: a deleted max id is NOT reused (true AUTOINCREMENT, not rowid).
        con.execute("INSERT INTO facts (sessionId, subject, relation, object) VALUES ('s','a','r','b')")
        con.execute("INSERT INTO facts (sessionId, subject, relation, object) VALUES ('s','a','r','c')")
        con.commit()
        max_id = con.execute("SELECT MAX(id) FROM facts").fetchone()[0]
        con.execute("DELETE FROM facts WHERE id = ?", (max_id,))
        con.execute("INSERT INTO facts (sessionId, subject, relation, object) VALUES ('s','a','r','d')")
        con.commit()
        new_id = con.execute("SELECT id FROM facts WHERE object = 'd'").fetchone()[0]
        assert new_id > max_id  # monotonic; a plain-rowid PK would have reused max_id
    finally:
        con.close()


def test_migration_chain_is_single_and_reversible():
    """The migration is the first/only revision and declares a working down_revision=None."""
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_cfg(ROOT / "_unused.db"))
    revs = list(script.walk_revisions())
    assert len(revs) == 1
    assert revs[0].down_revision is None
    assert revs[0].revision == "0001_trust_score_ttl"
