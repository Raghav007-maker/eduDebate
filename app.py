"""
EduDebate — app.py

Multi-agent Socratic learning tool for UPSC Polity & Indian Civics.
Orchestrates a 4-agent ADK SequentialAgent pipeline via Streamlit with
live per-agent card rendering.

Architecture notes:
- process_events() is the single source of truth for all card rendering.
  Both mock and real paths flow through it — no duplicated render logic.
- execute_debate() only decides whether to apply the mock patch, then
  delegates. It knows nothing about rendering.
- All agent output is HTML-escaped before injection to prevent XSS from
  unexpected model responses.
- asyncio.new_event_loop() is required: ADK's MCP client uses async
  internally even though runner.run() returns a sync generator.
"""

import os
import sys
import asyncio
import json
import re
import uuid
import html as html_lib
from dotenv import load_dotenv
from unittest.mock import patch

import streamlit as st
import google.genai.types as types
import google.adk as adk
from google.adk.sessions import InMemorySessionService

# Ensure src/ is importable from project root regardless of cwd
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import importlib
import src.agents.workflow
import src.lib.security
import src.lib.db
import src.lib.mock

importlib.reload(src.agents.workflow)
importlib.reload(src.lib.security)
importlib.reload(src.lib.db)
importlib.reload(src.lib.mock)

from src.agents.workflow import create_debate_workflow
from src.lib.security import screen_input
from src.lib.db import save_debate, get_past_debates
from src.lib.mock import mock_generate_content_async

load_dotenv()

# Default models
model_lite = "gemini-2.5-flash-lite"
model_standard = "gemini-2.5-flash"

# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="EduDebate — UPSC Polity Socratic Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=Space+Grotesk:wght@400;500;700&display=swap');

.main .block-container { padding-top: 2rem; font-family: 'Outfit', sans-serif; }

/* Base glass card */
.glass-card {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 24px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    margin-bottom: 20px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.glass-card:hover { transform: translateY(-2px); box-shadow: 0 12px 40px rgba(0, 0, 0, 0.15); }

/* Header */
.header-container {
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    color: white;
    padding: 30px;
    border-radius: 12px;
    margin-bottom: 30px;
    text-align: center;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.15);
}
.header-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.8rem;
    font-weight: 700;
    margin-bottom: 5px;
    letter-spacing: -0.5px;
}
.header-subtitle { font-size: 1.1rem; opacity: 0.9; font-weight: 300; }

/* Agent card anatomy */
.agent-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 15px;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}
.agent-name {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 1.1rem;
    font-weight: 600;
}
.agent-badge {
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    white-space: nowrap;
}

