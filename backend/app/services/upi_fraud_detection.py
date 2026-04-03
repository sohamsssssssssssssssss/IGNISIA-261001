"""
UPI circular transaction fraud detection module.
Detects fund rotation topologies where multiple MSMEs cycle the same
UPI funds to artificially inflate transaction volumes and scores.

Extends the existing NetworkX-based GST circular trading detection
to UPI payment flows.
"""

from collections import defaultdict
from typing import Any, Dict, List

import networkx as nx

from ..core.entity_graph import EntityGraphService


class UPIFraudDetector:
    """
    Detects circular UPI transaction patterns indicative of score manipulation.

    Detection strategies:
    1. Direct cycle detection: A→B→C→A fund loops
    2. Round-amount clustering: high % of round-number transfers (rotation signal)
    3. Temporal pattern: same-day back-and-forth between counterparties
    4. Volume inflation: large volumes but narrow counterparty base
    """

    def __init__(self, min_cycle_value: float = 50000, round_threshold_pct: float = 30):
        self.min_cycle_value = min_cycle_value
        self.round_threshold_pct = round_threshold_pct

    def detect_circular_transactions(
        self,
        transactions: List[Dict[str, Any]],
        gstin: str,
        entity_graph_service: EntityGraphService | None = None,
    ) -> Dict[str, Any]:
        """
        Analyze UPI transactions for circular patterns.

        Args:
            transactions: List of UPI transactions with counterparty_vpa, amount, direction
            gstin: The entity's GSTIN (acts as central node)

        Returns:
            - circular_risk: HIGH / MEDIUM / LOW
            - cycles_found: list of detected fund rotation cycles
            - round_amount_alert: bool
            - bounceback_pairs: counterparties with same-day back-and-forth
            - risk_score: 0-100 (higher = more suspicious)
        """
        if not transactions:
            result = self._empty_result()
            if entity_graph_service is not None:
                result.update(self.check_cross_entity_fraud(gstin, entity_graph_service))
            return result

        # Build directed transaction graph
        G = nx.DiGraph()
        daily_flows = defaultdict(lambda: defaultdict(float))
        total_txns = len(transactions)
        round_count = 0
        linked_nodes = set()

        for txn in transactions:
            counterparty = txn.get("counterparty_vpa", "UNKNOWN")
            amount = txn.get("amount", 0)
            direction = txn.get("direction", "DR")
            date = txn.get("date", "")
            is_round = txn.get("is_round_amount", False)

            if is_round:
                round_count += 1

            explicit_src = txn.get("src_vpa")
            explicit_dst = txn.get("dst_vpa")
            if explicit_src and explicit_dst:
                src, dst = explicit_src, explicit_dst
            else:
                if direction == "CR":
                    # Money coming IN: counterparty → gstin
                    src, dst = counterparty, gstin
                else:
                    # Money going OUT: gstin → counterparty
                    src, dst = gstin, counterparty

            if src != gstin:
                linked_nodes.add(src)
            if dst != gstin:
                linked_nodes.add(dst)

            if G.has_edge(src, dst):
                G[src][dst]["weight"] += amount
                G[src][dst]["count"] += 1
            else:
                G.add_edge(src, dst, weight=amount, count=1)

            # Track daily flows for bounceback detection
            daily_flows[date][(src, dst)] += amount

        # 1. CYCLE DETECTION (single-entity / transaction-local)
        cycles = list(nx.simple_cycles(G))
        high_value_cycles = []
        for cycle in cycles:
            if len(cycle) < 3:
                continue
            # Min edge weight in cycle
            cycle_weight = min(
                G[cycle[i]][cycle[(i + 1) % len(cycle)]]["weight"]
                for i in range(len(cycle))
            )
            if cycle_weight >= self.min_cycle_value:
                high_value_cycles.append({
                    "nodes": cycle,
                    "min_edge_value": round(cycle_weight),
                    "cycle_length": len(cycle),
                    "contains_focal_gstin": gstin in cycle,
                })

        # 2. ROUND AMOUNT ANALYSIS
        round_pct = (round_count / max(total_txns, 1)) * 100
        round_alert = round_pct >= self.round_threshold_pct

        # 3. BOUNCEBACK DETECTION (same-day back-and-forth)
        bounceback_pairs = []
        for date, flows in daily_flows.items():
            edges = list(flows.keys())
            for i, (src1, dst1) in enumerate(edges):
                reverse = (dst1, src1)
                if reverse in flows:
                    val_forward = flows[(src1, dst1)]
                    val_reverse = flows[reverse]
                    # If amounts are within 20% of each other, it's suspicious
                    ratio = min(val_forward, val_reverse) / max(val_forward, val_reverse, 1)
                    if ratio > 0.8:
                        bounceback_pairs.append({
                            "date": date,
                            "party_a": src1,
                            "party_b": dst1,
                            "amount_forward": round(val_forward),
                            "amount_reverse": round(val_reverse),
                            "match_ratio": round(ratio, 2),
                        })

        # 4. CONCENTRATION ANALYSIS
        counterparties = set()
        for txn in transactions:
            counterparties.add(txn.get("counterparty_vpa", "") or txn.get("src_vpa", ""))
        concentration = len(counterparties)
        total_volume = sum(txn.get("amount", 0) for txn in transactions)
        vol_per_counterparty = total_volume / max(concentration, 1)

        single_entity_score = min(len(high_value_cycles) * 12.5, 25.0)
        heuristics_score = 0.0
        heuristics_score += min(round_pct / self.round_threshold_pct * 10, 10)
        heuristics_score += min(len(bounceback_pairs) * 5, 10)
        if concentration < 10 and total_volume > 1000000:
            heuristics_score += 5
        heuristics_score = min(20.0, heuristics_score)

        cross_entity = self.check_cross_entity_fraud(gstin, entity_graph_service) if entity_graph_service else {
            "cross_entity_fraud_detected": False,
            "circular_flow_ratio": 0.0,
            "cycles_detected": [],
            "fraud_ring_members": [],
            "cross_entity_score": 0.0,
        }

        risk_score = min(
            100.0,
            float(cross_entity.get("cross_entity_score", 0.0)) + single_entity_score + heuristics_score,
        )

        # Risk classification
        if risk_score >= 60:
            circular_risk = "HIGH"
        elif risk_score >= 30:
            circular_risk = "MEDIUM"
        else:
            circular_risk = "LOW"

        return {
            "circular_risk": circular_risk,
            "risk_score": round(risk_score),
            "cycles_found": high_value_cycles,
            "cycle_count": len(high_value_cycles),
            "single_entity_cycles": len(high_value_cycles),
            "round_amount_alert": round_alert,
            "round_amount_pct": round(round_pct, 1),
            "bounceback_pairs": bounceback_pairs[:10],  # Top 10
            "bounceback_count": len(bounceback_pairs),
            "counterparty_count": concentration,
            "linked_msme_nodes": sorted(node for node in linked_nodes if len(node) == 15 and node != gstin),
            "linked_msme_count": len([node for node in linked_nodes if len(node) == 15 and node != gstin]),
            "total_volume": round(total_volume),
            "volume_per_counterparty": round(vol_per_counterparty),
            "cross_entity_fraud_detected": cross_entity["cross_entity_fraud_detected"],
            "circular_flow_ratio": cross_entity["circular_flow_ratio"],
            "fraud_ring_members": cross_entity["fraud_ring_members"],
            "cycles_detected": cross_entity["cycles_detected"],
            "cross_entity_score": round(float(cross_entity.get("cross_entity_score", 0.0)), 1),
            "single_entity_score": round(single_entity_score, 1),
            "heuristics_score": round(heuristics_score, 1),
            "graph_stats": {
                "nodes": G.number_of_nodes(),
                "edges": G.number_of_edges(),
                "density": round(nx.density(G), 4) if G.number_of_nodes() > 1 else 0,
            },
        }

    def check_cross_entity_fraud(
        self,
        gstin: str,
        entity_graph_service: EntityGraphService,
    ) -> Dict[str, Any]:
        cycles = [
            detail
            for detail in entity_graph_service.get_cycle_details_involving(gstin)
            if detail["min_edge_value"] >= self.min_cycle_value
        ]
        if not cycles:
            return {
                "cross_entity_fraud_detected": False,
                "circular_flow_ratio": 0.0,
                "cycles_detected": [],
                "fraud_ring_members": [],
                "cross_entity_score": 0.0,
            }

        outflow_summary = entity_graph_service.get_outflow_summary(gstin)
        total_outflow = float(outflow_summary["total_outflow"])
        cycle_members = set()
        for cycle in cycles:
            cycle_members.update(cycle["members"])
        cycle_members.discard(gstin)

        circular_outflow = 0.0
        for member in cycle_members:
            circular_outflow += float(outflow_summary["counterparties"].get(member, {}).get("weight", 0.0))

        circular_ratio = circular_outflow / total_outflow if total_outflow > 0 else 0.0
        cross_entity_score = min(55.0, circular_ratio * 55 + len(cycles) * 4)

        return {
            "cross_entity_fraud_detected": circular_ratio > 0.4,
            "circular_flow_ratio": round(circular_ratio, 3),
            "cycles_detected": [
                {
                    "members": cycle["members"],
                    "length": cycle["length"],
                    "contains_queried_gstin": gstin in cycle["members"],
                    "min_edge_value": cycle["min_edge_value"],
                }
                for cycle in cycles
            ],
            "fraud_ring_members": sorted(cycle_members),
            "cross_entity_score": round(cross_entity_score, 1),
        }

    def build_entity_graph(
        self,
        transactions: List[Dict[str, Any]],
        gstin: str,
        company_name: str = "",
        directors: List[Dict[str, Any]] | None = None,
        entity_graph_service: EntityGraphService | None = None,
    ) -> Dict[str, Any]:
        """
        Build a serializable entity-relationship graph from UPI transactions
        and director data.  Returns nodes + edges suitable for D3/Cytoscape
        rendering on the frontend.
        """
        if entity_graph_service is not None and entity_graph_service.get_outflow_summary(gstin)["counterparties"]:
            G = entity_graph_service.subgraph_for(gstin)
            cycles = [c for c in nx.simple_cycles(G) if len(c) >= 3]
            cycle_node_set = {n for c in cycles for n in c}
            circular_detected = len(cycles) > 0
        elif not transactions:
            return {
                "nodes": [{"id": gstin, "label": company_name or gstin, "type": "company", "risk": "low"}],
                "edges": [],
                "circular_topology_detected": False,
                "risk_summary": "No transaction data available.",
            }
        else:
            # ── Build the transaction graph ──────────────────────
            G = nx.DiGraph()
            for txn in transactions:
                explicit_src = txn.get("src_vpa")
                explicit_dst = txn.get("dst_vpa")
                if explicit_src and explicit_dst:
                    src, dst = explicit_src, explicit_dst
                else:
                    counterparty = txn.get("counterparty_vpa", "UNKNOWN")
                    if txn.get("direction") == "CR":
                        src, dst = counterparty, gstin
                    else:
                        src, dst = gstin, counterparty

                if G.has_edge(src, dst):
                    G[src][dst]["weight"] += txn.get("amount", 0)
                    G[src][dst]["count"] += 1
                else:
                    G.add_edge(src, dst, weight=txn.get("amount", 0), count=1)

            # ── Detect cycles ────────────────────────────────────
            cycles = [c for c in nx.simple_cycles(G) if len(c) >= 3]
            cycle_node_set = {n for c in cycles for n in c}
            circular_detected = len(cycles) > 0

        # ── Classify nodes ───────────────────────────────────
        def _fmt_inr(v: float) -> str:
            if v >= 1e7:
                return f"₹{v / 1e7:.1f}Cr"
            if v >= 1e5:
                return f"₹{v / 1e5:.0f}L"
            return f"₹{v:,.0f}"

        nodes: List[Dict[str, Any]] = []
        seen_ids = set()

        # Focal company
        nodes.append({
            "id": gstin,
            "label": company_name or gstin,
            "type": "company",
            "risk": "high" if gstin in cycle_node_set else "low",
        })
        seen_ids.add(gstin)

        # Directors (from MCA fixtures or caller-supplied data)
        directors = directors or []
        for d in directors:
            did = d.get("din", d.get("name", "DIR"))
            if did not in seen_ids:
                nodes.append({
                    "id": did,
                    "label": d.get("name", did),
                    "type": "director",
                    "risk": "high" if d.get("connected_entities", 0) > 3 else "medium",
                })
                seen_ids.add(did)

        # Counterparty / linked MSME nodes
        for node in G.nodes():
            if node in seen_ids:
                continue
            is_linked_msme = node.startswith("MSME_LINK_")
            nodes.append({
                "id": node,
                "label": node.replace("MSME_LINK_", "Shell Co. ") if is_linked_msme else node,
                "type": "company" if is_linked_msme else "counterparty",
                "risk": "high" if node in cycle_node_set else "low",
            })
            seen_ids.add(node)

        # ── Build edges ──────────────────────────────────────
        edges: List[Dict[str, Any]] = []

        # Director → company edges
        for d in directors:
            did = d.get("din", d.get("name", "DIR"))
            edges.append({"source": did, "target": gstin, "label": "Director", "type": "director"})
            # If director controls shell entities, link them too
            for node in G.nodes():
                if node.startswith("MSME_LINK_") and node in seen_ids:
                    edges.append({"source": did, "target": node, "label": "Director", "type": "director"})

        # UPI flow edges (aggregate by node pair, top flows only)
        edge_list = sorted(G.edges(data=True), key=lambda e: e[2]["weight"], reverse=True)
        for src, dst, data in edge_list[:30]:  # Cap at 30 for readability
            edges.append({
                "source": src,
                "target": dst,
                "label": f"UPI {_fmt_inr(data['weight'])}",
                "type": "upi_cycle" if (src in cycle_node_set and dst in cycle_node_set) else "upi_flow",
                "weight": round(data["weight"]),
                "txn_count": data.get("count", data.get("txn_count", 0)),
            })

        # ── Risk summary ─────────────────────────────────────
        shell_count = sum(1 for n in nodes if n["type"] == "company" and n["id"] != gstin and n["risk"] == "high")
        total_cycle_volume = sum(
            G[c[i]][c[(i + 1) % len(c)]]["weight"]
            for c in cycles
            for i in range(len(c))
        ) if cycles else 0
        director_count = sum(1 for n in nodes if n["type"] == "director")

        if circular_detected:
            risk_summary = (
                f"Director controls {shell_count + 1} entities. "
                f"{shell_count} shell companies rotating {_fmt_inr(total_cycle_volume)} in circular UPI flows."
            )
        elif shell_count > 0:
            risk_summary = f"{director_count} director(s) linked to {shell_count} external entities. No circular flows detected."
        else:
            risk_summary = "Clean entity graph. No shell companies or circular transaction patterns detected."

        return {
            "nodes": nodes,
            "edges": edges,
            "circular_topology_detected": circular_detected,
            "cycle_count": len(cycles),
            "cycle_nodes": sorted(cycle_node_set),
            "graph_stats": {
                "nodes": len(nodes),
                "edges": len(edges),
                "density": round(nx.density(G), 4) if G.number_of_nodes() > 1 else 0,
            },
            "risk_summary": risk_summary,
        }

    def build_networkx_entity_graph(
        self,
        transactions: List[Dict[str, Any]],
        gstin: str,
        company_name: str = "",
        directors: List[Dict[str, Any]] | None = None,
        risk_score: int | None = None,
        entity_graph_service: EntityGraphService | None = None,
    ) -> tuple[nx.DiGraph, List[List[str]]]:
        """Return a directed entity graph plus detected cycles for Cytoscape serialization."""
        directors = directors or []

        if entity_graph_service is not None and entity_graph_service.get_outflow_summary(gstin)["counterparties"]:
            G = entity_graph_service.subgraph_for(gstin)
            for node_id in list(G.nodes()):
                G.nodes[node_id].setdefault("type", "gstin")
                G.nodes[node_id].setdefault("name", company_name if node_id == gstin else node_id)
            for source, target, attrs in G.edges(data=True):
                amount = float(attrs.get("amount", attrs.get("weight", 0.0)) or 0.0)
                attrs["amount"] = amount
                attrs.setdefault("type", "upi_flow")
                attrs.setdefault("label", f"UPI ₹{int(amount / 100000)}L" if amount else "UPI flow")
            if gstin not in G:
                G.add_node(
                    gstin,
                    type="gstin",
                    name=company_name or gstin,
                    risk_score=risk_score,
                    director_count=len(directors),
                )
        else:
            G = nx.DiGraph()
            G.add_node(
                gstin,
                type="gstin",
                name=company_name or gstin,
                risk_score=risk_score,
                director_count=len(directors),
            )

            for transaction in transactions:
                explicit_src = transaction.get("src_vpa")
                explicit_dst = transaction.get("dst_vpa")
                if explicit_src and explicit_dst:
                    source, target = explicit_src, explicit_dst
                else:
                    counterparty = transaction.get("counterparty_vpa", "UNKNOWN")
                    if transaction.get("direction") == "CR":
                        source, target = counterparty, gstin
                    else:
                        source, target = gstin, counterparty

                for node_id in (source, target):
                    if node_id not in G:
                        G.add_node(node_id, type="gstin", name=node_id)

                edge_type = "upi_flow"
                amount = float(transaction.get("amount", 0) or 0)
                label = f"UPI ₹{int(amount / 100000)}L" if amount else "UPI flow"
                if G.has_edge(source, target):
                    G[source][target]["amount"] += amount
                else:
                    G.add_edge(source, target, type=edge_type, amount=amount, label=label)

        G.nodes[gstin]["type"] = "gstin"
        G.nodes[gstin]["name"] = company_name or gstin
        G.nodes[gstin]["risk_score"] = risk_score
        G.nodes[gstin]["director_count"] = len(directors)

        for director in directors:
            director_id = f"director_{director.get('din', director.get('name', 'unknown')).lower()}"
            G.add_node(
                director_id,
                type="director",
                name=director.get("name", director_id),
                company_count=director.get("connected_entities", 1),
            )
            G.add_edge(director_id, gstin, type="director_of", label="Director of")

        cycles = [cycle for cycle in nx.simple_cycles(G) if len(cycle) >= 3 and gstin in cycle]
        return G, cycles

    def _empty_result(self) -> Dict[str, Any]:
        return {
            "circular_risk": "LOW",
            "risk_score": 0,
            "cycles_found": [],
            "cycle_count": 0,
            "single_entity_cycles": 0,
            "round_amount_alert": False,
            "round_amount_pct": 0,
            "bounceback_pairs": [],
            "bounceback_count": 0,
            "counterparty_count": 0,
            "linked_msme_nodes": [],
            "linked_msme_count": 0,
            "total_volume": 0,
            "volume_per_counterparty": 0,
            "cross_entity_fraud_detected": False,
            "circular_flow_ratio": 0.0,
            "fraud_ring_members": [],
            "cycles_detected": [],
            "cross_entity_score": 0.0,
            "single_entity_score": 0.0,
            "heuristics_score": 0.0,
            "graph_stats": {"nodes": 0, "edges": 0, "density": 0},
        }
