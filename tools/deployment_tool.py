"""
Agent Tools: Deployment & Git History
Provides the agent access to recent deployments and git commits.
"""

import os
import json

DATA_FILE = os.path.join(os.path.dirname(__file__), "..", "infrastructure", "mock_data", "git_history.json")

def _load_git_history():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def get_recent_deployments(service_name: str = None, limit: int = 3) -> str:
    """Fetch recent git commits/deployments, optionally filtered by service name."""
    commits = _load_git_history()
    
    if service_name:
        commits = [c for c in commits if c["service"] == service_name]
        
    commits = commits[:limit]
    
    if not commits:
        return f"No recent deployments found for {service_name or 'any service'}."
    
    lines = [f"Recent Deployments{' for ' + service_name if service_name else ''}:"]
    for c in commits:
        lines.append(f"• Commit {c['commit_hash']} (PR #{c['pr_number']}) by {c['author']} at {c['timestamp']}")
        lines.append(f"  Service: {c['service']}")
        lines.append(f"  Message: {c['message']}")
        lines.append(f"  Files Changed: {', '.join(c['files_changed'])}")
        lines.append(f"  Summary: {c['diff_summary']}")
        lines.append("")
        
    return "\n".join(lines)

def get_commit_diff(commit_hash: str) -> str:
    """Get the specific code diff for a given commit hash."""
    commits = _load_git_history()
    
    for c in commits:
        if c["commit_hash"] == commit_hash or str(c["pr_number"]) == str(commit_hash):
            return (
                f"Diff for Commit {c['commit_hash']} (PR #{c['pr_number']}):\n"
                f"Message: {c['message']}\n"
                f"Files: {', '.join(c['files_changed'])}\n"
                f"\n```diff\n{c['diff_snippet']}\n```"
            )
            
    return f"Error: Commit or PR {commit_hash} not found."
