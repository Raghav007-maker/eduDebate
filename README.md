# EduDebate 🎓
> An AI-powered Socratic learning and revision assistant for UPSC Polity & Indian Civics, featuring a multi-agent debate workflow, live UI event streaming, SQLite persistence, and real-time MCP verification.

EduDebate is built for the Kaggle "AI Agents: Intensive Vibe Coding Capstone Project" hackathon.

---

## 🚀 Key Features

1. **Multi-Agent Socratic Debate Flow**:
   - **Research Agent (`gemini-2.5-flash-lite`)**: Deconstructs questions into sub-claims, retrieves initial context using Wikipedia MCP.
   - **Devil's Advocate (`gemini-2.5-flash`)**: Challenges interpretation and surfaces underrepresented views (minority opinions, political science perspectives) without contesting settled facts.
   - **Fact Checker (`gemini-2.5-flash`)**: Extracts assertions and verifies them using the Wikipedia search MCP tool. Yields structured JSON.
   - **Synthesis Agent (`gemini-2.5-flash`)**: Synthesizes the debate into a single exam-grade "Study Note" revision card.
2. **Pre-LLM Security Screening**:
   - Filters out prompt injection patterns (e.g., instructions override attempts).
   - Rejects empty, single-word, or low-effort queries.
   - Logs security rejections locally in `logs/security_rejections.log`.
3. **SQLite History Persistence**:
   - Stores user questions, agent outputs, and verdicts locally.
   - Sidebar history enables students to reload past debates with one click.
4. **Vibrant & Responsive UI**:
   - Glassmorphic UI styled with custom CSS.
   - Live streaming updates of each agent as it runs.
   - Color-coded verdict badges (Verified, Unverified, Disputed) for claims.

---

## 🛠️ Tech Stack
- **Backend**: Python 3.11+, Google ADK 2.0 (Agent Development Kit), FastMCP
- **Frontend**: Streamlit
- **Database**: SQLite3
- **APIs**: Gemini 2.5, Wikipedia Web Search API via `wikipedia-api`

---

## 📂 Project Structure
```
EduDebate/
├── data/                  # SQLite databases
├── logs/                  # Security rejection logs
├── src/
│   ├── agents/
│   │   └── workflow.py    # ADK SequentialAgent pipeline setup
│   ├── lib/
│   │   ├── db.py          # SQLite database connection & CRUD operations
│   │   ├── mcp_client.py  # Spawns MCP server subprocess & queries tool
│   │   └── security.py    # Pre-LLM validation and logs
│   ├── prompts/           # Specialized agent system instructions
│   │   ├── research_agent.py
│   │   ├── devils_advocate.py
│   │   ├── fact_check.py
│   │   └── synthesis.py
│   ├── test_manual.py      # Manual workflow mock/real validation
│   └── test_mcp_fallback.py# Verification of MCP server/client interface
├── app.py                 # Premium Streamlit UI entrypoint
├── mcp_server.py          # FastMCP Wikipedia Search tool server
├── requirements.txt       # Project dependencies
└── README.md
```

---

## ⚡ Setup & Run Instructions

### 1. Prerequisites
- Python 3.11 or higher
- A Gemini API Key from Google AI Studio

### 2. Installation
Clone the repository and install dependencies in a virtual environment:
```bash
# Clone the repository
git clone https://github.com/Raghav007-maker/eduDebate.git
cd eduDebate

# Setup virtual environment
python -m venv venv
./venv/Scripts/activate  # On Windows PowerShell
# source venv/bin/activate # On Unix/macOS

# Install requirements
pip install -r requirements.txt
```

### 3. Environment Variable Configuration
Create a `.env` file in the root directory:
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
```

### 4. Running the Application
Launch the Streamlit interface:
```bash
streamlit run app.py
```
Open `http://localhost:8501` in your browser.

---

## 🧪 Verification & Testing
To manually test the MCP client fallback or run mocked/real agent workflows via terminal:
```bash
# Test MCP Wikipedia search & fallback:
python src/test_mcp_fallback.py

# Test sequential workflow (runs mock mode if GEMINI_API_KEY is not set):
python src/test_manual.py
```