/* Per-agent colour themes */
.research-theme  { border-left: 5px solid #00d2ff; }
.research-badge  { background: rgba(0, 210, 255, 0.15); color: #00d2ff; }

.advocate-theme  { border-left: 5px solid #ff7675; }
.advocate-badge  { background: rgba(255, 118, 117, 0.15); color: #ff7675; }

.factcheck-theme { border-left: 5px solid #a29bfe; }
.factcheck-badge { background: rgba(162, 155, 254, 0.15); color: #a29bfe; }

.synthesis-theme {
    background: linear-gradient(145deg, rgba(253, 203, 110, 0.05) 0%, rgba(225, 112, 85, 0.05) 100%);
    border: 2px solid rgba(253, 203, 110, 0.3);
    border-left: 8px solid #fdcb6e;
}
.synthesis-badge { background: rgba(253, 203, 110, 0.15); color: #fdcb6e; }

/* Fact-check verdict rows */
.verdict-card {
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 10px;
    display: flex;
    flex-direction: column;
    gap: 4px;
}
.verdict-verified   { background: rgba(46, 204, 113, 0.1); border-left: 4px solid #2ecc71; }
.verdict-unverified { background: rgba(241, 196, 15, 0.1);  border-left: 4px solid #f1c40f; }
.verdict-disputed   { background: rgba(231, 76, 60, 0.1);   border-left: 4px solid #e74c3c; }

.verdict-lbl {
    font-weight: 700;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.verdict-lbl.verified   { color: #2ecc71; }
.verdict-lbl.unverified { color: #f1c40f; }
.verdict-lbl.disputed   { color: #e74c3c; }

.claim-text  { font-weight: 600; font-size: 0.95rem; }
.reason-text { font-size: 0.85rem; opacity: 0.8; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="header-container">
    <div class="header-title">🎓 EduDebate</div>
    <div class="header-subtitle">
        Multi-Agent Socratic Debate &amp; Study Note Generator
        for UPSC Polity &amp; Indian Civics
    </div>
</div>
""", unsafe_allow_html=True)


# ── Pure helpers ───────────────────────────────────────────────────────────────

def parse_factcheck_json(text: str) -> list:
    """Extract a JSON verdict array from raw or markdown-fenced agent output.

    Returns an empty list if parsing fails — callers must handle the fallback.
    """
    try:
        clean = text.strip()
        # Find the outermost JSON array boundaries to extract it cleanly
        start = clean.find('[')
        end = clean.rfind(']')
        if start != -1 and end != -1 and end > start:
            clean = clean[start:end+1]
        return json.loads(clean)
    except Exception:
        return []


def clean_html(html_str: str) -> str:
    """Strip per-line leading whitespace so Streamlit doesn't treat indented HTML as a fenced code block."""
    return "\n".join(line.strip() for line in html_str.splitlines())


def render_stepper(active_step: int) -> str:
    """Return HTML for the 4-step debate progress bar.

    active_step: 1 = Research running, 2 = Devil's Advocate, 3 = FactCheck,
                 4 = Synthesis, 5 = all complete.
    """
    steps = [
        ("Research",   "Claims gathered"),
        ("Challenge",  "Tensions surfaced"),
        ("Verify",     "Checking claims…"),
        ("Synthesise", "Final note"),
    ]
    html = (
        '<div style="display:flex;align-items:center;gap:4px;padding:10px 16px;'
        'background:rgba(255,255,255,0.03);border-radius:8px;'
        'border:1px solid rgba(255,255,255,0.08);margin-bottom:16px;">'
    )
    for i, (name, sub) in enumerate(steps, 1):
        done   = i < active_step or active_step == 5
        active = i == active_step and active_step != 5
        circle   = "✓" if done else str(i)
        color    = "#2ecc71" if done else ("#00d2ff" if active else "rgba(255,255,255,0.2)")
        sub_text = "Done" if done else (sub if active else "Pending")
        html += (
            f'<div style="display:flex;align-items:center;gap:8px;flex:1;">'
            f'<div style="width:26px;height:26px;border-radius:50%;border:1.5px solid {color};'
            f'display:flex;align-items:center;justify-content:center;font-size:11px;'
            f'font-weight:600;color:{color};flex-shrink:0;">{circle}</div>'
            f'<div style="font-size:11px;color:{color};line-height:1.3;">'
            f'<span style="font-weight:600;display:block;">{name}</span>'
            f'<span style="opacity:0.7;font-size:10px;">{sub_text}</span></div></div>'
        )
        if i < 4:
            div_color = "#2ecc71" if done else "rgba(255,255,255,0.1)"
            html += f'<div style="width:20px;height:1px;background:{div_color};flex-shrink:0;"></div>'
    html += "</div>"
    return html


def render_agent_card(theme: str, badge: str, title: str, body_html: str) -> str:
    """Return a complete glass-card HTML block.

    Centralises card markup so live rendering and historical rendering
    use identical HTML — one place to change layout or styling.
    """
    return clean_html(f"""
    <div class="glass-card {theme}-theme">
        <div class="agent-header">
            <span class="agent-badge {theme}-badge">{badge}</span>
            <span class="agent-name">{title}</span>
        </div>
        {body_html}
    </div>
    """)


def render_factcheck_html(agent_text: str) -> str:
    """Return styled verdict-card HTML from the FactCheck agent's JSON output.

    Falls back to an escaped <pre> block if JSON parsing fails, so
    the UI never shows a blank card or crashes on malformed output.
    """
    claims = parse_factcheck_json(agent_text)
    if claims:
        rows = ""
        for item in claims:
            v   = item.get("verdict", "Unverified").strip().lower()
            cls = "verified" if v == "verified" else ("disputed" if v == "disputed" else "unverified")
            rows += (
                f'<div class="verdict-card verdict-{cls}">'
                f'<div class="verdict-lbl {cls}">{cls}</div>'
                f'<div class="claim-text">'
                f'Claim: &ldquo;{html_lib.escape(item.get("claim", ""))}&rdquo;</div>'
                f'<div class="reason-text">'
                f'Reason: {html_lib.escape(item.get("reason", ""))}</div>'
                f'</div>'
            )
    else:
        # Agent returned prose or malformed JSON — show raw, safely escaped
        rows = f'<pre style="white-space:pre-wrap;">{html_lib.escape(agent_text)}</pre>'

    return render_agent_card(
        "factcheck", "Fact Checker",
        "MCP Wikipedia-sourced Verification Verdicts", rows
    )


# ── Async pipeline ─────────────────────────────────────────────────────────────

async def process_events(events, step_map, stepper_ph, r_card, a_card, f_card, s_card, agent_texts):
    """Iterate ADK runner events and render each agent card live as chunks arrive.

    This is the single rendering path used by both mock and real modes.
    All agent text is HTML-escaped before injection — model output is untrusted.
    """
    async for ev in events:
        author = ev.author

        # Advance stepper to whichever agent just fired
        if author in step_map:
            stepper_ph.markdown(render_stepper(step_map[author]), unsafe_allow_html=True)

        if author not in agent_texts:
            continue

        # Accumulate streamed text chunks from this event
        if ev.content and ev.content.parts:
            for part in ev.content.parts:
                if hasattr(part, "text") and part.text:
                    agent_texts[author] += part.text

        # Escape accumulated text once before any HTML injection
        safe = html_lib.escape(agent_texts[author])

        if author == "ResearchAgent":
            r_card.markdown(
                render_agent_card(
                    "research", "Research Agent",
                    "Initial Deconstruction &amp; Source Citations",
                    f'<div style="white-space:pre-wrap;">{safe}</div>',
                ),
                unsafe_allow_html=True,
            )

        elif author == "DevilsAdvocate":
            a_card.markdown(
                render_agent_card(
                    "advocate", "Devil's Advocate",
                    "Interpretation &amp; Historiographical Challenge",
                    f'<div style="white-space:pre-wrap;">{safe}</div>',
                ),
                unsafe_allow_html=True,
            )

        elif author == "FactCheck":
            # render_factcheck_html handles its own escaping internally
            f_card.markdown(render_factcheck_html(agent_texts[author]), unsafe_allow_html=True)

        elif author == "Synthesis":
            s_card.markdown(
                render_agent_card(
                    "synthesis", "Synthesis Note",
                    "Final UPSC Polity Revision Card",
                    f'<div style="white-space:pre-wrap;">{safe}</div>',
                ),
                unsafe_allow_html=True,
            )


async def execute_debate(
    runner, session_id, new_message, api_mode,
    stepper_ph, r_card, a_card, f_card, s_card, agent_texts
):
    """Apply mock patch when no API key present, then hand off to process_events.

    Keeping the mock/real branching here means process_events stays pure:
    it only knows how to render events, not where they came from.
    """
    step_map = {
        "ResearchAgent": 1,
        "DevilsAdvocate": 2,
        "FactCheck": 3,
        "Synthesis": 4,
    }

    def get_events():
        """Thin wrapper so the same runner.run_async() call is used in both branches."""
        return runner.run_async(
            user_id="streamlit_user",
            session_id=session_id,
            new_message=new_message,
        )

    if not api_mode:
        target = "google.adk.models.google_llm.Gemini.generate_content_async"
        with patch(target, side_effect=mock_generate_content_async, autospec=True):
            await process_events(
                get_events(), step_map,
                stepper_ph, r_card, a_card, f_card, s_card, agent_texts
            )
    else:
        await process_events(
            get_events(), step_map,
            stepper_ph, r_card, a_card, f_card, s_card, agent_texts
        )


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("Settings & History")

    st.subheader("Configuration")
    api_key_input = st.text_input(
        "Gemini API Key",
        type="password",
        value=os.getenv("GEMINI_API_KEY", ""),
        help="Leave blank to run in mock mode with stubbed agent responses.",
    )
    if api_key_input:
        os.environ["GEMINI_API_KEY"] = api_key_input
        api_mode = True
    else:
        api_mode = bool(os.environ.get("GEMINI_API_KEY", "").strip())

    if api_mode:
        st.success("✅ API Key Active — Real LLM Mode")
    else:
        st.warning("⚠️ No API Key — Mock Mode Active")

    st.markdown("---")
    st.subheader("Model Config")
    selected_model_family = st.selectbox(
        "Model Tier",
        options=[
            "Gemini 3.1 Flash-Lite (Recommended - High Quota: 50 RPD / 15 RPM)",
            "Gemini 2.5 Lite (Safe Option - Normal Quota: 20 RPD / 10 RPM)",
            "Gemini 3.5 / 3.1 Mixed (Exceeded for Today - 20 RPD Limit)"
        ],
        index=0,
        help="Select a model tier based on your current Google AI Studio daily quota limits."
    )
    if "2.5" in selected_model_family:
        model_lite = "gemini-2.5-flash-lite"
        model_standard = "gemini-2.5-flash-lite" # Use Lite for standard too to stay in the 10 RPM / 20 RPD bucket
    elif "Mixed" in selected_model_family:
        model_lite = "gemini-3.1-flash-lite"
        model_standard = "gemini-3.5-flash"
    else:
        model_lite = "gemini-3.1-flash-lite"
        model_standard = "gemini-3.1-flash-lite" # Run everything on 3.1 Lite to maximize your 50 RPD quota
    st.subheader("My Debates 📚")

    past_runs      = get_past_debates()
    selected_debate = None

    if past_runs:
        for run in past_runs:
            label = run["question"][:35] + ("…" if len(run["question"]) > 35 else "")
            if st.button(label, key=f"hist_{run['id']}", use_container_width=True):
                selected_debate = run
    else:
        st.info("No past debates yet. Ask your first question!")

    st.markdown("---")
    st.caption("Scope: UPSC Polity & Indian Civics only.")


# ── Session state ──────────────────────────────────────────────────────────────

if "current_debate" not in st.session_state:
    st.session_state.current_debate = None
if "question_input" not in st.session_state:
    st.session_state.question_input = ""

# Sidebar click loads a historical debate into state immediately
if selected_debate:
    st.session_state.current_debate = selected_debate


# ── Question input ─────────────────────────────────────────────────────────────

col_input, col_btn = st.columns([3, 1])
with col_input:
    user_query = st.text_input(
        "Ask a UPSC Polity or Civics question:",
        placeholder="e.g., Explain the significance of the Basic Structure Doctrine.",
        key="question_input",
    )
with col_btn:
    st.write("")
    st.write("")
    submit_button = st.button("Generate Debate", use_container_width=True, type="primary")


# ── Live debate execution ──────────────────────────────────────────────────────

if submit_button and user_query:
    # Clear any previously loaded historical debate so layout is clean
    st.session_state.current_debate = None

    is_safe, screening_msg = screen_input(user_query)
    if not is_safe:
        st.error(screening_msg)
    else:
        st.info(f"Question verified. Starting Socratic debate for: *{screening_msg}*")

        # Build placeholder layout before any agent runs
        stepper_ph = st.empty()
        stepper_ph.markdown(render_stepper(1), unsafe_allow_html=True)

        # Research vs Devil's Advocate side-by-side — visual centrepiece of the demo
        debate_cols = st.columns(2)
        with debate_cols[0]:
            r_card = st.empty()
        with debate_cols[1]:
            a_card = st.empty()
        f_card = st.empty()
        s_card = st.empty()

        agent_texts = {
            "ResearchAgent": "",
            "DevilsAdvocate": "",
            "FactCheck": "",
            "Synthesis": "",
        }

        # Initialise ADK pipeline parameters
        new_message = types.Content(role="user", parts=[types.Part(text=screening_msg)])
        max_retries = 3
        retry_delay = 15
        success = False

        for attempt in range(max_retries):
            # Reset agent texts for a fresh run
            for k in agent_texts:
                agent_texts[k] = ""

            # Re-initialize the workflow, runner and session ID to prevent state pollution
            workflow        = create_debate_workflow(model_lite=model_lite, model_standard=model_standard)
            session_service = InMemorySessionService()
            runner          = adk.Runner(
                agent=workflow,
                session_service=session_service,
                app_name="EduDebate",
                auto_create_session=True,
            )
            session_id = f"session_{uuid.uuid4().hex}"

            try:
                spinner_msg = "Agents are debating… please wait." if attempt == 0 else f"Rate limit hit (429). Retrying attempt {attempt+1}/{max_retries} in {retry_delay}s..."
                with st.spinner(spinner_msg):
                    if attempt > 0:
                        import time
                        time.sleep(retry_delay)

                    # Reset stepper to step 1
                    stepper_ph.markdown(render_stepper(1), unsafe_allow_html=True)

                    # Clear cards from previous failed runs if any
                    r_card.empty()
                    a_card.empty()
                    f_card.empty()
                    s_card.empty()

                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(
                            execute_debate(
                                runner, session_id, new_message, api_mode,
                                stepper_ph, r_card, a_card, f_card, s_card, agent_texts
                            )
                        )
                    finally:
                        loop.close()
                success = True
                break
            except Exception as e:
                err_msg = str(e)
                is_429 = "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "rate limit" in err_msg.lower()
                if is_429 and attempt < max_retries - 1:
                    continue
                else:
                    st.error(f"Debate failed: {e}")
                    # Break out of loop so we don't save a blank entry or reload
                    break

        if success:
            # Mark all steps complete
            stepper_ph.markdown(render_stepper(5), unsafe_allow_html=True)

            save_debate(
                question=screening_msg,
                research_output=agent_texts["ResearchAgent"],
                advocate_output=agent_texts["DevilsAdvocate"],
                factcheck_output=agent_texts["FactCheck"],
                synthesis_output=agent_texts["Synthesis"],
            )

            # Pre-load the freshly saved debate before rerun so the page
            # reloads directly into the historical view, not the blank state
            fresh = get_past_debates()
            if fresh:
                st.session_state.current_debate = fresh[0]

            st.success("Debate complete and saved to your history!")
            st.rerun()


# ── Historical debate view ─────────────────────────────────────────────────────

elif st.session_state.current_debate:
    run = st.session_state.current_debate

    st.markdown(f"### Debate: *{html_lib.escape(run['question'])}*")
    st.caption(f"Saved on {run['timestamp']}")
    st.markdown(render_stepper(5), unsafe_allow_html=True)

    hist_cols = st.columns(2)
    with hist_cols[0]:
        st.markdown(
            render_agent_card(
                "research", "Research Agent",
                "Initial Deconstruction &amp; Source Citations",
                f'<div style="white-space:pre-wrap;">{html_lib.escape(run["research_output"])}</div>',
            ),
            unsafe_allow_html=True,
        )
    with hist_cols[1]:
        st.markdown(
            render_agent_card(
                "advocate", "Devil's Advocate",
                "Interpretation &amp; Historiographical Challenge",
                f'<div style="white-space:pre-wrap;">{html_lib.escape(run["advocate_output"])}</div>',
            ),
            unsafe_allow_html=True,
        )

    st.markdown(render_factcheck_html(run["factcheck_output"]), unsafe_allow_html=True)

    st.markdown(
        render_agent_card(
            "synthesis", "Synthesis Note",
            "Final UPSC Polity Revision Card",
            f'<div style="white-space:pre-wrap;">{html_lib.escape(run["synthesis_output"])}</div>',
        ),
        unsafe_allow_html=True,
    )

    # Export controls for the synthesis study note
    if run["synthesis_output"]:
        st.download_button(
            "⬇ Save note as .txt",
            data=run["synthesis_output"],
            file_name=f"edudebate_{run['question'][:20].replace(' ', '_')}.txt",
            mime="text/plain",
            key="download_btn",
        )
        with st.expander("📋 View raw text to copy"):
            st.code(run["synthesis_output"], language=None)


# ── Empty state — example question chips ──────────────────────────────────────

elif not user_query:
    def select_example(q: str):
        """Pre-fill the text input with a sample question on click."""
        st.session_state.question_input = q

    st.markdown("""
    <div style="text-align:center;padding:30px 0 10px;">
        <div style="font-size:1.1rem;font-weight:600;color:rgba(255,255,255,0.7);
                    margin-bottom:8px;">Try asking about…</div>
    </div>""", unsafe_allow_html=True)

    examples = [
        "Was the Basic Structure Doctrine a judicial overreach?",
        "Explain the Governor's discretionary powers under Article 163.",
        "How did Article 370 reflect asymmetric federalism in India?",
        "Was the 42nd Amendment a threat to Indian democracy?",
    ]
    chip_cols = st.columns(2)
    for i, q in enumerate(examples):
        with chip_cols[i % 2]:
            st.button(q, key=f"ex_{i}", on_click=select_example, args=(q,), use_container_width=True)