#!/usr/bin/env python
"""Run the LiveKit voice agent worker."""

import os
import sys

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from livekit.agents import cli
from src.config.settings import settings

# Run the agent using LiveKit's CLI
if __name__ == "__main__":
    # Import the worker module to register the entrypoint
    import src.voice.voice_agent_worker

    # Set up environment for LiveKit
    os.environ["LIVEKIT_URL"] = settings.livekit_url
    os.environ["LIVEKIT_API_KEY"] = settings.livekit_api_key
    os.environ["LIVEKIT_API_SECRET"] = settings.livekit_api_secret

    # Run with CLI
    from livekit.agents.cli import cli_app
    cli_app()
