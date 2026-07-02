import os
import sys
import asyncio
import json
import re
from dotenv import load_dotenv
import streamlit as st
import google.genai.types as types
import google.adk as adk
from google.adk.sessions import InMemorySessionService
from unittest.mock import patch

# Ensure the project root is in python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.agents.workflow import create_debate_workflow
from src.lib.security import screen_input
from src.lib.db import save_debate, get_past_debates
from src.lib.mock import mock_generate_content_async

# Load environment variables
load_dotenv()

# Set up Streamlit Page Configuration
st.set_page_config(
    page_title="EduDebate — UPSC Polity Socratic Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Premium CSS Styling (Glassmorphism, Vibrant Gradients, Premium Fonts)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700;800&family=Space+Grotesk:wght@400;500;700&display=swap');

/* Main layout overrides */
.main .block-container {
    padding-top: 2rem;
    font-family: 'Outfit', sans-serif;
}

/* Glassmorphism Cards */
.glass-card {
    background: rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 24px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.1);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    margin-bottom: 20px;
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.glass-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.15);
}

/* Gradient Header */
.header-container {
    background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
    color: white;
    padding: 30px;
    border-radius: 12px;
    margin-bottom: 30px;
    text-align: center;
    box-shadow: 0 4px 20px rgba(0,0,0,0.15);
}

.header-title {
    font-family: 'Space Grotesk', sans-serif;
    font-size: 2.8rem;
    font-weight: 700;
    margin-bottom: 5px;
    letter-spacing: -0.5px;
}

.header-subtitle {
    font-size: 1.1rem;
    opacity: 0.9;
    font-weight: 300;
}

/* Agent Styling */
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
    font-size: 1.3rem;
    font-weight: 600;
}

