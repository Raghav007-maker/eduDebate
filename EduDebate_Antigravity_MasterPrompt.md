# EduDebate — Antigravity Master Build Prompt

**How to use this:** Paste the entire block below into Antigravity's chat as your first message in a fresh workspace. Antigravity will scaffold the project, write the CONTEXT.md, and build in phases. Don't paste it into Antigravity CLI in pieces — give it the whole spec at once so it can plan before it writes code (this is the Spec-Driven Development pattern Day 5 of the course teaches: treat this spec as the source of truth, not the code).

Assumptions baked into this prompt (change these before pasting if wrong):
- Scope is locked to **UPSC Polity & Indian Civics** topics only — not general knowledge. Trying to support every subject in 8 days is how these projects die.
- Backend: Python + ADK 2.0 (graph workflow API) + Gemini 2.5 Flash (cheap, fast, good enough for this — don't burn quota on Pro during dev).
- Frontend: Streamlit (matches your stack experience from FreshEye AI / Flight Delay project).
- Memory: SQLite, not Postgres. You don't need a real database for an 8-day demo.
- Fact-checking source: live Wikipedia API via `wikipedia-api` Python package, not preloaded snapshots — a live lookup is more convincing in a judged demo than static data.
- Deployment target: Cloud Run, because that's literally what the course's own Day 1 and Day 5 labs deploy to, and judges grading "Deployability" will recognize the pattern.

---

```
ROLE
You are acting as a senior software architect and pair programmer building a production-grade
multi-agent application called EduDebate for the Kaggle "AI Agents: Intensive Vibe Coding
Capstone Project" hackathon. I am a CS student with full-stack and ML experience
(FastAPI, TensorFlow, XGBoost, YOLOv8n) but limited prior exposure to ADK and MCP. Explain
non-obvious architectural decisions briefly as you make them, but do not over-explain basic
Python or Streamlit syntax.

PROJECT CONTEXT
EduDebate is a multi-agent Socratic learning tool for Indian competitive exam students
(scope: UPSC Polity & Indian Civics only). Instead of a single LLM answer, a student submits
a question and watches four specialized agents process it in sequence, visible live in the UI,
before a final synthesized study note is produced.

The core insight: students preparing for UPSC don't just need an answer, they need to see
where the answer is contested, what the strongest counter-argument is, and which claims are
actually verifiable. A single chatbot response hides all of that. EduDebate exposes it.

AGENT ARCHITECTURE (build as an ADK 2.0 graph workflow, not a simple chain)
1. Research Agent — takes the raw question, decomposes it into 2-4 sub-claims, and retrieves
   supporting context for each via the Wikipedia MCP tool (see MCP section below). Produces a
   structured initial position with citations.
2. Devil's Advocate Agent — does NOT contest settled facts (dates, constitutional articles,
   names). It challenges interpretation, emphasis, and completeness: what perspective is
   underrepresented in the Research Agent's framing? For a polity question this usually means
   surfacing a competing historiographical or political-science interpretation, not inventing
   a counter-fact. Bake this constraint into its system prompt explicitly or it will produce
   garbage contrarian noise instead of useful tension.
3. Fact-Check Agent — runs independently against both the Research Agent's and Devil's
   Advocate's claims. Cross-references specific factual assertions (dates, names, numbers,
   article references) against the Wikipedia MCP tool. Outputs a per-claim verdict: Verified /
   Unverified / Disputed, with a one-line reason. This agent's output must be structured JSON,
   not prose, so the UI can render verdict badges.
4. Synthesis Agent — takes all three prior outputs and produces a final "study note": a plain-
   language paragraph answer, a 3-bullet "key tensions" section showing where Research and
   Devil's Advocate disagreed, and a "verified facts" list pulled from the Fact-Check Agent.
   This is the only agent whose full output the student needs to walk away with.

Route agent outputs through a shared state object in the ADK graph so each downstream agent
sees the upstream agents' full structured output, not just free text.

MCP REQUIREMENT
Implement a minimal MCP server (or MCP-compatible tool wrapper, whichever Antigravity's
current ADK skill scaffolds by default) that exposes a single `wikipedia_search(query)` tool
backed by the `wikipedia-api` Python package. Both the Research Agent and Fact-Check Agent
must call this tool through MCP, not via a raw inline API call, since the hackathon rubric
explicitly grades MCP Server usage as a separate line item from general tool use.

SECURITY REQUIREMENT (graded separately — do not skip)
Before any user input reaches an agent, run it through a lightweight pre-LLM screen that:
- Strips/flags obvious prompt-injection patterns (e.g. "ignore previous instructions",
  attempts to extract system prompts)
- Rejects empty or single-word low-effort inputs with a friendly UI message instead of
  burning an agent run on them
Log rejected inputs to a local file for the demo (don't silently drop them — show this
working in the video).

MEMORY / SESSION
Use SQLite to persist: each debate run (question, all four agent outputs, timestamp), so a
student can revisit past study notes. Add a simple "My Debates" sidebar in Streamlit that
lists past sessions and reloads them on click. This is what justifies the memory/session
rubric line without needing a real auth system.

UI REQUIREMENTS (Streamlit)
- Question input box at the top, scoped with placeholder text indicating Polity/Civics focus
- A live "debate panel" using `st.status()` or sequential `st.chat_message()` blocks that
  reveal each agent's output as it completes, not all at once — this is the demo's "wow"
  moment, so don't short-circuit it by rendering everything instantly
- Verdict badges (green/yellow/red) for the Fact-Check Agent's per-claim output
- Final "Study Note" card, visually distinct from the debate panel, that the student could
  screenshot and use for revision
- Sidebar: past debates list (from SQLite)

CONSTRAINTS
- No API keys, secrets, or credentials hardcoded anywhere in source files. Use a `.env` file
  pattern with `.env.example` committed instead, and confirm this explicitly before
  finishing each phase.
- Keep the agent prompt templates in separate files (e.g. `prompts/research_agent.py`), not
  inline strings buried in orchestration code — judges read code, and scattered prompt logic
  reads as sloppy.
- Every non-trivial function gets a one-line docstring explaining intent, not just what the
  code does mechanically. Write comments like a developer who understands the system, not
  like auto-generated documentation — no filler phrases, no "this function is responsible
  for handling the logic of," just the actual reasoning.
- Do not scope-creep into supporting other exam subjects, other languages, or user accounts.
  If I ask for any of that mid-build, push back and remind me of the timeline before just
  doing it.

BUILD PHASES (work through these in order, confirm completion of each before moving to the next)
Phase 1 — Scaffold: initialize the project, set up `uv` virtual environment, install
agents-cli and ADK, create the CONTEXT.md file capturing all constraints above so they
persist across the session, set up git.
Phase 2 — Core agent graph: implement all four agents with mocked/stub tool calls first,
verify the graph routes state correctly end-to-end with a hardcoded test question before
touching real APIs.
Phase 3 — MCP integration: wire up the real Wikipedia MCP tool, replace stubs, test against
3 real UPSC Polity questions of varying difficulty.
Phase 4 — Security screen: implement and test the pre-LLM input screen with at least 2
adversarial test inputs (a prompt injection attempt and a junk input).
Phase 5 — SQLite persistence + Streamlit UI: build the live debate panel, verdict badges,
study note card, and past-debates sidebar.
Phase 6 — Polish + deploy: write the README.md (problem, solution, architecture diagram
description, setup instructions), deploy to Cloud Run, and do a final pass removing any
debug prints or commented-out dead code.

At the end of Phase 6, generate a short checklist confirming: no hardcoded keys, README
exists, all 4 agents demonstrably run, MCP tool is real (not mocked), security screen is
testable, and the app runs end-to-end on a fresh clone.
```

---

### Framework Breakdown
**Decomposition:** The build is broken into six sequential phases with explicit completion gates, because an 8-day agentic build without phase boundaries tends to drift into polishing the UI before the core agent graph even works end-to-end — this forces Antigravity (and you) to validate the riskiest part first.

**Constraints:** Hard rules on scope, security, secrets, and code structure are stated up front and Antigravity is explicitly told to push back if you ask it to scope-creep mid-build — without this, a vibe-coded project under time pressure naturally bloats past what a judge can read in one sitting.

**Role Assignment:** Framing Antigravity as a senior architect pairing with someone who knows full-stack/ML but not ADK/MCP calibrates its explanations to skip basics you already know while still flagging the non-obvious architectural decisions that actually matter for the judging rubric.
