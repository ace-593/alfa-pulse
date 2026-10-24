import csv
import io
import re
from datetime import datetime

from app.core.exceptions import AppError

ROLES = {"owner", "ceo", "cfo", "chief_accountant", "treasurer", "other"}
ROLE_LABELS = {
    "owner": "собственника",
    "ceo": "генерального директора",
    "cfo": "финансового директора",
    "chief_accountant": "главного бухгалтера",
    "treasurer": "казначея",
    "other": "пользователя",
}
TOPIC_LABELS = {
    "credit": "кредитование",
    "deposit": "депозиты",
    "fx": "внешняя торговля и валютные операции",
    "metal": "металлургия",
    "logistics": "перевозки",
    "agro": "сельское хозяйство",
    "leasing": "лизинг",
}


def normalize_email(value: str) -> str:
    result = value.strip().lower()
    if len(result) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", result):
        raise AppError(422, "INVALID_EMAIL", "Некорректный email")
    return result


def relevance(company_tags: list[str], material_tags: list[str], role: str) -> float:
    shared = set(company_tags) & set(material_tags)
    if not shared:
        return 0.0
    bonus = 0.08 * len(shared & {"credit", "fx", "deposit"}) if role in {"cfo", "treasurer"} else 0
    return min(0.99, 0.22 * len(shared) + bonus)


def date(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed
    except (ValueError, TypeError, AttributeError) as exc:
        raise AppError(422, "INVALID_DATE", "Дата должна содержать часовой пояс") from exc


def csv_rows(content: bytes, required: set[str]) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8-sig")
        first = text.splitlines()[0]
        reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=";" if ";" in first else ",", strict=True)
        headers = reader.fieldnames or []
        if len(set(headers)) != len(headers) or not required <= set(headers):
            raise ValueError("headers")
        rows = list(reader)
        if not rows or any(None in row or any(v is None for v in row.values()) for row in rows):
            raise ValueError("rows")
        return rows
    except (UnicodeError, ValueError, csv.Error, IndexError) as exc:
        raise AppError(422, "INVALID_CSV", "Проверь UTF-8, заголовки и число столбцов CSV") from exc
