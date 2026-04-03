from typing import List, Dict, Any
from app.models.gstr import GSTR2A, GSTR3B
import networkx as nx

class GSTReconciliationService:
    @staticmethod
    def reconcile_2a_vs_3b(gstr2a_list: List[GSTR2A], gstr3b_list: List[GSTR3B]) -> Dict[str, Any]:
        """
        Compute GSTR-2A vs 3B ITC variance per period.
        Variance > 15% flags CIRCULAR_TRADING_RISK (HIGH); 8–15% flags ITC_MISMATCH_MODERATE.
        """
        results = {}
        flags = []
        
        # Aggregate 2A ITC
        itc_2a_by_period = {}
        for ret in gstr2a_list:
            total_itc = 0.0
            if ret.b2b:
                for b2b in ret.b2b:
                    for inv in b2b.inv:
                        for itm in inv.itms:
                            total_itc += itm.iamt + itm.camt + itm.samt
            itc_2a_by_period[ret.fp] = total_itc
            
        # Aggregate 3B ITC
        itc_3b_by_period = {}
        for ret in gstr3b_list:
            total_itc = 0.0
            if ret.itc_elg and ret.itc_elg.itc_avl:
                for det in ret.itc_elg.itc_avl:
                    total_itc += det.iamt + det.camt + det.samt
            itc_3b_by_period[ret.ret_period] = total_itc
            
        for period, itc_2a in itc_2a_by_period.items():
            itc_3b = itc_3b_by_period.get(period, 0.0)
            if itc_2a == 0:
                variance = 1.0 if itc_3b > 0 else 0.0
            else:
                variance = abs(itc_3b - itc_2a) / itc_2a
                
            variance_pct = variance * 100
            flag = None
            if variance_pct > 15:
                flag = "CIRCULAR_TRADING_RISK (HIGH)"
            elif variance_pct > 8:
                flag = "ITC_MISMATCH_MODERATE"
                
            if flag:
                flags.append({"period": period, "variance_pct": variance_pct, "flag": flag})
                
            results[period] = {
                "itc_2a": itc_2a,
                "itc_3b": itc_3b,
                "variance_pct": variance_pct
            }
            
        return {"reconciliation": results, "flags": flags}

    @staticmethod
    def detect_circular_trading(invoices, threshold: float = 10_000_00) -> List[List[str]]:
        """
        Build a directed transaction graph from GST invoices and calculate cycles.
        Any cycle > threshold (e.g. 10 Lakhs) is flagged.
        invoices: [{"from": "GSTIN_A", "to": "GSTIN_B", "value": 1500000}]
        """
        G = nx.DiGraph()
        
        for inv in invoices:
            u, v, w = inv['from'], inv['to'], inv['value']
            if G.has_edge(u, v):
                G[u][v]['weight'] += w
            else:
                G.add_edge(u, v, weight=w)
                
        # Detect cycles
        cycles = list(nx.simple_cycles(G))
        high_value_cycles = []
        
        for cycle in cycles:
            # Check edge weights in the cycle
            cycle_weight = min(G[cycle[i]][cycle[(i+1)%len(cycle)]]['weight'] for i in range(len(cycle)))
            if cycle_weight > threshold:
                high_value_cycles.append(cycle)
                
        return high_value_cycles
