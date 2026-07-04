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
from src.lib.mock import mock_generate_content_async

async def test_run():
    """Runs the multi-agent debate pipeline, using mock mode if no API key is set."""
    load_dotenv()
    api_key_present = "GEMINI_API_KEY" in os.environ and os.environ["GEMINI_API_KEY"].strip() != ""

    workflow = create_debate_workflow(model_lite="gemini-3.1-flash-lite", model_standard="gemini-3.5-flash")
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
            events = runner.run_async(
                user_id="user_1",
                session_id="session_1",
                new_message=new_message,
                state_delta=state_delta
            )
            async for ev in events:
                print(f"\n[{ev.author or 'System'}] Event:")
                if ev.content:
                    for part in ev.content.parts:
                        if part.text:
                            print(part.text)
    else:
        print("--- GEMINI_API_KEY FOUND: RUNNING REAL LLM DEBATE ---")
        events = runner.run_async(
            user_id="user_1",
            session_id="session_1",
            new_message=new_message,
            state_delta=state_delta
        )
        async for ev in events:
            print(f"\n[{ev.author or 'System'}] Event:")
            if ev.content:
                for part in ev.content.parts:
                    if part.text:
                        print(part.text)

if __name__ == "__main__":
    asyncio.run(test_run())
