import asyncio
import sys
import os

# Ensure the root folder is in python search path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.lib.mcp_client import query_wikipedia_mcp

def safe_print(text: str):
    """Safely prints text to Windows console, replacing unencodable characters (like rupee sign)."""
    print(text.encode(sys.stdout.encoding or 'utf-8', errors='replace').decode(sys.stdout.encoding or 'utf-8'))

async def main():
    print("--- TESTING MCP CLIENT WIKIPEDIA SEARCH (NORMAL PATH) ---")
    res = await query_wikipedia_mcp("Article 370")
    print("Result:")
    safe_print(res[:500] + "...\n")

    print("--- TESTING MCP CLIENT FALLBACK (SIMULATED CRASH / INVALID SERVER PATH) ---")
    # Temporarily point to a non-existent file to simulate subprocess failure
    import src.lib.mcp_client as mcp_client
    original_path = mcp_client.SERVER_PATH
    mcp_client.SERVER_PATH = "non_existent_server_file.py"
    
    res_fallback = await query_wikipedia_mcp("Article 370")
    print("Fallback Result:")
    safe_print(res_fallback)
    
    # Restore original path
    mcp_client.SERVER_PATH = original_path

if __name__ == "__main__":
    asyncio.run(main())
