import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft7Validator, FormatChecker

from app.core.exceptions import AppError

SPEC = json.loads((Path(__file__).parents[2] / "data/openapi.json").read_text())


def compatible(value):
    if isinstance(value, list):
        return [compatible(v) for v in value]
    if isinstance(value, dict):
        value = {k: compatible(v) for k, v in value.items()}
        if value.pop("nullable", False) and "type" in value:
            value["type"] = [value["type"], "null"]
        return value
    return value


VALIDATION = compatible(SPEC)


def validate(value, schema):
    full_schema = {"components": VALIDATION["components"], **compatible(deepcopy(schema))}
    errors = sorted(
        Draft7Validator(full_schema, format_checker=FormatChecker()).iter_errors(value),
        key=lambda v: list(map(str, v.path)),
    )
    if errors:
        field = ".".join(map(str, errors[0].path)) or "body"
        raise AppError(422, "VALIDATION_ERROR", f"Некорректное поле: {field}")
    return value


def check_request(request, operation, body=None):
    for parameter in operation.get("parameters", []):
        name, location = parameter["name"], parameter["in"]
        values = (
            request.path_params
            if location == "path"
            else request.query_params
            if location == "query"
            else request.headers
        )
        raw = values.get(name)
        if raw is None:
            if parameter.get("required"):
                raise AppError(422, "MISSING_PARAMETER", f"Обязательный параметр: {name}")
            continue
        schema = parameter["schema"]
        if schema.get("type") == "integer":
            try:
                raw = int(raw)
            except ValueError as exc:
                raise AppError(422, "VALIDATION_ERROR", f"Некорректный параметр: {name}") from exc
        validate(raw, schema)
    if body is not None:
        validate(body, operation["requestBody"]["content"]["application/json"]["schema"])
