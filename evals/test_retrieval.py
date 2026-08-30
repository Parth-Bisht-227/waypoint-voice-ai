import pytest
from agent.retriever import search_faq_answer, search_faqs

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

def test_exact_japan_evisa_question_returns_grounded_overview():
    result = top_result(
        "Can an Indian passport holder apply for a Japan tourist eVisa?"
    )

    assert result is not None
    assert result["id"] == "faq_016"
    assert result["official_source"].startswith("Embassy of Japan")
    assert result["source_url"].startswith("https://www.in.emb-japan.go.jp/")
    assert result["last_reviewed"] == "2026-08-30"

def test_model_facing_search_returns_only_answer_and_source():
    result = search_faq_answer(
        "Can an Indian passport holder apply for a Japan tourist eVisa?"
    )

    assert set(result) == {"answer", "source"}
    assert result["source"].startswith("Embassy of Japan")

def test_model_facing_search_returns_one_compact_general_answer():
    result = search_faq_answer("What does blocked mean?")

    assert set(result) == {"answer"}
    assert "cannot currently continue" in result["answer"]

def test_model_facing_search_returns_compact_not_found_result():
    result = search_faq_answer(
        "What is the baggage allowance on Nordic Airlines?"
    )

    assert result == {"found": False}

@pytest.mark.parametrize(
    "query",
    [
        "What documents do I need for a Japan tourist visa?",
        "What should I prepare for a Tokyo holiday?",
        "Does the Japan visa checklist ask for financial evidence?",
    ],
)
def test_japan_document_questions_return_the_checklist_guidance(query):
    result = top_result(query)

    assert result is not None
    assert result["id"] == "faq_017"

def test_japan_application_paraphrase_returns_process_guidance():
    result = top_result(
        "How do I submit my Japan visa application through VFS?"
    )

    assert result is not None
    assert result["id"] == "faq_018"

@pytest.mark.parametrize(
    "query",
    [
        "How do I apply for a US tourist visa?",
        "What documents are needed for a Singapore tourist visa?",
    ],
)
def test_unsupported_visa_destinations_return_only_scope_guidance(query):
    results = search_faqs(query, top_k=3, min_score=2)

    assert [result["id"] for result in results] == ["faq_019"]

def test_generic_visa_words_do_not_leak_japan_specific_guidance():
    results = search_faqs(
        "What documents do I need for a tourist visa?",
        top_k=3,
        min_score=2,
    )

    assert not {"faq_016", "faq_017", "faq_018"} & {
        result["id"] for result in results
    }

@pytest.mark.parametrize(
    "query",
    ["", "   ", "...", "???"],
)
def test_empty_or_noise_query_returns_no_results(query):
    assert search_faqs(query) == []
