"""
Shared in-memory GSTIN-to-GSTIN flow graph for cross-entity fraud detection.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Tuple

import networkx as nx


def _looks_like_gstin(value: str | None) -> bool:
    if not value:
        return False
    raw = value.strip().upper()
    return len(raw) == 15 and raw.isalnum()


class EntityGraphService:
    def __init__(self) -> None:
        self.graph = nx.DiGraph()
        self._lock = threading.Lock()
        self._contributions: Dict[str, Dict[Tuple[str, str], Dict[str, float]]] = {}

    def _remove_owner_contribution(self, owner_gstin: str) -> None:
        previous = self._contributions.pop(owner_gstin, {})
        for (src, dst), payload in previous.items():
            if not self.graph.has_edge(src, dst):
                continue
            self.graph[src][dst]["weight"] = max(0.0, self.graph[src][dst]["weight"] - payload["weight"])
            self.graph[src][dst]["txn_count"] = max(0, self.graph[src][dst]["txn_count"] - int(payload["txn_count"]))
            owners = self.graph[src][dst].get("owners", set())
            owners.discard(owner_gstin)
            if self.graph[src][dst]["weight"] <= 0 or self.graph[src][dst]["txn_count"] <= 0:
                self.graph.remove_edge(src, dst)
        for node in list(self.graph.nodes()):
            if self.graph.degree(node) == 0:
                self.graph.remove_node(node)

    def register_gstin_flows(
        self,
        owner_gstin: str,
        outflows: Dict[str, float],
        txn_counts: Dict[str, int] | None = None,
    ) -> None:
        with self._lock:
            self._remove_owner_contribution(owner_gstin)
            owner_edges: Dict[Tuple[str, str], Dict[str, float]] = {}
            for counterparty_gstin, amount in outflows.items():
                if not _looks_like_gstin(counterparty_gstin) or counterparty_gstin == owner_gstin:
                    continue
                count = int((txn_counts or {}).get(counterparty_gstin, 1))
                edge_key = (owner_gstin, counterparty_gstin)
                owner_edges[edge_key] = {"weight": float(amount), "txn_count": count}
                if self.graph.has_edge(owner_gstin, counterparty_gstin):
                    self.graph[owner_gstin][counterparty_gstin]["weight"] += float(amount)
                    self.graph[owner_gstin][counterparty_gstin]["txn_count"] += count
                    self.graph[owner_gstin][counterparty_gstin].setdefault("owners", set()).add(owner_gstin)
                else:
                    self.graph.add_edge(
                        owner_gstin,
                        counterparty_gstin,
                        weight=float(amount),
                        txn_count=count,
                        owners={owner_gstin},
                    )
            self._contributions[owner_gstin] = owner_edges

    def register_transactions(self, owner_gstin: str, transactions: List[Dict[str, Any]]) -> None:
        aggregated: Dict[Tuple[str, str], Dict[str, float]] = {}
        for txn in transactions:
            src = (txn.get("src_vpa") or "").strip().upper()
            dst = (txn.get("dst_vpa") or "").strip().upper()
            if src and dst and _looks_like_gstin(src) and _looks_like_gstin(dst):
                key = (src, dst)
                bucket = aggregated.setdefault(key, {"weight": 0.0, "txn_count": 0})
                bucket["weight"] += float(txn.get("amount", 0) or 0)
                bucket["txn_count"] += 1

        with self._lock:
            self._remove_owner_contribution(owner_gstin)
            self._contributions[owner_gstin] = {}
            for (src, dst), payload in aggregated.items():
                self._contributions[owner_gstin][(src, dst)] = payload
                if self.graph.has_edge(src, dst):
                    self.graph[src][dst]["weight"] += payload["weight"]
                    self.graph[src][dst]["txn_count"] += int(payload["txn_count"])
                    self.graph[src][dst].setdefault("owners", set()).add(owner_gstin)
                else:
                    self.graph.add_edge(
                        src,
                        dst,
                        weight=payload["weight"],
                        txn_count=int(payload["txn_count"]),
                        owners={owner_gstin},
                    )

    def get_cycles_involving(self, gstin: str) -> List[List[str]]:
        with self._lock:
            if gstin not in self.graph:
                return []
            cycles = list(nx.simple_cycles(self.graph))
            return [cycle for cycle in cycles if gstin in cycle and len(cycle) >= 3]

    def get_cycle_details_involving(self, gstin: str) -> List[Dict[str, Any]]:
        with self._lock:
            if gstin not in self.graph:
                return []
            details: List[Dict[str, Any]] = []
            for cycle in nx.simple_cycles(self.graph):
                if gstin not in cycle or len(cycle) < 3:
                    continue
                min_edge_value = min(
                    float(self.graph[cycle[i]][cycle[(i + 1) % len(cycle)]].get("weight", 0.0))
                    for i in range(len(cycle))
                )
                details.append({
                    "members": cycle,
                    "length": len(cycle),
                    "min_edge_value": round(min_edge_value),
                })
            return details

    def get_related_members(self, gstin: str) -> List[str]:
        members = set()
        for cycle in self.get_cycles_involving(gstin):
            members.update(cycle)
        members.discard(gstin)
        return sorted(members)

    def get_outflow_summary(self, gstin: str) -> Dict[str, Any]:
        with self._lock:
            out_edges = list(self.graph.out_edges(gstin, data=True))
        total_outflow = sum(float(data.get("weight", 0.0)) for _, _, data in out_edges)
        return {
            "total_outflow": total_outflow,
            "counterparties": {
                dst: {
                    "weight": round(float(data.get("weight", 0.0))),
                    "txn_count": int(data.get("txn_count", 0)),
                }
                for _, dst, data in out_edges
            },
        }

    def subgraph_for(self, gstin: str) -> nx.DiGraph:
        with self._lock:
            nodes = {gstin}
            nodes.update(self.graph.predecessors(gstin) if gstin in self.graph else [])
            nodes.update(self.graph.successors(gstin) if gstin in self.graph else [])
            cycles = [cycle for cycle in nx.simple_cycles(self.graph) if gstin in cycle and len(cycle) >= 3]
            for cycle in cycles:
                nodes.update(cycle)
            return self.graph.subgraph(nodes).copy()

    def health_summary(self) -> Dict[str, int]:
        with self._lock:
            return {
                "nodes": self.graph.number_of_nodes(),
                "edges": self.graph.number_of_edges(),
                "tracked_gstins": len(self._contributions),
            }


_entity_graph_service: EntityGraphService | None = None


def get_entity_graph_service() -> EntityGraphService:
    global _entity_graph_service
    if _entity_graph_service is None:
        _entity_graph_service = EntityGraphService()
    return _entity_graph_service


def reset_entity_graph_service() -> None:
    global _entity_graph_service
    _entity_graph_service = None
