from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

pytest.importorskip("alembic")
pytest.importorskip("sqlalchemy")

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


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
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute("PRAGMA foreign_key_list(facts)").fetchall()
        return rows[0][6] if rows else None
    finally:
        con.close()


@pytest.fixture()
def shadow_db(tmp_path):
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
    assert _columns(shadow_db) == _BASELINE_COLUMNS
    command.upgrade(_cfg(shadow_db), "head")
    cols = _columns(shadow_db)
    assert "trust_score" in cols and "ttl" in cols

    con = sqlite3.connect(shadow_db)
    try:
        row = con.execute(
            "SELECT subject, relation, object, trust_score, ttl FROM facts"
        ).fetchone()
    finally:
        con.close()
    assert row == ("daslab", "uses", "arcrift", 0.5, None)


def test_upgrade_preserves_indexes_and_fk(shadow_db):
    command.upgrade(_cfg(shadow_db), "head")
    assert _indexes(shadow_db) >= _BASELINE_INDEXES
    assert _fk_on_delete(shadow_db) == "CASCADE"


def test_downgrade_is_reversible_rollback_drill(shadow_db):
    command.upgrade(_cfg(shadow_db), "head")
    assert {"trust_score", "ttl"} <= _columns(shadow_db)
    command.downgrade(_cfg(shadow_db), "base")
    cols = _columns(shadow_db)
    assert "trust_score" not in cols and "ttl" not in cols


    assert cols == _BASELINE_COLUMNS
    assert _indexes(shadow_db) >= _BASELINE_INDEXES
    assert _fk_on_delete(shadow_db) == "CASCADE"
    assert _fact_count(shadow_db) == 1


def test_downgrade_preserves_autoincrement_pk(shadow_db):
    command.upgrade(_cfg(shadow_db), "head")
    command.downgrade(_cfg(shadow_db), "base")
    con = sqlite3.connect(shadow_db)
    try:
        ddl = con.execute("SELECT sql FROM sqlite_master WHERE name='facts'").fetchone()[0]
        assert "AUTOINCREMENT" in ddl.upper()

        con.execute("INSERT INTO facts (sessionId, subject, relation, object) VALUES ('s','a','r','b')")
        con.execute("INSERT INTO facts (sessionId, subject, relation, object) VALUES ('s','a','r','c')")
        con.commit()
        max_id = con.execute("SELECT MAX(id) FROM facts").fetchone()[0]
        con.execute("DELETE FROM facts WHERE id = ?", (max_id,))
        con.execute("INSERT INTO facts (sessionId, subject, relation, object) VALUES ('s','a','r','d')")
        con.commit()
        new_id = con.execute("SELECT id FROM facts WHERE object = 'd'").fetchone()[0]
        assert new_id > max_id
    finally:
        con.close()


def test_migration_chain_is_single_and_reversible():
    from alembic.script import ScriptDirectory

    script = ScriptDirectory.from_config(_cfg(ROOT / "_unused.db"))
    revs = list(script.walk_revisions())
    assert len(revs) == 1
    assert revs[0].down_revision is None
    assert revs[0].revision == "0001_trust_score_ttl"
