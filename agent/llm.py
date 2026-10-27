"""
llm.py  --  the one function that talks to the AI model.

This file is COMPLETE. You do not need to change it. It wraps the `openai`
library so the rest of the agent can just call `chat(messages)` and get back
the model's text reply.

It reads three settings from your environment (loaded from the .env file):
    LLM_API_KEY   -- your secret API key
    LLM_BASE_URL  -- the API endpoint (OpenAI-compatible)
    LLM_MODEL     -- which model to use, e.g. gemini-3.5-flash-lite
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

# Read the .env file (if present) and put its values into the environment.
load_dotenv()

# Build the client once, when this module is first imported.
_client = OpenAI(
    api_key=os.environ.get("LLM_API_KEY"),
    base_url=os.environ.get("LLM_BASE_URL"),
)

# Remember which model we were told to use.
_model = os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite")


def chat(messages):
    """
    Send a list of chat messages to the model and return its text reply.

    `messages` is a list of dicts in the standard chat format, for example:
        [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello!"},
        ]

    Returns: the assistant's reply as a plain string.
    """
    response = _client.chat.completions.create(
        model=_model,
        messages=messages,
        # temperature 0 = more focused / repeatable answers, which is nice while
        # learning because the agent behaves more predictably.
        temperature=0,
    )
    # The model can occasionally return no text (e.g. an empty or filtered
    # response). Coerce that to "" so callers always get a string to work with.
    return response.choices[0].message.content or ""
