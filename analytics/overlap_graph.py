"""Category-scoped overlap graph: matrices, clustering, and layouts."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering

CATEGORY_ORDER = [
    "Large Cap",
    "Mid Cap",
    "Small Cap",
    "Large & Mid Cap",
    "Multi Cap",
    "Flexi Cap",
    "ELSS",
]

STRONG_EDGE_PCT = 75.0
WEAK_EDGE_MIN_PCT = 15.0

TIER_DEFS = (
    ("A", "Very similar", "Hold just one of these", 60.0),
    ("B", "High overlap", "Moderate redundancy", 45.0),
    ("C", "Moderate", "Some shared holdings", 30.0),
    ("D", "Most unique", "Best for diversification", 0.0),
)


def fund_label(name: str, max_len: int = 28) -> str:
    n = (
        name.replace("Aditya Birla Sun Life ", "ABSL ")
        .replace("ICICI Prudential ", "ICICI Pru ")
        .replace("Mirae Asset ", "Mirae ")
        .replace("Franklin Templeton ", "Franklin ")
        .replace(" Large Cap Fund", "")
        .replace(" Large Cap", "")
        .replace(" Fund", "")
        .strip()
    )
    return (n[: max_len - 1] + "…") if len(n) > max_len else n


def funds_in_category(master: pd.DataFrame, category: str) -> list[str]:
    if master.empty or "category" not in master.columns:
        return []
    return (
        master.loc[master["category"] == category, "fund_name"]
        .dropna()
        .unique()
        .tolist()
    )


def filter_pairs(similarity: pd.DataFrame, funds: list[str]) -> pd.DataFrame:
    if similarity.empty or len(funds) < 2:
        return similarity.iloc[0:0]
    fund_set = set(funds)
    mask = similarity["fund_a"].isin(fund_set) & similarity["fund_b"].isin(fund_set)
    return similarity.loc[mask].copy()


def build_score_matrix(
    funds: list[str], pairs: pd.DataFrame
) -> tuple[np.ndarray, dict[tuple[str, str], float]]:
    n = len(funds)
    matrix = np.zeros((n, n), dtype=float)
    lookup: dict[tuple[str, str], float] = {}
    idx = {f: i for i, f in enumerate(funds)}

    for _, row in pairs.iterrows():
        a, b = row["fund_a"], row["fund_b"]
        if a not in idx or b not in idx:
            continue
        score = float(row["normalized_score"])
        i, j = idx[a], idx[b]
        matrix[i, j] = matrix[j, i] = score
        lookup[(a, b)] = lookup[(b, a)] = score

    return matrix, lookup


def pair_score(lookup: dict[tuple[str, str], float], a: str, b: str) -> float:
    if a == b:
        return 0.0
    return lookup.get((a, b), lookup.get((b, a), 0.0))


@dataclass(frozen=True)
class ClusterGroup:
    letter: str
    title: str
    subtitle: str
    fund_indices: tuple[int, ...]
    mean_overlap: float
    tier_key: str  # very_similar | high | moderate | distinct


def _mean_internal_overlap(matrix: np.ndarray, indices: tuple[int, ...]) -> float:
    if len(indices) < 2:
        return 0.0
    vals = [matrix[i, j] for i, j in combinations(indices, 2)]
    return float(np.mean(vals)) if vals else 0.0


def _tier_for_mean(mean_overlap: float) -> tuple[str, str, str, str]:
    for letter, title, subtitle, threshold in TIER_DEFS:
        if mean_overlap >= threshold:
            key = {
                "A": "very_similar",
                "B": "high",
                "C": "moderate",
                "D": "distinct",
            }[letter]
            return letter, title, subtitle, key
    return "D", TIER_DEFS[-1][1], TIER_DEFS[-1][2], "distinct"


def cluster_funds(matrix: np.ndarray, n_funds: int) -> list[ClusterGroup]:
    if n_funds == 0:
        return []
    if n_funds == 1:
        return [
            ClusterGroup("D", "Most unique", "Best for diversification", (0,), 0.0, "distinct")
        ]

    n_clusters = min(4, n_funds)
    dist = np.clip(100.0 - matrix, 0.0, None)
    np.fill_diagonal(dist, 0.0)

    labels = AgglomerativeClustering(
        n_clusters=n_clusters,
        metric="precomputed",
        linkage="average",
    ).fit_predict(dist)

    buckets: dict[int, list[int]] = {}
    for i, lab in enumerate(labels):
        buckets.setdefault(int(lab), []).append(i)

    groups: list[ClusterGroup] = []
    for indices in buckets.values():
        idx_t = tuple(sorted(indices))
        mean_ov = _mean_internal_overlap(matrix, idx_t)
        letter, title, subtitle, tier_key = _tier_for_mean(mean_ov)
        groups.append(
            ClusterGroup(letter, title, subtitle, idx_t, mean_ov, tier_key)
        )

    groups.sort(key=lambda g: g.mean_overlap, reverse=True)
    letters = ["A", "B", "C", "D"]
    remapped: list[ClusterGroup] = []
    for i, g in enumerate(groups):
        letter = letters[i] if i < len(letters) else "D"
        remapped.append(
            ClusterGroup(
                letter,
                g.title,
                g.subtitle,
                g.fund_indices,
                g.mean_overlap,
                g.tier_key,
            )
        )
    return remapped


def force_layout(
    matrix: np.ndarray,
    *,
    iterations: int = 300,
    seed: int = 42,
) -> np.ndarray:
    """Spring-embedding layout where natural edge length = 1 - overlap/100.
    Higher overlap → shorter spring → nodes sit closer in the final layout.
    All pairs also have a repulsion force to prevent collapse."""
    n = matrix.shape[0]
    if n == 0:
        return np.zeros((0, 2))
    if n == 1:
        return np.array([[0.0, 0.0]])

    rng = np.random.default_rng(seed)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    pos = np.column_stack([np.cos(angles), np.sin(angles)]) * 0.6

    K_repel  = 0.06   # global repulsion keeps nodes from collapsing
    K_spring = 0.20   # spring stiffness — governs how strongly overlap pulls nodes

    for step in range(iterations):
        # Cooling schedule: large steps early, fine-tune late
        temperature = max(0.01, 0.18 * (1.0 - step / iterations) ** 1.5)
        disp = np.zeros_like(pos)

        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                delta = pos[i] - pos[j]
                dist = max(float(np.linalg.norm(delta)), 0.01)
                direction = delta / dist

                # Repulsion: proportional to 1/dist² (same for every pair)
                disp[i] += direction * K_repel / (dist * dist)

                # Spring: natural length = 1 - overlap (0 overlap → nodes far apart,
                # 100% overlap → natural length 0 i.e. perfectly overlapping)
                w = matrix[i, j] / 100.0
                if w > 0:
                    natural_len = 1.0 - w  # Hooke's law rest length
                    spring_f    = K_spring * (dist - natural_len)
                    disp[i] -= direction * spring_f

        pos += np.clip(disp, -temperature, temperature)
        pos -= pos.mean(axis=0, keepdims=True)

    span = np.max(np.abs(pos)) or 1.0
    return pos / span


def circular_layout(n: int) -> np.ndarray:
    if n == 0:
        return np.zeros((0, 2))
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.column_stack([np.cos(angles), np.sin(angles)])


def bubble_positions(
    groups: list[ClusterGroup],
    *,
    seed: int = 7,
) -> np.ndarray:
    """Place funds inside four cluster regions (2×2 grid)."""
    n = sum(len(g.fund_indices) for g in groups)
    pos = np.zeros((n, 2))
    if n == 0:
        return pos

    centers = [(0.28, 0.72), (0.72, 0.72), (0.28, 0.28), (0.72, 0.28)]
    rng = np.random.default_rng(seed)

    for gi, group in enumerate(groups):
        cx, cy = centers[gi % len(centers)]
        m = len(group.fund_indices)
        if m == 1:
            offsets = [(0.0, 0.0)]
        else:
            angles = np.linspace(0, 2 * np.pi, m, endpoint=False)
            radius = min(0.11, 0.04 + 0.012 * m)
            offsets = [(radius * np.cos(a), radius * np.sin(a)) for a in angles]

        for k, fund_i in enumerate(group.fund_indices):
            ox, oy = offsets[k]
            jitter = (rng.random(2) - 0.5) * 0.015
            pos[fund_i] = [cx + ox + jitter[0], cy + oy + jitter[1]]

    return pos


def top_overlaps(
    fund: str,
    funds: list[str],
    lookup: dict[tuple[str, str], float],
    *,
    limit: int = 5,
    min_pct: float = 0.0,
) -> list[tuple[str, float]]:
    rows = [
        (other, pair_score(lookup, fund, other))
        for other in funds
        if other != fund and pair_score(lookup, fund, other) >= min_pct
    ]
    rows.sort(key=lambda x: x[1], reverse=True)
    return rows[:limit]


def get_edges(
    matrix: np.ndarray,
    min_pct: float,
    *,
    top_k_per_fund: int | None = 3,
) -> list[tuple[int, int, float]]:
    """Unique undirected edges at or above min_pct; optionally cap degree per fund."""
    n = matrix.shape[0]
    if n < 2:
        return []

    edge_scores: dict[tuple[int, int], float] = {}
    for i in range(n):
        neighbors = [
            (j, float(matrix[i, j]))
            for j in range(n)
            if j != i and matrix[i, j] >= min_pct
        ]
        neighbors.sort(key=lambda x: x[1], reverse=True)
        if top_k_per_fund is not None:
            neighbors = neighbors[:top_k_per_fund]
        for j, score in neighbors:
            key = (i, j) if i < j else (j, i)
            edge_scores[key] = max(edge_scores.get(key, 0.0), score)

    return [(i, j, s) for (i, j), s in edge_scores.items()]


def selected_indices(graph: "CategoryGraph", selected_funds: list[str]) -> set[int]:
    return {graph.funds.index(f) for f in selected_funds if f in graph.funds}


def neighbor_indices(
    graph: "CategoryGraph",
    selected_funds: list[str],
    min_pct: float,
) -> set[int]:
    idxs = selected_indices(graph, selected_funds)
    if not idxs:
        return set()
    out = set(idxs)
    for i in idxs:
        for j, score in enumerate(graph.matrix[i]):
            if j != i and score >= min_pct:
                out.add(j)
    return out


def pairs_among_selected(
    graph: "CategoryGraph",
    selected_funds: list[str],
    min_pct: float,
) -> list[tuple[str, str, float]]:
    idxs = sorted(selected_indices(graph, selected_funds))
    rows: list[tuple[str, str, float]] = []
    for a, b in combinations(idxs, 2):
        score = float(graph.matrix[a, b])
        if score >= min_pct:
            rows.append((graph.funds[a], graph.funds[b], score))
    rows.sort(key=lambda r: r[2], reverse=True)
    return rows


@dataclass
class CategoryGraph:
    category: str
    funds: list[str]
    labels: list[str]
    matrix: np.ndarray
    lookup: dict[tuple[str, str], float]
    clusters: list[ClusterGroup]
    fund_cluster: dict[int, int]
    positions_force: np.ndarray
    positions_bubble: np.ndarray
    positions_constellation: np.ndarray


def build_category_graph(
    category: str,
    funds: list[str],
    pairs: pd.DataFrame,
) -> CategoryGraph | None:
    if len(funds) < 1:
        return None

    matrix, lookup = build_score_matrix(funds, pairs)
    labels = [fund_label(f) for f in funds]
    clusters = cluster_funds(matrix, len(funds))

    fund_cluster: dict[int, int] = {}
    for gi, group in enumerate(clusters):
        for fi in group.fund_indices:
            fund_cluster[fi] = gi

    return CategoryGraph(
        category=category,
        funds=funds,
        labels=labels,
        matrix=matrix,
        lookup=lookup,
        clusters=clusters,
        fund_cluster=fund_cluster,
        positions_force=force_layout(matrix),
        positions_bubble=bubble_positions(clusters),
        positions_constellation=circular_layout(len(funds)),
    )
