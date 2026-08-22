import pytest
from agent.retriever import search_faqs

def top_result(query: str):
    results = search_faqs(query, top_k=3, min_score = 2)
    return results[0] if results else None

def test_exact_blocked_question():
    result = top_result("What does blocked mean?")

    assert result is not None
    assert result["id"] == "faq_002"

def test_blocked_paraphrase():
    result = top_result("My application seems stuck.")

    assert result is not None
    assert result["id"] == "faq_002"

def test_missing_documents_question():
    result = top_result("How do i find out which documents are missing?")

    assert result is not None
    assert result["id"] == "faq_006"

def test_travel_date_confirmation_question():
    result = top_result("Why do I have to confirm a date change?")

    assert result is not None
    assert result["id"] == "faq_008"

def test_unknown_airline_policy_returns_no_result():
    results = search_faqs(
        "What is the baggage allowance on Nordic Airlines?",
        top_k=3,
        min_score=2,
    )
    assert results == []

def test_human_support_explanation():
    result = top_result("How does human support work?")

    assert result is not None
    assert result["id"] == "faq_010"

@pytest.mark.parametrize(
    "query",
    ["", "   ", "...", "???"],
)
def test_empty_or_noise_query_returns_no_results(query):
    assert search_faqs(query) == []