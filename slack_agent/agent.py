
import os
import logging

import google.auth
from google.adk.apps.app import App
from google.adk.auth.auth_schemes import OpenIdConnectWithConfig
from google.adk.auth.auth_credential import AuthCredential, AuthCredentialTypes, OAuth2Auth
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools import google_search
from google.adk.tools import FunctionTool, AgentTool, VertexAiSearchTool
from google.adk.agents import Agent

# Setup logging
logging.basicConfig(level=logging.INFO)
from dotenv import load_dotenv


# Load .env from the same directory as this file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
# Set default environment variables if not present
_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1") 
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")

# --- Slack Toolset Configuration Based On OpenAPI Specification ---


auth_scheme = OpenIdConnectWithConfig(
   authorization_endpoint="https://slack.com/oauth/v2/authorize",
   token_endpoint="https://slack.com/api/oauth.v2.access",
   scopes=['chat:write']
)

# 2. Define the Credentials
# We pull these from the environment variables.
client_id = os.environ.get("SLACK_CLIENT_ID", "dummy_client_id")
client_secret = os.environ.get("SLACK_CLIENT_SECRET", "dummy_client_secret")

auth_credential = AuthCredential(
 auth_type=AuthCredentialTypes.OPEN_ID_CONNECT,
 oauth2=OAuth2Auth(
   client_id=client_id,
   client_secret=client_secret,
 )
)

# 3. Load the OpenAPI Spec
spec_path = os.path.join(os.path.dirname(__file__), 'spec.yaml')
with open(spec_path, 'r') as f:
   spec_content = f.read()

slack_toolset = OpenAPIToolset(
  spec_str=spec_content,
  spec_str_type='yaml',
  auth_scheme=auth_scheme,
  auth_credential=auth_credential,
)

# 4. Initialize Vertex AI Search Tool
data_store_id = os.environ.get("VERTEX_AI_SEARCH_DATA_STORE_ID")
project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
location = os.environ.get("GOOGLE_CLOUD_LOCATION", "global")
print(f"Using data store ID: {data_store_id}")
if data_store_id :
    # Construct full path assuming default_collection
    data_store_id = f"projects/{project_id}/locations/{location}/collections/default_collection/dataStores/{data_store_id}"
    print(f"Using data store ID: {data_store_id}")

vertex_ai_search_tool = VertexAiSearchTool(
    data_store_id=data_store_id
)
MODEL_NAME = 'gemini-2.5-flash'
# Configure and create the main LLM Agent.
search_agent = Agent(
name="search_agent",
model=MODEL_NAME,
description="An AI agent to search for content using Google Search.",
instruction="You are an expert at using Google Search to find relevant information",
tools=[google_search]
)

vertex_ai_search_tool_agent = Agent(
name="vertex_ai_search_agent",
model=MODEL_NAME,
description="An agent that searches for content using Vertex AI Search.",
instruction="""You are an expert at using Vertex AI Search to find relevant information about user queries.
You MUST provide a summary followed by a 'Reference:' section.
Format:
<Summary of findings>

Reference:
1. [Title](url)
2. [Title](url)

If no URL is available, use the title as the citation.
""",
tools=[vertex_ai_search_tool]
)

root_agent = LlmAgent(
   model=MODEL_NAME,
   name='slack_assistant',
   instruction="""You are a helpful assistant that answers questions and performs actions. Use the provided tools to post messages to Slack.
   First try to answer the question using internal knowledge by delegating to `vertex_ai_search_agent`.
   If external research is approved, delegate queries to the `search_agent` to find relevant information.
   ALWAYS preserve the 'Reference:' section provided by the `vertex_ai_search_agent` in your final response. Do not summarize the references, list them exactly as provided.""",
   tools=[slack_toolset, AgentTool(search_agent), AgentTool(vertex_ai_search_tool_agent)]
)

app = App(root_agent=root_agent, name="slack_app")

if __name__ == "__main__":
    print("Slack Agent App initialized.")
