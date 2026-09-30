"""Model-agnostic smart dataset curation scoring.

The engine is intentionally independent from Tkinter and PyTorch.  It combines
rarity, diversity, difficulty and relevance into a deterministic greedy selector.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence, Set


@dataclass(frozen=True)
class CuratorWeights:
    diversity: float = 1.0
    difficulty: float = 1.0
    relevance: float = 2.0
    rarity: float = 1.5
    multi_label: float = 0.15


def class_rarity(class_to_images: Mapping[str, Sequence[str]]) -> Dict[str, float]:
    """Return inverse-frequency rarity, normalized to [0, 1]."""
    counts = {c: len(set(v)) for c, v in class_to_images.items()}
    nonzero = [n for n in counts.values() if n > 0]
    if not nonzero:
        return {c: 0.0 for c in counts}
    max_count = max(nonzero)
    min_count = min(nonzero)
    if max_count == min_count:
        return {c: 1.0 if counts[c] else 0.0 for c in counts}
    # Rare class => close to 1, common class => close to 0.
    return {
        c: ((max_count - n) / (max_count - min_count)) if n else 0.0
        for c, n in counts.items()
    }


def image_rarity(image_labels: Mapping[str, Iterable[str]], rarity: Mapping[str, float]) -> Dict[str, float]:
    scores = {}
    for stem, labels in image_labels.items():
        labs = list(dict.fromkeys(labels))
        scores[stem] = sum(rarity.get(c, 0.0) for c in labs) / max(1, len(labs))
    return scores


def selection_score(
    stem: str,
    image_labels: Mapping[str, Iterable[str]],
    remaining: Mapping[str, int],
    difficulty: Mapping[str, float],
    diversity: float,
    rarity: Mapping[str, float],
    weights: CuratorWeights = CuratorWeights(),
) -> float:
    labels = list(dict.fromkeys(image_labels.get(stem, [])))
    relevant = [c for c in labels if remaining.get(c, 0) > 0]
    if not relevant:
        return float("-inf")
    relevance = sum(1 for _ in relevant)
    rarity_score = sum(rarity.get(c, 0.0) for c in relevant) / len(relevant)
    multi = max(0, len(relevant) - 1)
    return (
        weights.diversity * diversity
        + weights.difficulty * float(difficulty.get(stem, 0.0))
        + weights.relevance * relevance
        + weights.rarity * rarity_score
        + weights.multi_label * multi
    )


def greedy_select(
    candidates: Sequence[str],
    image_labels: Mapping[str, Iterable[str]],
    quotas: Mapping[str, int],
    difficulty: Mapping[str, float] | None = None,
    embeddings: Mapping[str, Sequence[float]] | None = None,
    weights: CuratorWeights = CuratorWeights(),
) -> List[str]:
    """Greedily select candidates while satisfying as much class quota as possible.

    Embeddings are optional.  When supplied, cosine similarity is used to reward
    visual diversity without importing torch.
    """
    difficulty = difficulty or {}
    class_to_images: Dict[str, Set[str]] = {c: set() for c in quotas}
    for stem in candidates:
        for c in set(image_labels.get(stem, [])):
            if c in class_to_images:
                class_to_images[c].add(stem)
    rarity = class_rarity(class_to_images)

    remaining = dict(quotas)
    pool = list(dict.fromkeys(candidates))
    selected: List[str] = []

    # Unit vectors, and each candidate's best similarity to anything selected so
    # far, updated incrementally (O(pool) per pick instead of O(pool * selected)).
    unit = {s: _unit(embeddings[s]) for s in pool if embeddings and s in embeddings}
    max_sim: Dict[str, float] = {}

    while pool and any(v > 0 for v in remaining.values()):
        best_stem = None
        best_score = float("-inf")
        for stem in pool:
            div = 1.0 - max_sim[stem] if stem in max_sim else 1.0
            score = selection_score(stem, image_labels, remaining, difficulty, div, rarity, weights)
            if score > best_score or (score == best_score and (best_stem is None or stem.casefold() < best_stem.casefold())):
                best_score, best_stem = score, stem
        if best_stem is None or best_score == float("-inf"):
            break
        pool.remove(best_stem)
        selected.append(best_stem)
        chosen = unit.get(best_stem)
        if chosen is not None:
            for stem in pool:
                vec = unit.get(stem)
                if vec is not None:
                    sim = sum(a * b for a, b in zip(vec, chosen))
                    if sim > max_sim.get(stem, -1.0):
                        max_sim[stem] = sim
        for c in set(image_labels.get(best_stem, [])):
            if c in remaining:
                remaining[c] = max(0, remaining[c] - 1)
    return selected


def _unit(vector: Sequence[float]) -> List[float]:
    values = [float(x) for x in vector]
    norm = sum(x * x for x in values) ** 0.5 or 1.0
    return [x / norm for x in values]
