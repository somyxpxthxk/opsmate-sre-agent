import os
import json
import asyncio
import logging
import traceback
import base64
from typing import Optional, List, Dict, Any

# Cloud Deployment Setup: Decode GCP JSON from Base64 string if present
if "GCP_CREDENTIALS_BASE64" in os.environ:
    creds_json = base64.b64decode(os.environ["GCP_CREDENTIALS_BASE64"]).decode("utf-8")
    with open("cloud_credentials.json", "w") as f:
        f.write(creds_json)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.abspath("cloud_credentials.json")

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agent import create_opsmate_chat
from infrastructure.chaos_engine import inject_chaos, resolve_all
from infrastructure.metrics_store import MetricsStore

app = FastAPI(title="OpsMate Backend")

# Enable CORS for the frontend React app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    session_id: str = "default_session"

# We map session_ids to google.genai ChatSession objects
_sessions: Dict[str, Any] = {}

@app.post("/api/chat")
async def chat_endpoint(req: ChatRequest):
    """
    Streaming chat endpoint for the custom React UI.
    Receives message history and streams back OpsMate's response.
    """
    session_id = req.session_id
    
    # Get the latest user message
    user_message = req.messages[-1].content
    
    # Initialize chat session if it doesn't exist for this session_id
    if session_id not in _sessions:
        _sessions[session_id] = create_opsmate_chat()
        
    chat = _sessions[session_id]

    async def event_stream():
        max_retries = 3
        retry_delay = 10 # Start with 10 seconds wait since GCP quota recovers per minute
        
        for attempt in range(max_retries):
            try:
                # Use send_message (non-streaming) so the SDK can automatically execute tools
                # like get_all_services_health in the background before giving the final answer!
                response = await chat.send_message(user_message)
                
                # Yield the entire text at once
                if response.text:
                    yield f"data: {json.dumps({'text': response.text})}\n\n"
                        
                yield "data: [DONE]\n\n"
                return # Success! Exit the generator
                
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "Resource exhausted" in error_str:
                    if attempt < max_retries - 1:
                        logging.warning(f"Rate limited. Retrying in {retry_delay}s... (Attempt {attempt+1}/{max_retries})")
                        # Send a friendly message to the UI so the user knows it's waiting
                        wait_msg = f"\n\n*[Rate limited by Google Cloud Trial Quota... pausing for {retry_delay} seconds to recover]*\n\n"
                        yield f"data: {json.dumps({'text': wait_msg})}\n\n"
                        
                        await asyncio.sleep(retry_delay)
                        retry_delay += 10 # Wait longer on next failure (10s, 20s, 30s)
                        continue # Retry the loop
                
                # If we exhausted retries or it's a different error
                logging.error(f"Error during chat generation: {error_str}")
                traceback.print_exc()
                yield f"data: {json.dumps({'error': error_str})}\n\n"
                yield "data: [DONE]\n\n"
                return

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/chaos/{scenario}")
def trigger_chaos(scenario: str):
    """Trigger a specific incident scenario for the demo."""
    result = inject_chaos(scenario)
    return result

@app.post("/api/resolve")
def resolve_all_chaos():
    """Reset the infrastructure to a healthy state."""
    result = resolve_all()
    # Reset agent memory so it forgets the past incident
    global _sessions
    _sessions = {}
    return result

@app.get("/api/metrics")
def get_dashboard_metrics():
    """Get real-time metrics for the War Room Dashboard UI."""
    store = MetricsStore()
    return {
        "services": store.get_all_services_summary(),
        "bank_rails": store.get_bank_rails_summary(),
        "incident_timeline": store.incident_timeline
    }

if __name__ == "__main__":
    import uvicorn
    # reload=False: chaos writes logs/source files; watching those restarts the
    # process, wipes MetricsStore, and kills in-flight Gemini chats.
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
