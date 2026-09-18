"""
OpsMate SRE & Engineering Teammate
===================================
Autonomous agent that handles SRE incidents, investigates root causes,
and communicates with the engineering team via a Slack-like interface.
Using google-genai SDK for Gemini Enterprise.
"""

import os
import sys
import asyncio
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, HttpOptions

# Load our custom tools
from tools.metrics_tool import get_service_metrics, get_all_services_health, get_bank_rail_health
from tools.deployment_tool import get_recent_deployments, get_commit_diff
from tools.blast_radius_tool import analyze_blast_radius
from tools.remediation_tool import execute_remediation
from tools.postmortem_tool import get_incident_timeline, draft_postmortem_summary
from tools.log_tool import read_service_logs, search_all_logs

load_dotenv()

SYSTEM_PROMPT = """\
You are OpsMate, an expert Site Reliability Engineer (SRE) and Engineering teammate at Paytm.
Your mission is to help engineers debug production incidents, analyze blast radius, and execute auto-remediations.

## Your Investigation Methodology
1. **Triage** — Use get_all_services_health() and get_bank_rail_health() to understand what is failing.
2. **Blast Radius** — Use analyze_blast_radius() to understand the business impact of the failure.
3. **Deep Dive** — Use read_service_logs(), search_all_logs(), get_service_metrics(), and get_recent_deployments() to find the root cause.
4. **Remediate** — If you identify a known chaos scenario, execute_remediation() to fix it.
5. **Report** — Use draft_postmortem_summary() when the incident is resolved.

## Communication Style
- You are chatting in a Slack-like interface with a human engineer.
- Be concise, professional, and helpful.
- When you find a root cause, explain it clearly with evidence.
- ALWAYS ask the human engineer before executing a remediation (unless they explicitly tell you to "fix it").
- Use markdown for formatting logs, code diffs, and metrics.
- Keep your messages to 1-2 short paragraphs + bullet points when possible. Don't overwhelm the user with massive walls of text in the chat.
"""

# Native python functions to pass to Gemini
opsmate_tools = [
    get_all_services_health,
    get_bank_rail_health,
    get_service_metrics,
    analyze_blast_radius,
    read_service_logs,
    search_all_logs,
    get_recent_deployments,
    get_commit_diff,
    execute_remediation,
    draft_postmortem_summary
]

import os
import logging
from dotenv import load_dotenv
from google import genai
from google.genai.types import HttpOptions

load_dotenv()

logger = logging.getLogger(__name__)

project = os.environ.get("GOOGLE_CLOUD_PROJECT")
location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")

if not project:
    raise RuntimeError("GOOGLE_CLOUD_PROJECT is not set")

client = genai.Client(
    enterprise=True,
    project=project,
    location=location,
    http_options=HttpOptions(api_version="v1"),
)

logger.info(
    "OpsMate initialized with Agent Platform: project=%s, location=%s",
    project,
    location,
)

def create_opsmate_chat():
    """Returns an async chat session configured with OpsMate tools."""
    config = GenerateContentConfig(
        tools=opsmate_tools,
        system_instruction=SYSTEM_PROMPT,
        temperature=0.0
    )
    return client.aio.chats.create(
        model="gemini-3.8-flash", 
        config=config
    )

if __name__ == "__main__":
    # Test local execution
    async def run_local():
        chat = create_opsmate_chat()
        prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Hi OpsMate, give me a quick health check of the system."
        response = await chat.send_message(prompt)
        print("\nOpsMate:", response.text)
    
    asyncio.run(run_local())
