import os
from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.sessions import InMemorySessionService
from google.adk import Runner

from src.prompts import (
    research_agent as research_prompts,
    devils_advocate as advocate_prompts,
    fact_check as factcheck_prompts,
    synthesis as synthesis_prompts,
)
from src.lib.mcp_client import query_wikipedia_mcp

async def wikipedia_search(query: str) -> str:
    """Searches Wikipedia for a given UPSC Polity/Civics topic via MCP subprocess."""
    return await query_wikipedia_mcp(query)

def create_debate_workflow() -> SequentialAgent:
    """Creates and configures the sequential multi-agent debate pipeline."""
    # Define model assignments based on project constraints
    model_lite = "gemini-2.5-flash-lite"
    model_standard = "gemini-2.5-flash"

    # Agent 1: Research Agent (uses flash-lite, decomposes topic, queries source via MCP)
    research_agent = LlmAgent(
        name="ResearchAgent",
        model=model_lite,
        instruction=research_prompts.SYSTEM_INSTRUCTION,
        output_key="research_output",
        tools=[wikipedia_search]
    )

    # Agent 2: Devil's Advocate Agent (uses flash standard, challenges interpretation)
    devils_advocate = LlmAgent(
        name="DevilsAdvocate",
        model=model_standard,
        # Reference Research Agent's output via output_key binding
        instruction=advocate_prompts.SYSTEM_INSTRUCTION + "\n\nInitial Research Input to challenge:\n{research_output}",
        output_key="advocate_output"
    )

    # Agent 3: Fact-Check Agent (uses flash standard, validates claims via Wikipedia search tool)
    fact_check = LlmAgent(
        name="FactCheck",
        model=model_standard,
        instruction=factcheck_prompts.SYSTEM_INSTRUCTION + "\n\nResearch Claims:\n{research_output}\n\nDevil's Advocate Claims:\n{advocate_output}",
        output_key="factcheck_output",
        tools=[wikipedia_search]
    )

    # Agent 4: Synthesis Agent (uses flash standard, compiles final study note)
    synthesis = LlmAgent(
        name="Synthesis",
        model=model_standard,
        instruction=synthesis_prompts.SYSTEM_INSTRUCTION + "\n\nResearch Analysis:\n{research_output}\n\nDevil's Advocate Challenges:\n{advocate_output}\n\nFact-Checking Verdicts:\n{factcheck_output}",
        output_key="synthesis_output"
    )

    # Wrap the agents sequentially
    workflow = SequentialAgent(
        name="EduDebateWorkflow",
        sub_agents=[research_agent, devils_advocate, fact_check, synthesis]
    )

    return workflow
