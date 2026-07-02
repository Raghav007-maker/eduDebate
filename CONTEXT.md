# EduDebate — Context & Constraints

This document acts as the source of truth for the project constraints, architectures, and design standards to ensure strict compliance.

## Project Scope
- Scoped strictly to **UPSC Polity & Indian Civics** topics. No general knowledge or other exam subjects.
- Reframe short inputs to expand into a query rather than reject them.
- Only reject empty or malicious/injection inputs.

## Agent Architecture (ADK 2.0)
- Configured using `LlmAgent` and `SequentialAgent` pipelines.
- Multi-agent workflow:
  1. `research_agent`: (`gemini-2.5-flash-lite`) Decomposes questions and fetches Wikipedia search results. Exposes tool usage via MCP.
  2. `devils_advocate`: (`gemini-2.5-flash`) Challenges emphasis, interpretation, and completeness. Doesn't contest settled facts.
  3. `fact_check`: (`gemini-2.5-flash`) Cross-references specific factual assertions against Wikipedia search results via MCP. Outputs structured JSON.
  4. `synthesis`: (`gemini-2.5-flash`) Synthesizes final revision study note.
- Output routing uses ADK's `output_key` and `{placeholder}` bindings in sequential chain.

## Model Assignments
- `gemini-2.5-flash-lite`: `research_agent`
- `gemini-2.5-flash`: `devils_advocate`, `fact_check`, `synthesis`

## MCP Tool (Wikipedia Search)
- Run a Python MCP server subprocess (`mcp_server.py`) using `fastmcp` + `wikipedia-api`.
- Client wrapper `src/lib/mcp_client.py` handles subprocess lifecycle, health check, and a graceful try-catch fallback. If the server fails/dies, agents degrade gracefully (e.g. marking fact check as "Unverified due to source unavailability") instead of crashing.

## Security & Input Screening
- Obvious injection patterns (e.g., "ignore previous instructions") must be rejected.
- Reject empty inputs.
- Log rejections to `logs/security_rejections.log`.

## Streamlit UI & Event-driven updates
- Live reveal uses actual ADK event streaming/callbacks. Do not simulate with `time.sleep()`.
- Distinct study note revision cards and color-coded badges for verified/unverified/disputed assertions.
- SQLite persistence tracks all debate runs and enables history retrieval from a sidebar.
