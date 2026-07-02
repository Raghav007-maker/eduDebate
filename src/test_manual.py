import sys
import os
import asyncio
from unittest.mock import patch
from dotenv import load_dotenv

import google.adk as adk
from google.adk.sessions import InMemorySessionService
from google.adk.models.llm_response import LlmResponse
import google.genai.types as types

# Ensure the root folder is in python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.workflow import create_debate_workflow

async def mock_generate_content_async(self, llm_request, **kwargs):
    """Mocks LLM responses based on active adk_agent_name label to verify workflow integration."""
    # Retrieve agent name from labels
    agent_name = ""
    if llm_request.config and llm_request.config.labels:
        agent_name = llm_request.config.labels.get("adk_agent_name", "")

    if agent_name == "FactCheck":
        response_text = '[{"claim": "Article 370 was drafted by Gopalaswami Ayyangar.", "verdict": "Verified", "reason": "Wikipedia context confirms the role of Gopalaswami Ayyangar."}]'
    elif agent_name == "Synthesis":
        response_text = (
            "EXPLANATION:\nArticle 370 of the Indian Constitution gave special status to Jammu and Kashmir.\n\n"
            "KEY Socratic TENSIONS:\n"
            "* Tension 1: Autonomy versus complete integration into the Union.\n"
            "* Tension 2: Constitutional validity of modifications using Governor concurrence.\n"
            "* Tension 3: Historiographical perspectives on the temporary nature of Article 370.\n\n"
            "VERIFIED FACTS:\n"
            "* Gopalaswami Ayyangar drafted Article 370."
        )
    elif agent_name == "DevilsAdvocate":
        response_text = (
            "CHALLENGED ASSUMPTIONS:\n"
            "The initial framing assumes integration automatically equates to absolute constitutional uniformity.\n\n"
            "ALTERNATIVE PERSPECTIVE:\n"
            "Asymmetrical federalism is a recognized constitutional feature globally and in other regions of India (e.g. Article 371)."
        )
    else:  # ResearchAgent
        response_text = (
            "DECOMPOSED CLAIMS:\n"
            "1. Article 370 was drafted by Gopalaswami Ayyangar.\n"
            "2. Article 370 was intended as a temporary provision.\n\n"
            "INITIAL POSITION:\n"
            "Article 370 provided J&K with internal autonomy from 1954 to 2019.\n\n"
            "SOURCES & KEYWORDS:\n"
            "Article 370, Gopalaswami Ayyangar, Jammu and Kashmir Reorganisation"
        )

    llm_response = LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(text=response_text)]
        ),
        turn_complete=True
    )
    yield llm_response

async def test_run():
    """Runs the multi-agent debate pipeline, using mock mode if no API key is set."""
    load_dotenv()
    api_key_present = "GEMINI_API_KEY" in os.environ and os.environ["GEMINI_API_KEY"].strip() != ""

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
        parts=[types.Part(text="What is the history and significance of Article 370?")]
    )

    # State delta simulates MCP Wikipedia search context injected in Phase 3
    state_delta = {
        "wikipedia_context": "Wikipedia context: Article 370 was a temporary provision drafting Jammu and Kashmir's autonomy, drafted by Gopalaswami Ayyangar."
    }

    if not api_key_present:
        print("--- GEMINI_API_KEY NOT FOUND: RUNNING IN MOCK MODE ---")
        target = "google.adk.models.google_llm.Gemini.generate_content_async"
        with patch(target, side_effect=mock_generate_content_async, autospec=True):
            events = runner.run(
                user_id="user_1",
                session_id="session_1",
                new_message=new_message,
                state_delta=state_delta
            )
            for ev in events:
                print(f"\n[{ev.author or 'System'}] Event:")
                if ev.content:
                    for part in ev.content.parts:
                        if part.text:
                            print(part.text)
    else:
        print("--- GEMINI_API_KEY FOUND: RUNNING REAL LLM DEBATE ---")
        events = runner.run(
            user_id="user_1",
            session_id="session_1",
            new_message=new_message,
            state_delta=state_delta
        )
        for ev in events:
            print(f"\n[{ev.author or 'System'}] Event:")
            if ev.content:
                for part in ev.content.parts:
                    if part.text:
                        print(part.text)

if __name__ == "__main__":
    asyncio.run(test_run())
