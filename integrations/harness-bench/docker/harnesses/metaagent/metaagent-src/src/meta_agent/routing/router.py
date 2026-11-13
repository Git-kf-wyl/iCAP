"""Ordered routing with versioned context-aware caching and measured outcomes."""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
from collections import Counter, OrderedDict, deque
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import asdict, dataclass, replace
from typing import Any

from meta_agent.errors import BootError, RouteClassificationError
from meta_agent.routing.conditions import Condition
from meta_agent.spec.fastpath import IntentMetadata, RouterConfig, WorkflowPluginManifest

Embedder = Callable[[list[str]], Awaitable[list[list[float]]]]
Classifier = Callable[[str, dict[str, str]], Awaitable[tuple[str, float] | None]]
_EMBEDDERS: dict[str, Embedder] = {}
_CLASSIFIERS: dict[str, Classifier] = {}


@dataclass(frozen=True)
class WorkflowRouteTarget:
    """Route a standalone Workflow without pretending it is an M3 plugin."""

    name: str
    version: str
    intent: IntentMetadata


def register_embedding_provider(name: str, provider: Embedder) -> None:
    _EMBEDDERS[name] = provider


def register_classifier_provider(name: str, provider: Classifier) -> None:
    _CLASSIFIERS[name] = provider


@dataclass(frozen=True)
class RouteDecision:
    matched: bool = False
    plugin: str | None = None
    plugin_version: str | None = None
    plugin_digest: str | None = None
    graph_version: str = ""
    strategy: str = "none"
    confidence: float = 0.0
    threshold: float = 0.0
    reason: str = "no_match"
    cache_hit: bool = False
    latency_ms: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize(vector: list[float]) -> tuple[float, ...]:
    if not vector or not all(isinstance(x, (int, float)) and math.isfinite(x) for x in vector):
        raise RouteClassificationError("META_ROUTE_VECTOR", "Invalid embedding vector.")
    norm = math.sqrt(sum(x * x for x in vector))
    if not math.isfinite(norm) or norm == 0:
        raise RouteClassificationError("META_ROUTE_VECTOR", "Invalid embedding norm.")
    return tuple(x / norm for x in vector)


