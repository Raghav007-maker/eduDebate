import requests
import wikipediaapi
from fastmcp import FastMCP

# Create the FastMCP server instance
mcp = FastMCP("EduDebateWikipedia")

def search_top_title(query: str) -> str | None:
    """Queries Wikipedia Search Web API to obtain the most relevant page title matching the search term."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "format": "json"
    }
    headers = {
        "User-Agent": "EduDebate/1.0 (contact@example.com)"
    }
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        search_results = data.get("query", {}).get("search", [])
        if search_results:
            return search_results[0]["title"]
    except Exception:
        # Fallback gracefully during network or parsing errors
        return None
    return None

@mcp.tool()
def wikipedia_search(query: str) -> str:
    """Searches Wikipedia for the specified Indian Polity / Civics topic and returns its summary text."""
    title = search_top_title(query)
    if not title:
        return f"No search results found on Wikipedia for: '{query}'."

    # Fetch details for the top title
    wiki = wikipediaapi.Wikipedia(
        user_agent='EduDebate/1.0 (contact@example.com)',
        language='en'
    )
    try:
        page = wiki.page(title)
        if page.exists():
            return (
                f"Title: {page.title}\n"
                f"URL: {page.fullurl}\n\n"
                f"Summary:\n{page.summary[:1500]}"
            )
    except Exception as e:
        return f"Error retrieving page details for '{title}': {str(e)}."

    return f"Wikipedia page '{title}' exists but could not be read."

if __name__ == "__main__":
    # Launch MCP server over standard I/O channel
    mcp.run()
