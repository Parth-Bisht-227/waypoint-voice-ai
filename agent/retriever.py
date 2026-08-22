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

    # Keywords are deliberately curated search hints,
    # so give them slightly more weight.
    for keyword in faq.get("keywords", []):
        normalized_keyword = normalize_text(keyword)
        keyword_tokens = tokenize(keyword)

        if normalized_keyword in normalized_query:
            score += 4

        score += 3 * len(
            query_tokens & keyword_tokens
        )

    return score



def search_faqs(
    query: str,
    top_k: int = 3,
    min_score: int = 2,
) -> list[dict]:
    """
    Return the most relevant FAQ entries for the user's query.
    """

    results = []

    for faq in load_faqs():
        score = score_faq(query, faq)

        if score >= min_score:
            results.append(
                {
                    "id": faq["id"],
                    "category": faq["category"],
                    "question": faq["question"],
                    "answer": faq["answer"],
                    "score": score,
                }
            )

    results.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    return results[:top_k]
