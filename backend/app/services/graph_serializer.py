from __future__ import annotations

from typing import Any, Dict, List

import networkx as nx


NODE_COLORS = {
    "gstin_queried": "#ef4444",
    "gstin_cycle": "#dc2626",
    "gstin_connected": "#475569",
    "director": "#f59e0b",
    "cluster": "#7c3aed",
}

EDGE_COLORS = {
    "director_of": "#f59e0b",
    "common_promoter": "#a78bfa",
    "upi_flow": "#2563eb",
    "eway_flow": "#10b981",
    "cycle_member": "#ef4444",
}


def serialize_graph(
    G: nx.DiGraph,
    queried_gstin: str,
    detected_cycles: List[List[str]],
) -> Dict[str, Any]:
    cycle_node_set = {node for cycle in detected_cycles for node in cycle}
    cycle_edge_set = set()
    for cycle in detected_cycles:
        for idx in range(len(cycle)):
            source = cycle[idx]
            target = cycle[(idx + 1) % len(cycle)]
            cycle_edge_set.add((source, target))
            cycle_edge_set.add((target, source))

    nodes = []
    for node_id, attrs in G.nodes(data=True):
        node_type = attrs.get("type", "gstin")
        if node_id == queried_gstin:
            color = NODE_COLORS["gstin_queried"]
            size = 60
        elif node_id in cycle_node_set and node_type == "gstin":
            color = NODE_COLORS["gstin_cycle"]
            size = 45
        elif node_type == "director":
            color = NODE_COLORS["director"]
            size = 40
        elif node_type == "cluster":
            color = NODE_COLORS["cluster"]
            size = 42
        else:
            color = NODE_COLORS["gstin_connected"]
            size = 35

        display_label = (
            attrs.get("name", node_id)
            if node_id == queried_gstin or node_type == "director"
            else f"****{node_id[-6:]}"
        )
        nodes.append(
            {
                "data": {
                    "id": node_id,
                    "label": display_label,
                    "type": node_type,
                    "color": color,
                    "size": size,
                    "in_cycle": node_id in cycle_node_set,
                    "is_queried": node_id == queried_gstin,
                    "gstin": node_id if node_type == "gstin" else None,
                    "risk_score": attrs.get("risk_score"),
                    "entity_name": attrs.get("name", "Unknown"),
                    "director_count": attrs.get("director_count"),
                    "company_count": attrs.get("company_count"),
                }
            }
        )

    edges = []
    for idx, (source, target, attrs) in enumerate(G.edges(data=True)):
        edge_type = attrs.get("type", "upi_flow")
        in_cycle = (source, target) in cycle_edge_set
        effective_type = "cycle_member" if in_cycle else edge_type
        amount = attrs.get("amount", 0)
        label = attrs.get("label", "")
        if not label:
            if edge_type == "upi_flow" and amount:
                label = f"UPI ₹{int(amount / 100000)}L"
            elif edge_type == "director_of":
                label = "Director of"
            elif edge_type == "common_promoter":
                label = "Common promoter"
            elif edge_type == "eway_flow" and amount:
                label = f"E-Way ₹{int(amount / 100000)}L"

        edges.append(
            {
                "data": {
                    "id": f"e{idx}_{source}_{target}",
                    "source": source,
                    "target": target,
                    "type": effective_type,
                    "color": EDGE_COLORS.get(effective_type, "#475569"),
                    "width": max(2, min(9, amount / 400000)) if amount else 3,
                    "label": label,
                    "amount": amount,
                    "in_cycle": in_cycle,
                    "arrow": edge_type in {"upi_flow", "eway_flow", "cycle_member"},
                }
            }
        )

    total_cycle_amount = 0
    for cycle in detected_cycles:
        for idx in range(len(cycle)):
            source = cycle[idx]
            target = cycle[(idx + 1) % len(cycle)]
            if G.has_edge(source, target):
                total_cycle_amount += G[source][target].get("amount", 0)

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "queried_gstin": queried_gstin,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "cycles_detected": len(detected_cycles),
            "cycle_paths": [
                [node if node == queried_gstin else f"****{node[-6:]}" for node in cycle]
                for cycle in detected_cycles
            ],
            "total_cycle_amount": total_cycle_amount,
        },
    }
