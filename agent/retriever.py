import json
import re
from functools import lru_cache
from pathlib import Path


'''
lexical search implemented here, since the data is very small.
lexical search is primarily about the 
words/tokens themselves, not their underlying semantic meaning.


our current retriever is very simple:

    user query
    ↓
    normalize + tokenize
    ↓
    compare words/phrases against:
    - FAQ question
    - curated keywords
    ↓
    assign relevance score
    ↓
    sort highest → lowest
    ↓
    return top matching FAQs



this is the list of available approaches that can be implemented:

1. Exact / keyword lookup
   "blocked" → blocked FAQ

2. Custom lexical scoring          ← we're here
   token overlap + phrases + keywords

3. TF-IDF / BM25
   smarter statistical lexical ranking

4. Fuzzy matching
   handles spelling variations / similar strings

5. Embedding / vector search
   searches by semantic similarity

6. Hybrid retrieval
   lexical + embeddings together

7. LLM-based retrieval/reranking
   retrieve candidates, then let an LLM rank them


for our current lightweight v1, lexical retrieval is the right choice...   
'''

FAQ_PATH = (
    Path(__file__).resolve().parent.parent
    / "knowledge"
    / "faqs.json"
)

STOP_WORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "am",
    "i",
    "my",
    "me",
    "you",
    "your",
    "it",
    "to",
    "of",
    "for",
    "and",
    "or",
    "do",
    "does",
    "what",
    "why",
    "how",
    "can",
    "could",
    "would",

    # Domain-generic words
    "application",
}

def normalize_text(text: str) -> str:
    """
    Lowercase text and remove punctuation so lexical matching
    is more consistent.
    """
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def tokenize(text: str) -> set[str]:
    """
    Convert text into useful searchable words while dropping
    common words that contribute little meaning.
    """
    normalized = normalize_text(text)

    return {
        token
        for token in normalized.split()
        if token not in STOP_WORDS
    }


def matches_required_query_terms(query: str, faq: dict) -> bool:
    """Keep scenario-specific FAQs from matching the wrong destination."""

    required_terms = faq.get("required_query_terms", [])
    if not required_terms:
        return True

    normalized_query = normalize_text(query)
    return any(
        normalize_text(term) in normalized_query
        for term in required_terms
    )


def exclusive_query_categories(
    query: str,
    faqs: list[dict],
) -> set[str]:
    """Find categories that explicitly claim a query's domain terms."""

    normalized_query = normalize_text(query)
    return {
        faq["category"]
        for faq in faqs
        for term in faq.get("exclusive_query_terms", [])
        if normalize_text(term) in normalized_query
    }


@lru_cache(maxsize=1)
def load_faqs() -> list[dict]:
    """
    Load the FAQ corpus once per agent process.

    lru_cache means repeated searches do not repeatedly read the
    json file from disk.
    """
    with FAQ_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def score_faq(query: str, faq:dict) -> int:
    """
    Give an FAQ a deterministic relevance score for a query.
    Higher score means a stronger lexical match.
    """

    normalized_query = normalize_text(query)
    normalized_question = normalize_text(faq["question"])

    query_tokens = tokenize(query)
    question_tokens = tokenize(faq["question"])

    score = 0

    # Strong boost for a nearly exact FAQ question.
    if normalized_query == normalized_question:
        score += 10

    # Useful when one phrase largely contains the other.
    if (
        normalized_query in normalized_question
        or normalized_question in normalized_query
    ):
        score += 4

    # Words appearing in the FAQ question are important.
    score += 2 * len(
        query_tokens & question_tokens
    )

    # Keywords are deliberately curated search hints. Phrase matches can each
    # contribute, while overlapping keyword tokens count only once so repeated
    # generic words cannot overwhelm a more specific FAQ question.
    keyword_tokens: set[str] = set()
    for keyword in faq.get("keywords", []):
        normalized_keyword = normalize_text(keyword)
        keyword_tokens.update(tokenize(keyword))

        if normalized_keyword in normalized_query:
            score += 4

    score += 3 * len(query_tokens & keyword_tokens)

    return score



def search_faqs(
    query: str,
    top_k: int = 3,
    min_score: int = 2,
) -> list[dict]:
    """
    Return the most relevant FAQ entries for the user's query.
    """

    if not normalize_text(query):
        return []
    
    results = []
    faqs = load_faqs()
    exclusive_categories = exclusive_query_categories(query, faqs)

    for faq in faqs:
        if (
            exclusive_categories
            and faq["category"] not in exclusive_categories
        ):
            continue

        if not matches_required_query_terms(query, faq):
            continue

        score = score_faq(query, faq)

        if score >= min_score:
            result = {
                "id": faq["id"],
                "category": faq["category"],
                "question": faq["question"],
                "answer": faq["answer"],
                "score": score,
            }
            for metadata_key in (
                "official_source",
                "source_url",
                "last_reviewed",
            ):
                if metadata_key in faq:
                    result[metadata_key] = faq[metadata_key]

            results.append(result)

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[:top_k]


def search_faq_answer(query: str) -> dict:
    """Return one compact, model-facing answer from the local FAQ corpus."""

    results = search_faqs(
        query=query,
        top_k=1,
        min_score=2,
    )
    if not results:
        return {"found": False}

    top_result = results[0]
    response = {"answer": top_result["answer"]}

    if source := top_result.get("official_source"):
        response["source"] = source

    return response