class FastPathRouter:
    def __init__(
        self,
        config: RouterConfig,
        manifests: Sequence[WorkflowPluginManifest | WorkflowRouteTarget],
        digests: dict[str, str],
        graph_version: str,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.config = config.model_copy(deep=True)
        self.manifests = sorted(manifests, key=lambda m: (-m.intent.priority, m.name))
        self.by_name = {m.name: m for m in manifests}
        self.digests, self.graph_version, self.clock = digests, graph_version, clock
        self.conditions = {m.name: Condition(m.intent.when) for m in manifests}
        self.thresholds = {m.name: m.intent.threshold for m in manifests}
        self.disabled: set[str] = set()
        self.generation = 0
        self.stats: Counter[str] = Counter()
        self.plugin_stats: dict[str, Counter[str]] = {m.name: Counter() for m in manifests}
        self.windows: dict[str, deque[bool]] = {m.name: deque() for m in manifests}
        self.bad_windows: Counter[str] = Counter()
        self.cache: OrderedDict[str, tuple[float, RouteDecision]] = OrderedDict()
        self.vectors: dict[str, list[tuple[float, ...]]] = {}
        self.embedder = _EMBEDDERS.get(config.embedding_provider or "")
        self.classifier = _CLASSIFIERS.get(config.classifier_provider or "")
        if (
            config.embedding_provider
            and self.embedder is None
            or config.classifier_provider
            and self.classifier is None
        ):
            raise BootError("META_ROUTER_PROVIDER", "Routing provider is not registered.")
        if any(route.plugin not in self.by_name for route in config.skill_routes):
            raise BootError("META_SKILL_ROUTE", "Skill route refers to an inactive plugin.")

    async def start(self) -> None:
        if self.embedder is None:
            return
        examples = [(m.name, text) for m in self.manifests for text in m.intent.examples]
        if not examples:
            return
        vectors = await self.embedder([text for _, text in examples])
        self.stats["embedding_calls"] += 1
        if len(vectors) != len(examples):
            raise BootError("META_ROUTER_PROVIDER", "Embedding provider returned incorrect count.")
        dimension: int | None = None
        for (name, _), raw in zip(examples, vectors, strict=True):
            vector = _normalize(raw)
            dimension = dimension or len(vector)
            if len(vector) != dimension:
                raise BootError("META_ROUTER_PROVIDER", "Embedding dimensions are inconsistent.")
            self.vectors.setdefault(name, []).append(vector)

    def _eligible(self, name: str, context: dict[str, Any]) -> bool:
        return name not in self.disabled and self.conditions[name].matches(context)

    def _decision(self, name: str, strategy: str, confidence: float) -> RouteDecision:
        manifest = self.by_name[name]
        return RouteDecision(
            True,
            name,
            manifest.version,
            self.digests[name],
            self.graph_version,
            strategy,
            confidence,
            self.thresholds[name],
            "matched",
        )

    async def route(self, query: str, context: dict[str, Any], scope: str) -> RouteDecision:
        start = self.clock()
        key = hashlib.sha256(
            json.dumps(
                [scope, query, context, self.graph_version, self.generation],
                sort_keys=True,
                allow_nan=False,
            ).encode()
        ).hexdigest()
        self.stats["requests"] += 1
        cached = self.cache.get(key)
        if (
            cached
            and cached[0] > start
            and (cached[1].plugin is None or self._eligible(cached[1].plugin, context))
        ):
            self.cache.move_to_end(key)
            self.stats["cache_hits"] += 1
            decision = replace(cached[1], cache_hit=True)
        else:
            self.cache.pop(key, None)
            try:
                decision = await self._match(query, context)
            except RouteClassificationError:
                self.stats["classification_errors"] += 1
                decision = RouteDecision(
                    graph_version=self.graph_version, reason="classification_error"
                )
            if (
                self.config.cache_max_entries
                and self.config.cache_ttl_s
                and decision.reason != "classification_error"
            ):
                self.cache[key] = (start + self.config.cache_ttl_s, decision)
                while len(self.cache) > self.config.cache_max_entries:
                    self.cache.popitem(last=False)
        if decision.plugin:
            self.plugin_stats[decision.plugin]["selected"] += 1
        else:
            self.stats["misses"] += 1
        return replace(decision, latency_ms=max(0.0, (self.clock() - start) * 1000))

    async def _match(self, query: str, context: dict[str, Any]) -> RouteDecision:
        eligible = [m for m in self.manifests if self._eligible(m.name, context)]
        names = {m.name for m in eligible}
        for route in self.config.skill_routes:
            if route.plugin in names and (
                query in route.exact or any(query.startswith(p) for p in route.prefixes)
            ):
                return self._decision(route.plugin, "skill_meta", 1.0)
        for manifest in eligible:
            if any(re.search(pattern, query) for pattern in manifest.intent.rules):
                return self._decision(manifest.name, "rule", 1.0)
        if self.embedder is not None and self.vectors and eligible:
            vectors = await self.embedder([query])
            self.stats["embedding_calls"] += 1
            if len(vectors) != 1:
                raise RouteClassificationError("META_ROUTE_VECTOR", "Incorrect query vector count.")
            vector = _normalize(vectors[0])
            scored = []
            for manifest in eligible:
                references = self.vectors.get(manifest.name, [])
                if any(len(ref) != len(vector) for ref in references):
                    raise RouteClassificationError(
                        "META_ROUTE_VECTOR", "Embedding dimension changed."
                    )
                score = max(
                    (sum(a * b for a, b in zip(ref, vector, strict=True)) for ref in references),
                    default=-1.0,
                )
                if score >= self.thresholds[manifest.name]:
                    scored.append((score, manifest))
            if scored:
                score, manifest = max(scored, key=lambda item: item[0])
                return self._decision(manifest.name, "embedding", min(1.0, score))
        for manifest in eligible:
            if (
                manifest.intent.when is not None
                and not manifest.intent.rules
                and not manifest.intent.examples
            ):
                return self._decision(manifest.name, "condition", 1.0)
        if self.classifier is not None and eligible:
            self.stats["classifier_calls"] += 1
            candidate = await self.classifier(
                query, {m.name: m.intent.description for m in eligible}
            )
            if candidate is not None:
                name, confidence = candidate
                if name not in names or not math.isfinite(confidence) or not 0 <= confidence <= 1:
                    raise RouteClassificationError(
                        "META_ROUTE_CLASSIFIER", "Invalid classifier result."
                    )
                if confidence >= self.thresholds[name]:
                    return self._decision(name, "llm", confidence)
        return RouteDecision(graph_version=self.graph_version)

    def on_result(self, name: str, outcome: str) -> None:
        self.plugin_stats[name][outcome] += 1
        cfg = self.config.adaptive
        if not cfg.enabled or outcome not in {"success", "failed", "terminal"}:
            return
        window = self.windows[name]
        window.append(outcome == "success")
        if len(window) < cfg.window_size:
            return
        if sum(window) / len(window) < cfg.min_success_rate:
            self.bad_windows[name] += 1
            self.thresholds[name] = min(1.0, self.thresholds[name] + cfg.threshold_step)
            if self.bad_windows[name] >= cfg.disable_after_windows:
                self.disabled.add(name)
            self.generation += 1
            self.cache.clear()
        else:
            self.bad_windows[name] = 0
        window.clear()

    def snapshot(self) -> dict[str, Any]:
        return {
            "totals": dict(self.stats),
            "plugins": {name: dict(stats) for name, stats in self.plugin_stats.items()},
            "thresholds": dict(self.thresholds),
            "disabled": sorted(self.disabled),
            "policy_generation": self.generation,
            "graph_version": self.graph_version,
        }
