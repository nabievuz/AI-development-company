
from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(_REPO_ROOT / "scripts"))

import pytest
from artifact_schemas import (
    ALLOWED_FIELD_TYPES,
    SchemaError,
    available_schema_names,
    load_schema_file,
    schema_path,
    schema_registry,
)

_VALID = """\
name: {name}
version: 1
description: A valid artifact for tests.
fields:
  - name: run_id
    type: string
    required: true
    description: an id
  - name: count
    type: integer
"""


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / f"{name}.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_load_valid_schema(tmp_path: Path) -> None:
    p = _write(tmp_path, "alpha", _VALID.format(name="alpha"))
    schema = load_schema_file(p)
    assert schema.name == "alpha"
    assert schema.version == 1
    assert [f.name for f in schema.fields] == ["run_id", "count"]
    assert schema.fields[0].required is True
    assert schema.fields[1].required is False


def test_shipped_example_schemas_are_valid() -> None:
    schemas_dir = _REPO_ROOT / "governance" / "schemas"
    names = available_schema_names(schemas_dir)
    assert {"task-ledger", "typed-contracts"} <= names


def test_default_field_types_cover_json_kinds() -> None:
    assert {"string", "integer", "number", "boolean", "object", "array"} == set(
        ALLOWED_FIELD_TYPES
    )


def test_unknown_field_type_fails(tmp_path: Path) -> None:
    text = _VALID.format(name="beta").replace("type: string", "type: bogus")
    p = _write(tmp_path, "beta", text)
    with pytest.raises(SchemaError):
        load_schema_file(p)


def test_missing_name_fails(tmp_path: Path) -> None:
    text = "version: 1\ndescription: no name\nfields:\n  - name: x\n    type: string\n"
    p = _write(tmp_path, "gamma", text)
    with pytest.raises(SchemaError):
        load_schema_file(p)


def test_missing_description_fails(tmp_path: Path) -> None:
    text = "name: delta\nfields:\n  - name: x\n    type: string\n"
    p = _write(tmp_path, "delta", text)
    with pytest.raises(SchemaError):
        load_schema_file(p)


def test_empty_fields_list_fails(tmp_path: Path) -> None:
    text = "name: epsilon\ndescription: has no fields\nfields: []\n"
    p = _write(tmp_path, "epsilon", text)
    with pytest.raises(SchemaError):
        load_schema_file(p)


def test_name_must_equal_file_stem(tmp_path: Path) -> None:

    p = _write(tmp_path, "zeta", _VALID.format(name="other"))
    with pytest.raises(SchemaError):
        load_schema_file(p)


def test_non_mapping_top_level_fails(tmp_path: Path) -> None:
    p = _write(tmp_path, "eta", "- just\n- a\n- list\n")
    with pytest.raises(SchemaError):
        load_schema_file(p)


def test_invalid_yaml_fails(tmp_path: Path) -> None:
    p = _write(tmp_path, "theta", "name: theta\n  bad: : indent\n:::\n")
    with pytest.raises(SchemaError):
        load_schema_file(p)


def test_version_below_one_fails(tmp_path: Path) -> None:
    text = _VALID.format(name="iota").replace("version: 1", "version: 0")
    p = _write(tmp_path, "iota", text)
    with pytest.raises(SchemaError):
        load_schema_file(p)


def test_registry_skips_malformed(tmp_path: Path) -> None:
    _write(tmp_path, "good", _VALID.format(name="good"))
    _write(tmp_path, "broken", "name: broken\n")
    names = available_schema_names(tmp_path)
    assert names == {"good"}
    reg = schema_registry(tmp_path)
    assert set(reg) == {"good"}
    assert reg["good"].name == "good"


def test_schema_path_resolves_name(tmp_path: Path) -> None:
    assert schema_path("foo", tmp_path) == tmp_path / "foo.yaml"


def test_missing_dir_returns_empty(tmp_path: Path) -> None:
    missing = tmp_path / "nope"
    assert available_schema_names(missing) == set()
    assert schema_registry(missing) == {}
