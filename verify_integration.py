import os
import sys

# Mock environment variables
os.environ["VERTEX_AI_SEARCH_DATA_STORE_ID"] = "test-data-store-id"
os.environ["GOOGLE_CLOUD_PROJECT"] = "test-project"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

try:
    from slack_agent.agent import vertex_ai_search_tool, root_agent
    print("Successfully imported agent and tool.")
    print(f"Tool name: {vertex_ai_search_tool.name}")
    print(f"Agent tools: {[t.name for t in root_agent.tools]}")
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
