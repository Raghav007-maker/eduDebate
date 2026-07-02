from google.adk.models.llm_response import LlmResponse
import google.genai.types as types

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
