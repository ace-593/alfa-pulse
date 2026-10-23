"""Search the curated Alfa-Bank evidence index without inventing evidence.

This module intentionally searches only human_checked_excerpts. Document titles and
keywords may identify candidate PDFs, but are never returned as proof of a bank view.
Python >= 3.10; standard library only.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

DEFAULT_INDEX = Path(__file__).with_name("bank_evidence_index.json")
REVIEW_REQUIRED = "requires_bank_document_review"
EXCERPTS_AVAILABLE = "bank_excerpts_available"


def _normalise(value: str) -> str:
    value = value.casefold().replace("ё", "е")
    return re.sub(r"[^\w]+", " ", value, flags=re.UNICODE).strip()


def load_index(path: str | Path = DEFAULT_INDEX) -> dict[str, Any]:
    """Load the bank evidence index and validate its basic structure."""
    with Path(path).open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError("Evidence index must be a JSON object")
    if not isinstance(data.get("documents"), list):
        raise ValueError("Evidence index must contain a 'documents' list")
    if not isinstance(data.get("human_checked_excerpts", []), list):
        raise ValueError("'human_checked_excerpts' must be a list")
    return data


def validate_excerpt(excerpt: dict[str, Any], documents: dict[str, dict[str, Any]]) -> list[str]:
    """Return validation errors; an excerpt is usable only if source/page/quote exist."""
    errors: list[str] = []
    document_id = excerpt.get("document_id")
    if not document_id or document_id not in documents:
        errors.append("unknown_document_id")
    if not isinstance(excerpt.get("page"), int) or excerpt["page"] < 1:
        errors.append("invalid_page")
    if not isinstance(excerpt.get("short_exact_quote"), str) or not excerpt["short_exact_quote"].strip():
        errors.append("missing_exact_quote")
    if not excerpt.get("review_status"):
        errors.append("missing_review_status")
    if not excerpt.get("interpretation_limit"):
        errors.append("missing_interpretation_limit")
    if document_id in documents and isinstance(excerpt.get("page"), int):
        pages = documents[document_id].get("pages")
        if isinstance(pages, int) and excerpt["page"] > pages:
            errors.append("page_out_of_document_range")
    return errors


def search_verified_excerpts(
    query: str = "",
    categories: Iterable[str] = (),
    *,
    index_path: str | Path = DEFAULT_INDEX,
    limit: int = 5,
) -> dict[str, Any]:
    """Search reviewed excerpts only. Unreviewed documents are not evidence.

    Matching is deterministic lexical matching over quote, categories, title and topic
    metadata. This is a baseline; it does not claim semantic/vector search.
    """
    if limit < 1:
        raise ValueError("limit must be >= 1")
    index = load_index(index_path)
    documents = {doc.get("document_id"): doc for doc in index["documents"] if doc.get("document_id")}
    query_tokens = set(_normalise(query).split())
    requested_categories = {_normalise(str(c)) for c in categories if str(c).strip()}
    found: list[tuple[int, dict[str, Any], dict[str, Any]]] = []
    invalid_count = 0

    for excerpt in index.get("human_checked_excerpts", []):
        errors = validate_excerpt(excerpt, documents)
        if errors:
            invalid_count += 1
            continue
        doc = documents[excerpt["document_id"]]
        excerpt_categories = {_normalise(str(c)) for c in excerpt.get("categories", [])}
        searchable = " ".join([
            excerpt.get("short_exact_quote", ""),
            doc.get("title", ""),
            " ".join(doc.get("topics", [])),
            " ".join(excerpt.get("categories", [])),
        ])
        tokens = set(_normalise(searchable).split())
        category_match = bool(requested_categories & excerpt_categories)
        query_match = bool(query_tokens & tokens)
        if (not query_tokens and not requested_categories) or category_match or query_match:
            score = len(query_tokens & tokens) + (3 if category_match else 0)
            found.append((score, excerpt, doc))

    found.sort(key=lambda row: (row[0], row[2].get("document_date", "")), reverse=True)
    results = []
    for score, excerpt, doc in found[:limit]:
        results.append({
            "bank_document_id": doc["document_id"],
            "bank_document_title": doc.get("title"),
            "source_url": doc.get("source_url"),
            "page": excerpt["page"],
            "short_exact_quote": excerpt["short_exact_quote"],
            "as_of_date": doc.get("document_date"),
            "categories": excerpt.get("categories", []),
            "evidence_status": excerpt["review_status"],
            "interpretation_limit": excerpt["interpretation_limit"],
            "bank_analyst_opinion_not_ai_conclusion": True,
            "match_score": score,
        })

    status = EXCERPTS_AVAILABLE if results else REVIEW_REQUIRED
    return {
        "retrieved_bank_excerpts": results,
        "igor_handoff_status": status,
        "queries_to_bank_corpus": [] if results else [{
            "query": query,
            "categories": sorted(requested_categories),
            "candidate_only_not_found_evidence": True,
            "requires_document_search_or_visual_review": True,
        }],
        "bank_corpus_overview": {
            "total_documents": len(documents),
            "documents_with_any_curated_excerpt": len({e.get("document_id") for e in index.get("human_checked_excerpts", []) if not validate_excerpt(e, documents)}),
            "all_pages_searchable": False,
            "reason": index.get("limitations", "Only reviewed excerpts are searchable; document names alone are not evidence."),
            "invalid_excerpt_records_skipped": invalid_count,
        },
        "prohibited_claim": "Do not claim a bank viewpoint based on an unindexed PDF name alone.",
    }


def build_handoff(
    company_id: str,
    source_id: str,
    query: str = "",
    categories: Iterable[str] = (),
    *,
    index_path: str | Path = DEFAULT_INDEX,
    news_is_demo: bool = False,
) -> dict[str, Any]:
    """Build one P1.1-compatible handoff record for a company/news pair."""
    result = search_verified_excerpts(query, categories, index_path=index_path)
    return {
        "schema_version": "P1.1",
        "company_id": company_id,
        "source_id": source_id,
        "queries_to_bank_corpus": result["queries_to_bank_corpus"],
        "retrieved_bank_excerpts": result["retrieved_bank_excerpts"],
        "bank_corpus_overview": result["bank_corpus_overview"],
        "igor_handoff_status": result["igor_handoff_status"],
        "prohibited_claim": result["prohibited_claim"],
        "news_is_demo": news_is_demo,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Search reviewed Alfa-Bank evidence excerpts")
    parser.add_argument("query", nargs="?", default="", help="Words related to a news event")
    parser.add_argument("--category", action="append", default=[], help="Category; may be repeated")
    parser.add_argument("--company-id", default="TEST_COMPANY")
    parser.add_argument("--source-id", default="TEST_NEWS")
    parser.add_argument("--index", default=str(DEFAULT_INDEX))
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    print(json.dumps(build_handoff(args.company_id, args.source_id, args.query, args.category,
                                   index_path=args.index, news_is_demo=args.demo),
                     ensure_ascii=False, indent=2))
