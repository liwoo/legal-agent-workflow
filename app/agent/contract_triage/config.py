"""Environment bootstrap — load the local ``.env`` before anything reads it.

Importing this module loads ``app/agent/.env`` (the agent's working directory
when launched standalone or by ``make up``) so ``OPENAI_API_KEY`` /
``OPENAI_CHAT_MODEL`` and the other settings are available to the chat client and
observability layers. Idempotent and side-effect-only; safe to import anywhere.
"""

from __future__ import annotations

from dotenv import load_dotenv

# ``override=True`` makes the local ``.env`` file authoritative — its values win
# over anything already in the environment. This is deliberate: a stale
# ``OPENAI_API_KEY`` exported in a shell profile (~/.zshrc) must NOT silently
# shadow the key the developer just put in ``.env``. Vars the file doesn't define
# (e.g. the OTEL/object-store config ``make up`` sources from e2e/stack.env) are
# left untouched, so injected runtime config still flows through.
load_dotenv(override=True)
