#!/usr/bin/env python3


from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from _paths import ROOT


ALLOWED_FIELD_TYPES = frozenset(
    {"string", "integer", "number", "boolean", "object", "array"}
)


DEFAULT_SCHEMAS_DIR = ROOT / "governance" / "schemas"


class SchemaError(Exception):
    pass


try:
    from pydantic import BaseModel, ValidationError, field_validator

    HAVE_PYDANTIC = True
except ImportError:
    HAVE_PYDANTIC = False


if HAVE_PYDANTIC:

    class ArtifactField(BaseModel):

        name: str
        type: str
        required: bool = False
        description: str = ""

        @field_validator("name")
        @classmethod
        def _name_nonempty(cls, v: str) -> str:
            if not v or not v.strip():
                raise ValueError("field name must be non-empty")
            return v

        @field_validator("type")
        @classmethod
        def _type_known(cls, v: str) -> str:
            if v not in ALLOWED_FIELD_TYPES:
                raise ValueError(
                    f"unknown field type {v!r}; allowed: {sorted(ALLOWED_FIELD_TYPES)}"
                )
            return v

    class ArtifactSchema(BaseModel):

        name: str
        version: int = 1
        description: str
        fields: list[ArtifactField]

        @field_validator("name", "description")
        @classmethod
        def _nonempty(cls, v: str) -> str:
            if not v or not v.strip():
                raise ValueError("must be non-empty")
            return v

        @field_validator("version")
        @classmethod
        def _version_positive(cls, v: int) -> int:
            if v < 1:
                raise ValueError("version must be >= 1")
            return v

        @field_validator("fields")
        @classmethod
        def _fields_nonempty(cls, v: list) -> list:
            if not v:
                raise ValueError("fields must be a non-empty list")
            return v

    def _build_schema(data: dict, source: str) -> ArtifactSchema:
        try:
            return ArtifactSchema(**data)
        except ValidationError as exc:
            raise SchemaError(f"{source}: {exc}") from exc

else:


    @dataclass
    class ArtifactField:

        name: str
        type: str
        required: bool = False
        description: str = ""

    @dataclass
    class ArtifactSchema:

        name: str
        description: str
        fields: list[ArtifactField]
        version: int = 1

    def _require_str(data: dict, key: str, source: str) -> str:
        if key not in data:
            raise SchemaError(f"{source}: missing required key '{key}'")
        val = data[key]
        if not isinstance(val, str) or not val.strip():
            raise SchemaError(f"{source}: '{key}' must be a non-empty string")
        return val

    def _build_field(raw: object, source: str) -> ArtifactField:
        if not isinstance(raw, dict):
            raise SchemaError(f"{source}: each field must be a mapping")
        name = _require_str(raw, "name", source)
        ftype = _require_str(raw, "type", source)
        if ftype not in ALLOWED_FIELD_TYPES:
            raise SchemaError(
                f"{source}: field '{name}' has unknown type {ftype!r}; "
                f"allowed: {sorted(ALLOWED_FIELD_TYPES)}"
            )
        required = raw.get("required", False)
        if not isinstance(required, bool):
            raise SchemaError(f"{source}: field '{name}' 'required' must be a bool")
        description = raw.get("description", "")
        if not isinstance(description, str):
            raise SchemaError(f"{source}: field '{name}' 'description' must be a string")
        return ArtifactField(
            name=name, type=ftype, required=required, description=description
        )

    def _build_schema(data: dict, source: str) -> ArtifactSchema:
        name = _require_str(data, "name", source)
        description = _require_str(data, "description", source)
        version = data.get("version", 1)
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise SchemaError(f"{source}: 'version' must be an int >= 1")
        raw_fields = data.get("fields")
        if not isinstance(raw_fields, list) or not raw_fields:
            raise SchemaError(f"{source}: 'fields' must be a non-empty list")
        fields = [_build_field(rf, source) for rf in raw_fields]
        return ArtifactSchema(
            name=name, description=description, fields=fields, version=version
        )


def load_schema_file(path: Path) -> ArtifactSchema:
    source = path.name
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SchemaError(f"{source}: cannot read file: {exc}") from exc
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SchemaError(f"{source}: invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise SchemaError(f"{source}: top level must be a mapping")
    schema = _build_schema(data, source)
    if schema.name != path.stem:
        raise SchemaError(
            f"{source}: schema name '{schema.name}' must equal the file stem "
            f"'{path.stem}' (the name is the registry key)"
        )
    return schema


def schema_path(name: str, schemas_dir: Path | None = None) -> Path:
    base = schemas_dir if schemas_dir is not None else DEFAULT_SCHEMAS_DIR
    return base / f"{name}.yaml"


def available_schema_names(schemas_dir: Path | None = None) -> set[str]:
    base = schemas_dir if schemas_dir is not None else DEFAULT_SCHEMAS_DIR
    names: set[str] = set()
    if not base.is_dir():
        return names
    for p in sorted(base.glob("*.yaml")):
        try:
            names.add(load_schema_file(p).name)
        except SchemaError:
            continue
    return names


def schema_registry(schemas_dir: Path | None = None) -> dict[str, ArtifactSchema]:
    base = schemas_dir if schemas_dir is not None else DEFAULT_SCHEMAS_DIR
    registry: dict[str, ArtifactSchema] = {}
    if not base.is_dir():
        return registry
    for p in sorted(base.glob("*.yaml")):
        try:
            schema = load_schema_file(p)
        except SchemaError:
            continue
        registry[schema.name] = schema
    return registry


__all__ = [
    "ALLOWED_FIELD_TYPES",
    "DEFAULT_SCHEMAS_DIR",
    "HAVE_PYDANTIC",
    "ArtifactField",
    "ArtifactSchema",
    "SchemaError",
    "available_schema_names",
    "load_schema_file",
    "schema_path",
    "schema_registry",
]
