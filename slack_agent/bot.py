import os
import logging
import asyncio
from dotenv import load_dotenv
import os

# Load .env from the same directory as this file
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

from slack_bolt import App as BoltApp
from slack_bolt.adapter.socket_mode import SocketModeHandler
from google.adk.runners import Runner
from .agent import app as adk_app

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from google.adk.sessions.in_memory_session_service import InMemorySessionService

# Unset Client ID and Secret to avoid Bolt enabling OAuth flow (we want single workspace bot)
os.environ.pop("SLACK_CLIENT_ID", None)
os.environ.pop("SLACK_CLIENT_SECRET", None)

# Initialize Bolt App
bolt_app = BoltApp(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize ADK Runner
# We use the app defined in agent.py
session_service = InMemorySessionService()
runner = Runner(app=adk_app, session_service=session_service)

@bolt_app.event("app_mention")
def handle_app_mention(event, say):
    """Handles app mentions."""
    logger.info(f"Received app_mention: {event}")
    process_event(event, say)

@bolt_app.message(".*")
def handle_message(message, say):
    """Handles direct messages or messages in channels where bot is present."""
    if message.get("subtype") is None:
        logger.info(f"Received message: {message}")
        process_event(message, say)

def process_event(event, say):
    """Processes the event using ADK Runner."""
    user_id = event.get("user")
    channel_id = event.get("channel")
    text = event.get("text")
    ts = event.get("ts")

    if not text:
        return

    # Create a session ID based on channel and user to keep context
    # For a shared channel bot, maybe just channel_id is enough if we want shared context?
    # Or session_id = f"slack-{channel_id}" for channel-wide context.
    # Let's go with channel-wide context for now as it's typical for bots.
    session_id = f"slack-{channel_id}"

    logger.info(f"Processing message for session {session_id}: {text}")

    # Run the agent synchronously for now as Bolt's default handler is sync
    # But ADK Runner is better used async. 
    # We can use asyncio.run() if we are in a sync context, but Bolt can also be async.
    # For simplicity, let's use the sync run() method of Runner if available, or wrap async.
    
    # Runner.run is a generator, so we need to iterate over events.
    # Ensure session exists
    async def ensure_session():
        if not await session_service.get_session(app_name=adk_app.name, user_id=user_id, session_id=session_id):
            await session_service.create_session(app_name=adk_app.name, user_id=user_id, session_id=session_id)
    
    asyncio.run(ensure_session())

    try:
        # We need to construct a proper ADK Content/Message
        from google.genai import types
        new_message = types.Content(
            role="user",
            parts=[types.Part(text=text)]
        )

        # Execute the agent
        # Note: runner.run is a generator that yields events.
        # We want to capture the model's response.
        
        for adk_event in runner.run(
            user_id=user_id,
            session_id=session_id,
            new_message=new_message
        ):
            logger.info(f"Received ADK event: {adk_event}")
            # Check if the event has content from the model
            # The author might be the agent name (e.g. 'slack_assistant'), so we check content.role
            if adk_event.content and adk_event.content.role == "model":
                logger.info(f"Model event content parts: {adk_event.content.parts}")
                # Extract text from content
                response_text = ""
                if adk_event.content.parts:
                    for part in adk_event.content.parts:
                        if part.text:
                            response_text += part.text
                        # If there are other parts like 'thought', we might want to log them or ignore them.
                        # But for now, let's just focus on text.
                
                if response_text:
                    say(response_text, thread_ts=ts) # Reply in thread

    except Exception as e:
        logger.error(f"Error processing event: {e}", exc_info=True)
        say(f"I encountered an error: {e}", thread_ts=ts)

if __name__ == "__main__":
    # Start the app using Socket Mode
    app_token = os.environ.get("SLACK_APP_TOKEN")
    # We might need SLACK_APP_TOKEN for Socket Mode. 
    # The .env provided earlier didn't show SLACK_APP_TOKEN, only BOT_TOKEN, CLIENT_ID, SECRET, SIGNING_SECRET.
    # If no APP_TOKEN, we might need to use HTTP server.
    # But usually for local dev, Socket Mode is preferred.
    # Let's check if SLACK_APP_TOKEN is in env, if not, maybe we can't use SocketMode.
    
    if app_token:
        handler = SocketModeHandler(bolt_app, app_token)
        handler.start()
    else:
        print("SLACK_APP_TOKEN not found. Starting in HTTP mode on port 3000.")
        bolt_app.start(port=int(os.environ.get("PORT", 3000)))
