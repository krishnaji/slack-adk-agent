
import os
import logging

import google.auth
from google.adk.apps.app import App
from google.adk.auth.auth_schemes import OpenIdConnectWithConfig
from google.adk.auth.auth_credential import AuthCredential, AuthCredentialTypes, OAuth2Auth
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools import google_search
from google.adk.tools import FunctionTool,AgentTool
from google.adk.agents import Agent

# Setup logging
logging.basicConfig(level=logging.INFO)

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
MODEL_NAME = 'gemini-2.5-flash'
# Configure and create the main LLM Agent.
search_agent = Agent(
name="search_agent",
model=MODEL_NAME,
description="An AI agent to search for content using Google Search.",
instruction="You are an expert at using Google Search to find relevant information for presentations.",
tools=[google_search]
)


root_agent = LlmAgent(
   model=MODEL_NAME,
   name='slack_assistant',
   instruction='You are a helpful assistant that answers questions and performs actions. Use the provided tools to post messages to Slack.If external research is approved, delegate queries to the `search_agent` to find relevant information.',
   tools=[slack_toolset,  AgentTool(search_agent)]
)

app = App(root_agent=root_agent, name="slack_app")

if __name__ == "__main__":
    print("Slack Agent App initialized.")
