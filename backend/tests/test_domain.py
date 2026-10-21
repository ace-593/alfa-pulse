import pytest

from app.application.analytics import claim, verified_claims
from app.domain.models import AppError
from app.domain.policies import csv_rows, date, normalize_email, relevance


def test_csv_quotes_and_invalid_links_format():
    values = csv_rows(b'SYNTHETIC_U;NAME\ncompany;"a;b"\n', {"SYNTHETIC_U"})
    assert values[0]["NAME"] == "a;b"
    with pytest.raises(AppError):
        csv_rows(b"A,A\n1,2", {"A"})
    with pytest.raises(AppError):
        csv_rows(b"A,B\n1,2,3", {"A"})


def test_core_policies():
    assert normalize_email(" NAME@example.COM ") == "name@example.com"
    with pytest.raises(AppError):
        normalize_email("bad")
    with pytest.raises(AppError):
        date("2026-10-01")
    assert relevance(["credit"], ["credit"], "cfo") > relevance(["credit"], ["credit"], "ceo")
    assert relevance(["agro"], ["credit"], "cfo") == 0


def test_claims_require_real_quote_and_acyclic_support():
    source = {"id": "a", "version": "1", "kind": "external_news", "text": "Supported text"}
    invalid = claim("text", "confirmed_fact", [{"materialId": "a", "materialVersion": "1", "quote": "invented"}])
    with pytest.raises(AppError):
        verified_claims([invalid], [source], [])
    a, b = claim("A", "model_inference", features=["f"]), claim("B", "model_inference", features=["f"])
    a["supportingClaimIds"], b["supportingClaimIds"] = [b["id"]], [a["id"]]
    with pytest.raises(AppError):
        verified_claims([a, b], [], ["f"])
