import asyncio
import ipaddress
import socket
from datetime import UTC
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import urljoin, urlparse

import httpx
from defusedxml import ElementTree
from pypdf import PdfReader

from app.application.common import fingerprint
from app.domain.models import AppError, iso
from app.domain.policies import date

TOPICS = {
    "credit": ["ставк", "кредит", "финансир", "долг"],
    "deposit": ["депозит", "размещен"],
    "fx": ["валют", "курс", "импорт", "экспорт"],
    "metal": ["металл", "сталь", "золот"],
    "logistics": ["логист", "перевоз", "транспорт"],
    "agro": ["зерн", "сельск", "урожа"],
    "leasing": ["лизинг"],
}


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def strip_html(value):
    parser = PlainText()
    parser.feed(value or "")
    return " ".join(" ".join(parser.parts).split())


class HttpSourceFetcher:
    async def collect(self, source, published_from=None):
        parsed = urlparse(source["url"])
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
            raise AppError(422, "INVALID_SOURCE", "Источники должны использовать HTTPS")
        addresses = await asyncio.get_running_loop().getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise AppError(422, "INVALID_SOURCE", "Внутренние адреса источников запрещены")
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client:
                async with client.stream("GET", source["url"]) as response:
                    response.raise_for_status()
                    data = bytearray()
                    async for part in response.aiter_bytes():
                        data.extend(part)
                        if len(data) > 8 * 1024 * 1024:
                            raise AppError(422, "SOURCE_TOO_LARGE", "Материал превышает 8 МиБ")
        except (httpx.HTTPError, OSError) as exc:
            raise AppError(503, "SOURCE_UNAVAILABLE", "Источник недоступен") from exc
        fmt = source.get("_format", "rss")
        records = []
        try:
            if fmt == "rss":
                root = ElementTree.fromstring(bytes(data))
                for item in root.findall(".//item")[:200]:
                    timestamp = item.findtext("pubDate")
                    published = parsedate_to_datetime(timestamp).astimezone(UTC) if timestamp else None
                    records.append(
                        (
                            item.findtext("title") or "Без заголовка",
                            strip_html(item.findtext("description")),
                            urljoin(source["url"], item.findtext("link") or source["url"]),
                            published,
                        )
                    )
            elif fmt in {"text", "pdf"}:
                if fmt == "pdf":
                    reader = await asyncio.to_thread(PdfReader, BytesIO(bytes(data)))
                    if len(reader.pages) > 100:
                        raise ValueError("too many PDF pages")
                    content = await asyncio.to_thread(lambda: "\n".join(p.extract_text() or "" for p in reader.pages))
                else:
                    content = bytes(data).decode("utf-8")
                records.append(
                    (
                        source["name"],
                        content[:50000],
                        source["url"],
                        date(source["_publishedAt"]) if source.get("_publishedAt") else None,
                    )
                )
            else:
                raise ValueError("unsupported source format")
        except Exception as exc:
            raise AppError(422, "SOURCE_PARSE_FAILED", "Материал не удалось разобрать") from exc
        result = []
        for title, content, url, published in records:
            if published_from and (not published or published < published_from):
                continue
            if urlparse(url).scheme != "https":
                url = source["url"]
            material_id = fingerprint([source["id"], url])[:32]
            topics = [
                tag for tag, fragments in TOPICS.items() if any(f in (title + content).casefold() for f in fragments)
            ]
            record = {
                "id": material_id,
                "kind": source["kind"],
                "title": title[:500],
                "publisher": source["name"],
                "url": url,
                "publishedAt": iso(published) if published else None,
                "retrievedAt": iso(),
                "version": fingerprint([title, content])[:24],
                "text": content[:50000],
                "topics": topics,
                "availability": "available",
            }
            result.append(record)
        return result
