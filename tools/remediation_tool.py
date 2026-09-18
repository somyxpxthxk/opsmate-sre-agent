"""
Agent Tools: Remediation & Auto-Fixes
Provides the agent ability to execute resolutions against the infrastructure.
"""

from infrastructure.chaos_engine import resolve_chaos

def execute_remediation(scenario_or_action: str, **kwargs) -> str:
    """
    Execute a remediation action to fix an ongoing incident.
    Valid actions: 
      - 'bank_node_timeout' (takes kwarg reroute_to='HDFC')
      - 'bad_deployment' (rolls back the latest PR)
      - 'auth_token_expiry' (rotates JWT keys)
      - 'settlement_deadlock' (clears DB locks and restarts service)
      - 'memory_leak' (restarts the merchant service)
    """
    result = resolve_chaos(scenario_or_action, **kwargs)
    
    if "error" in result:
        return f"Remediation Failed: {result['error']}"
        
    return (
        f"Remediation Executed Successfully:\n"
        f"Action: {result.get('action', scenario_or_action)}\n"
        f"Detail: {result.get('detail', 'System recovered.')}\n"
        f"Status: {result['status']}"
    )
