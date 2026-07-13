"""Environment bootstrap — load the local ``.env`` before anything reads it.

Importing this module loads ``app/agent/.env`` (the agent's working directory
when launched standalone or by the Aspire AppHost) so ``OPENAI_API_KEY`` /
``OPENAI_CHAT_MODEL`` and the other settings are available to the chat client and
observability layers. Idempotent and side-effect-only; safe to import anywhere.
"""

from __future__ import annotations

from dotenv import load_dotenv

# ``override=False`` keeps real environment variables (e.g. those Aspire injects)
# authoritative over the file, while filling in anything the file provides.
load_dotenv(override=False)