.agent-badge {
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

/* Agent themes */
.research-theme { border-left: 5px solid #00d2ff; }
.research-badge { background-color: rgba(0, 210, 255, 0.15); color: #00d2ff; }

.advocate-theme { border-left: 5px solid #ff7675; }
.advocate-badge { background-color: rgba(255, 118, 117, 0.15); color: #ff7675; }

.factcheck-theme { border-left: 5px solid #a29bfe; }
.factcheck-badge { background-color: rgba(162, 155, 254, 0.15); color: #a29bfe; }

.synthesis-theme { 
    background: linear-gradient(145deg, rgba(253, 203, 110, 0.05) 0%, rgba(225, 112, 85, 0.05) 100%);
    border: 2px solid rgba(253, 203, 110, 0.3);
    border-left: 8px solid #fdcb6e;
}
.synthesis-badge { background-color: rgba(253, 203, 110, 0.15); color: #fdcb6e; }

/* Verdict Badges */
.verdict-card {
    padding: 12px 16px;
    border-radius: 8px;
    margin-bottom: 10px;
    font-size: 0.95rem;
    display: flex;
    flex-direction: column;
    gap: 4px;
}

.verdict-verified {
    background-color: rgba(46, 204, 113, 0.1);
    border-left: 4px solid #2ecc71;
}

.verdict-unverified {
    background-color: rgba(241, 196, 15, 0.1);
    border-left: 4px solid #f1c40f;
}

.verdict-disputed {
    background-color: rgba(231, 76, 60, 0.1);
    border-left: 4px solid #e74c3c;
}

.verdict-lbl {
    font-weight: 700;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.verdict-lbl.verified { color: #2ecc71; }
.verdict-lbl.unverified { color: #f1c40f; }
.verdict-lbl.disputed { color: #e74c3c; }

.claim-text {
    font-weight: 600;
}
.reason-text {
    font-size: 0.85rem;
    opacity: 0.8;
}

</style>
""", unsafe_allow_html=True)

# Application Header
st.markdown("""
<div class="header-container">
    <div class="header-title">🎓 EduDebate</div>
    <div class="header-subtitle">Multi-Agent Socratic Debate & Study Note Generator for UPSC Polity & Indian Civics</div>
</div>
""", unsafe_allow_html=True)

# Helper function to extract JSON robustly
def parse_factcheck_json(text: str) -> list:
    """Extracts and parses a JSON array of factcheck verdicts, supporting raw or markdown-fenced strings."""
    try:
        clean_text = text.strip()
        if "```" in clean_text:
            match = re.search(r'\[\s*\{.*\}\s*\]', clean_text, re.DOTALL)
            if match:
                clean_text = match.group(0)
            else:
                clean_text = clean_text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)
    except Exception:
        return []

# Helper function to render step progress
def render_stepper(active_step: int):
    """Renders a 4-step progress indicator. active_step: 0=none, 1-4=which agent is running, 5=completed."""
    steps = [
        ("Research", "Claims gathered"),
        ("Challenge", "Tensions surfaced"),
        ("Verify", "Checking claims..."),
        ("Synthesise", "Final note"),
    ]
    html = '<div style="display:flex;align-items:center;gap:4px;padding:10px 16px;background:rgba(255,255,255,0.03);border-radius:8px;border:1px solid rgba(255,255,255,0.08);margin-bottom:16px;">'
    for i, (name, sub) in enumerate(steps, 1):
        if i < active_step or active_step == 5:
            circle = "✓"
            color = "#2ecc71"
            sub_text = "Done" if active_step == 5 or i < active_step else sub
        elif i == active_step:
            circle = str(i)
            color = "#00d2ff"
            sub_text = sub
        else:
            circle = str(i)
            color = "rgba(255,255,255,0.2)"
            sub_text = "Pending"
        
        html += f'''<div style="display:flex;align-items:center;gap:8px;flex:1;">
            <div style="width:26px;height:26px;border-radius:50%;border:1.5px solid {color};display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:600;color:{color};flex-shrink:0;">{circle}</div>
            <div style="font-size:11px;color:{color};line-height:1.3;"><span style="font-weight:600;display:block;">{name}</span><span style="opacity:0.7;font-size:10px;">{sub_text}</span></div>
        </div>'''
        if i < 4:
            divider_color = "#2ecc71" if (i < active_step or active_step == 5) else "rgba(255,255,255,0.1)"
            html += f'<div style="width:20px;height:1px;background:{divider_color};flex-shrink:0;"></div>'
    html += '</div>'
    return html

# Sidebar Session/History and Config Panel
with st.sidebar:
    st.title("Settings & History")
    
    # API Key Configuration
    st.subheader("Configuration")
    api_key = st.text_input("Gemini API Key", type="password", value=os.getenv("GEMINI_API_KEY", ""))
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
        api_mode = True
    else:
        api_mode = "GEMINI_API_KEY" in os.environ and os.environ["GEMINI_API_KEY"].strip() != ""
    
    if api_mode:
        st.success("API Key Active (Real LLM Mode)")
    else:
        st.warning("No API Key (Mock Mode Activated)")

    st.markdown("---")
    st.subheader("My Debates 📚")
    
    past_runs = get_past_debates()
    selected_debate = None
    
    if past_runs:
        for run in past_runs:
            q_text = run["question"]
            btn_label = q_text[:35] + "..." if len(q_text) > 35 else q_text
            if st.button(btn_label, key=f"hist_{run['id']}", use_container_width=True):
                selected_debate = run
    else:
        st.info("No past debates yet. Try asking your first question!")

# Session state initialization to handle loaded debates
if "current_debate" not in st.session_state:
    st.session_state.current_debate = None

if "question_input" not in st.session_state:
    st.session_state.question_input = ""

if selected_debate:
    st.session_state.current_debate = selected_debate

# Main view layout
col_input, col_info = st.columns([3, 1])

with col_input:
    user_query = st.text_input(
        "Ask a UPSC Polity or Civics question:",
        placeholder="e.g., Explain the significance of the Basic Structure Doctrine.",
        key="question_input"
    )

with col_info:
    st.write("")
    st.write("")
    submit_button = st.button("Generate Debate", use_container_width=True, type="primary")

# Run new workflow if button clicked
if submit_button and user_query:
    st.session_state.current_debate = None # Reset selected history
    st.session_state.question_input = ""      # Clear state value to prevent sticky inputs
    
    # 1. Run Pre-LLM Security Screening
    is_safe, screening_msg = screen_input(user_query)
    
    if not is_safe:
        st.error(screening_msg)
    else:
        st.info(f"Question verified. Spawning Socratic debate for: *{screening_msg}*")
        
        # Stepper placeholder at the top
        stepper_ph = st.empty()
        stepper_ph.markdown(render_stepper(1), unsafe_allow_html=True)
        
        # Side-by-side columns for Research vs Devil's Advocate
        debate_cols = st.columns(2)
        with debate_cols[0]:
            r_card = st.empty()
        with debate_cols[1]:
            a_card = st.empty()
            
        f_card = st.empty()
        s_card = st.empty()
        
        # State variables to accumulate texts
        agent_texts = {
            "ResearchAgent": "",
            "DevilsAdvocate": "",
            "FactCheck": "",
            "Synthesis": ""
        }
        
        # Run ADK graph
        workflow = create_debate_workflow()
        session_service = InMemorySessionService()
        runner = adk.Runner(
            agent=workflow,
            session_service=session_service,
            app_name="EduDebate",
            auto_create_session=True
        )
        
        new_message = types.Content(
            role="user",
            parts=[types.Part(text=screening_msg)]
        )
        
        state_delta = {
            "wikipedia_context": f"Wikipedia context: UPSC Polity context search for {screening_msg}"
        }
        
        async def run_agents():
            if not api_mode:
                target = "google.adk.models.google_llm.Gemini.generate_content_async"
                with patch(target, side_effect=mock_generate_content_async, autospec=True):
                    return runner.run(
                        user_id="streamlit_user",
                        session_id="session_live",
                        new_message=new_message,
                        state_delta=state_delta
                    )
            else:
                return runner.run(
                    user_id="streamlit_user",
                    session_id="session_live",
                    new_message=new_message,
                    state_delta=state_delta
                )
        
        try:
            # Avoid asyncio.run loop errors in Streamlit
            loop = asyncio.new_event_loop()
            events = loop.run_until_complete(run_agents())
            
            step_map = {"ResearchAgent": 1, "DevilsAdvocate": 2, "FactCheck": 3, "Synthesis": 4}
            
            for ev in events:
                author = ev.author
                if author in step_map:
                    stepper_ph.markdown(render_stepper(step_map[author]), unsafe_allow_html=True)
                
                if author in agent_texts:
                    text_chunk = ""
                    if ev.content and ev.content.parts:
                        for part in ev.content.parts:
                            if part.text:
                                text_chunk += part.text
                    
                    agent_texts[author] += text_chunk
                    
                    if author == "ResearchAgent":
                        r_card.markdown(f"""
                        <div class="glass-card research-theme">
                            <div class="agent-header">
                                <span class="agent-badge research-badge">Research Agent</span>
                                <span class="agent-name">Initial Deconstruction & Source Citations</span>
                            </div>
                            <div style="white-space: pre-wrap;">{agent_texts[author]}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    elif author == "DevilsAdvocate":
                        a_card.markdown(f"""
                        <div class="glass-card advocate-theme">
                            <div class="agent-header">
                                <span class="agent-badge advocate-badge">Devil's Advocate</span>
                                <span class="agent-name">Interpretation & Historiographical Challenge</span>
                            </div>
                            <div style="white-space: pre-wrap;">{agent_texts[author]}</div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                    elif author == "FactCheck":
                        claims_list = parse_factcheck_json(agent_texts[author])
                        if claims_list:
                            html_content = ""
                            for item in claims_list:
                                v = item.get("verdict", "Unverified").strip().lower()
                                badge_class = "verified" if v == "verified" else "unverified" if v == "unverified" else "disputed"
                                card_class = f"verdict-{badge_class}"
                                
                                html_content += f"""
                                <div class="verdict-card {card_class}">
                                    <div class="verdict-lbl {badge_class}">{v}</div>
                                    <div class="claim-text">Claim: "{item.get('claim', '')}"</div>
                                    <div class="reason-text">Reason: {item.get('reason', '')}</div>
                                </div>
                                """
                            f_card.markdown(f"""
                            <div class="glass-card factcheck-theme">
                                <div class="agent-header">
                                    <span class="agent-badge factcheck-badge">Fact Checker</span>
                                    <span class="agent-name">MCP Wikipedia-sourced Verification Verdicts</span>
                                </div>
                                {html_content}
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            f_card.markdown(f"""
                            <div class="glass-card factcheck-theme">
                                <div class="agent-header">
                                    <span class="agent-badge factcheck-badge">Fact Checker</span>
                                    <span class="agent-name">MCP Wikipedia-sourced Verification Verdicts</span>
                                </div>
                                <pre style="white-space: pre-wrap;">{agent_texts[author]}</pre>
                            </div>
                            """, unsafe_allow_html=True)
                            
                    elif author == "Synthesis":
                        s_card.markdown(f"""
                        <div class="glass-card synthesis-theme">
                            <div class="agent-header">
                                <span class="agent-badge synthesis-badge">Synthesis Note</span>
                                <span class="agent-name">Final UPSC Polity Revision Card</span>
                            </div>
                            <div style="white-space: pre-wrap;">{agent_texts[author]}</div>
                        </div>
                        """, unsafe_allow_html=True)
            
            loop.close()
            stepper_ph.markdown(render_stepper(5), unsafe_allow_html=True)
            
            # Save debate session
            save_debate(
                question=screening_msg,
                research_output=agent_texts["ResearchAgent"],
                advocate_output=agent_texts["DevilsAdvocate"],
                factcheck_output=agent_texts["FactCheck"],
                synthesis_output=agent_texts["Synthesis"]
            )
            st.success("Debate finalized and saved to your history sidebar!")
            st.rerun()
            
        except Exception as e:
            st.error(f"An error occurred during debate simulation: {str(e)}")

# Render selected past debate or a default greeting with clickable chips
if st.session_state.current_debate:
    run = st.session_state.current_debate
    st.markdown(f"### Historical Debate Session: *{run['question']}*")
    st.caption(f"Saved on {run['timestamp']}")
    
    # Stepper in complete state for loaded debates
    st.markdown(render_stepper(5), unsafe_allow_html=True)
    
    # Side-by-side columns layout
    saved_cols = st.columns(2)
    with saved_cols[0]:
        st.markdown(f"""
        <div class="glass-card research-theme">
            <div class="agent-header">
                <span class="agent-badge research-badge">Research Agent</span>
                <span class="agent-name">Initial Deconstruction & Source Citations</span>
            </div>
            <div style="white-space: pre-wrap;">{run['research_output']}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with saved_cols[1]:
        st.markdown(f"""
        <div class="glass-card advocate-theme">
            <div class="agent-header">
                <span class="agent-badge advocate-badge">Devil's Advocate</span>
                <span class="agent-name">Interpretation & Historiographical Challenge</span>
            </div>
            <div style="white-space: pre-wrap;">{run['advocate_output']}</div>
        </div>
        """, unsafe_allow_html=True)
    
    # Fact Check verdicts
    claims_list = parse_factcheck_json(run['factcheck_output'])
    if claims_list:
        html_content = ""
        for item in claims_list:
            v = item.get("verdict", "Unverified").strip().lower()
            badge_class = "verified" if v == "verified" else "unverified" if v == "unverified" else "disputed"
            card_class = f"verdict-{badge_class}"
            
            html_content += f"""
            <div class="verdict-card {card_class}">
                <div class="verdict-lbl {badge_class}">{v}</div>
                <div class="claim-text">Claim: "{item.get('claim', '')}"</div>
                <div class="reason-text">Reason: {item.get('reason', '')}</div>
            </div>
            """
        st.markdown(f"""
        <div class="glass-card factcheck-theme">
            <div class="agent-header">
                <span class="agent-badge factcheck-badge">Fact Checker</span>
                <span class="agent-name">MCP Wikipedia-sourced Verification Verdicts</span>
            </div>
            {html_content}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="glass-card factcheck-theme">
            <div class="agent-header">
                <span class="agent-badge factcheck-badge">Fact Checker</span>
                <span class="agent-name">MCP Wikipedia-sourced Verification Verdicts</span>
            </div>
            <pre style="white-space: pre-wrap;">{run['factcheck_output']}</pre>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown(f"""
    <div class="glass-card synthesis-theme">
        <div class="agent-header">
            <span class="agent-badge synthesis-badge">Synthesis Note</span>
            <span class="agent-name">Final UPSC Polity Revision Card</span>
        </div>
        <div style="white-space: pre-wrap;">{run['synthesis_output']}</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Export options for Study Note
    if run['synthesis_output']:
        col_copy, col_save, _ = st.columns([1, 1, 4])
        with col_copy:
            st.button(
                "📋 Copy note", 
                key="copy_btn", 
                help="Copy synthesis to clipboard",
                on_click=lambda: st.write(
                    f'<script>navigator.clipboard.writeText(`{run["synthesis_output"]}`)</script>',
                    unsafe_allow_html=True
                )
            )
        with col_save:
            st.download_button(
                "⬇ Save note", 
                data=run['synthesis_output'],
                file_name=f"edudebate_{run['question'][:20].replace(' ','_')}.txt",
                mime="text/plain",
                key="download_btn"
            )

elif not user_query:
    # Chips / Interactive Example Questions
    st.markdown("""
    <div style="text-align:center;padding:30px 0 10px;">
        <div style="font-size:1.1rem;font-weight:600;color:rgba(255,255,255,0.7);margin-bottom:8px;">Try asking about...</div>
    </div>""", unsafe_allow_html=True)
    
    examples = [
        "Was the Basic Structure Doctrine a judicial overreach?",
        "Explain the Governor's discretionary powers under Article 163.",
        "How did Article 370 reflect asymmetric federalism in India?",
        "Was the 42nd Amendment a threat to Indian democracy?"
    ]
    cols = st.columns(2)
    for i, q in enumerate(examples):
        with cols[i % 2]:
            if st.button(q, key=f"ex_{i}", use_container_width=True):
                st.session_state.question_input = q
                st.rerun()
