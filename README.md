# OpsMate: The Autonomous SRE Teammate 🚀

OpsMate is an intelligent, agentic Site Reliability Engineering (SRE) assistant powered by Google's **Gemini 2.5/3.8 Flash** models and **Vertex AI**. 

Instead of replacing engineers, OpsMate acts as a brilliant teammate in the war room. When a production incident occurs, OpsMate autonomously pulls live telemetry, analyzes application logs, and cross-references recent code deployments to determine the root cause in seconds—drastically reducing Mean Time to Resolution (MTTR).

## ✨ Features

- **Real-Time Telemetry Streaming:** OpsMate reads live degradation metrics (Error Rates, P99 Latency).
- **Agentic Tool Calling:** Built on the `google-genai` SDK, OpsMate has direct, programmatic access to:
  - `get_live_metrics`: Polls current service health.
  - `search_logs`: Greps through simulated production logs.
  - `get_commit_diff`: Inspects recent pull requests and git diffs for breaking changes.
- **Chaos Engineering Engine:** A built-in incident injector that simulates real-world outages (e.g., Database connection pool exhaustion caused by an unindexed SQL query) for live demonstrations.
- **Human-in-the-Loop Remediation:** Proposes rollbacks or infrastructure fixes and waits for explicit engineer approval before executing.

## 🛠️ Technology Stack

- **AI Engine:** Google Gemini (via `google-genai` SDK) routed through Vertex AI Enterprise endpoints.
- **Authentication:** Google Cloud Application Default Credentials (ADC) for enterprise-grade security.
- **Backend:** Python / FastAPI with asynchronous text streaming.
- **Frontend:** React (Vite) + Vanilla CSS (Custom modern styling, Glassmorphism, CSS Grid).

## 🚀 Running Locally

1. **Clone the repository**
   ```bash
   git clone https://github.com/somyxpxthxk/opsmate-sre-agent.git
   cd opsmate-sre-agent
   ```

2. **Backend Setup**
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Environment Configuration**
   Create a `.env` file in the root directory:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key
   GOOGLE_CLOUD_PROJECT=your_gcp_project_id
   GOOGLE_GENAI_USE_VERTEXAI=true
   GOOGLE_CLOUD_LOCATION=global
   ```

4. **Start the Backend**
   ```bash
   python server.py
   ```

5. **Start the Frontend**
   Open a new terminal window:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

## 🎯 The Hackathon Demo Scenario
1. Open the OpsMate UI.
2. Click **"Bad Deployment"** in the left rail to trigger the Chaos Engine.
3. OpsMate will automatically detect the anomaly and begin an investigation.
4. Watch as OpsMate queries logs and git commits to discover that **PR #892** introduced an unindexed SQL query, exhausting the connection pool!
