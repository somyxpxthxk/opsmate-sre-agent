"""
Agent Tools: Blast Radius & Impact Analysis
Provides the agent ability to calculate business impact of ongoing incidents.
"""

import os
import json
from infrastructure.metrics_store import MetricsStore

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "infrastructure", "mock_data", "merchants.json")

def _load_merchants():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def analyze_blast_radius(incident_type: str, parameter: str = None) -> str:
    """
    Calculate the business impact (merchants affected, GMV at risk).
    incident_type can be 'bank_rail_down' or 'service_down'.
    parameter should be the bank code (e.g., 'AXIS') or service name.
    """
    merchants = _load_merchants()
    store = MetricsStore()
    
    affected = []
    
    if incident_type == "bank_rail_down" and parameter:
        affected = [m for m in merchants if m["primary_bank_rail"] == parameter]
        rail = store.bank_rails.get(parameter)
        traffic_weight = rail.traffic_weight_pct if rail else "Unknown"
        
        if not affected:
            return f"No merchants explicitly mapped to {parameter}, but {traffic_weight}% of general traffic is at risk."
            
        total_vol = sum(m["daily_txn_volume_inr"] for m in affected)
        
        lines = [
            f"Blast Radius Analysis: {parameter} Bank Rail Outage",
            f"Affected Merchants (Primary Routing): {len(affected)} / {len(merchants)} total",
            f"Daily GMV at Risk: ₹{total_vol:,}",
            f"General Traffic Weight: {traffic_weight}% of all UPI transactions",
            "",
            "Top Affected Merchants:"
        ]
        
        # Sort by volume
        affected.sort(key=lambda x: x["daily_txn_volume_inr"], reverse=True)
        for m in affected[:5]:
            lines.append(f"• {m['name']} ({m['mid']}): ₹{m['daily_txn_volume_inr']:,}/day")
            
        return "\n".join(lines)
        
    elif incident_type == "service_down":
        total_vol = sum(m["daily_txn_volume_inr"] for m in merchants)
        return (
            f"Blast Radius Analysis: {parameter or 'Core Service'} Outage\n"
            f"CRITICAL: 100% of traffic affected.\n"
            f"Total Daily GMV at Risk: ₹{total_vol:,}\n"
            f"Active Merchants Affected: {len(merchants)}"
        )
        
    return "Unknown incident type for blast radius analysis. Use 'bank_rail_down' or 'service_down'."
