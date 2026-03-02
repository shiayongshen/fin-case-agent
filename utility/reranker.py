import re
from typing import Iterable, List, Sequence, Tuple, Union


def _tokenize(text: str) -> List[str]:
    # Simple tokenization with unicode word characters
    return re.findall(r"\w+", text.lower())


def _score_pair(query: str, document: str) -> float:
    q_tokens = _tokenize(query)
    d_tokens = _tokenize(document)
    if not q_tokens or not d_tokens:
        return 0.0

    q_set = set(q_tokens)
    d_set = set(d_tokens)
    intersection = len(q_set & d_set)
    union = len(q_set | d_set)
    if union == 0:
        return 0.0
    return intersection / union


class SimpleReranker:
    """A lightweight, torch-free reranker for basic relevance scoring."""

    def compute_score(
        self,
        pairs: Union[Sequence[str], Iterable[Sequence[str]]],
    ) -> Union[float, List[float]]:
        # Accept either a single pair [query, doc] or a list of (query, doc) pairs.
        if isinstance(pairs, (list, tuple)):
            if len(pairs) == 2 and all(isinstance(x, str) for x in pairs):
                return _score_pair(pairs[0], pairs[1])

            if pairs and isinstance(pairs[0], (list, tuple)) and len(pairs[0]) == 2:
                return [_score_pair(q, d) for q, d in pairs]  # type: ignore[misc]

        raise ValueError("Invalid input to compute_score; expected [query, doc] or list of pairs.")


def initialize_reranker() -> SimpleReranker:
    return SimpleReranker()
