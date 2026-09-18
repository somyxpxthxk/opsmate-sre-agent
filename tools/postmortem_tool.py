"""
Agent Tools: Postmortem Generator
Provides the agent ability to fetch the incident timeline and generate a summary.
"""

from infrastructure.metrics_store import MetricsStore

def get_incident_timeline() -> str:
    """Fetch the chronological timeline of events for the current incident."""
    store = MetricsStore()
    
    if not store.incident_timeline:
        return "No incident events recorded in the current session."
        
    lines = ["Incident Timeline:"]
    for event in store.incident_timeline:
        lines.append(f"[{event['timestamp']}] (T+{event['elapsed_sec']}s) [{event['type']}] {event['detail']}")
        
    return "\n".join(lines)

def draft_postmortem_summary() -> str:
    """Generate a structured draft postmortem based on the metrics store state and timeline."""
    store = MetricsStore()
    
    if not store.incident_timeline:
        return "Cannot generate postmortem: No incident data found."
        
    timeline_str = get_incident_timeline()
    
    template = f"""# Incident Postmortem Draft

## 1. Summary
[Agent: Fill in brief summary of the incident and impact based on the timeline]

## 2. Timeline
{timeline_str}

## 3. Root Cause
[Agent: Detail the technical root cause discovered during investigation]

## 4. Resolution
[Agent: Describe the remediation steps taken to restore service]

## 5. Action Items
[Agent: Propose 2-3 preventative measures to avoid recurrence]
"""
    return template
