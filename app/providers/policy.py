"""Model vendor policy: the deployment region bans OpenAI, Google and Anthropic.

The restriction applies to the model vendor, not the host, so their open-weight
releases (gpt-oss, Gemma) are excluded too, including on Bedrock or OpenRouter.
"""

from __future__ import annotations

BANNED_VENDORS = (
    "openai",
    "gpt",
    "google",
    "gemini",
    "gemma",
    "anthropic",
    "claude",
)


def ensure_allowed_model(slug: str) -> None:
    """Raise when a configured model belongs to a banned vendor."""
    lowered = slug.lower()
    for vendor in BANNED_VENDORS:
        if vendor in lowered:
            raise ValueError(
                f"model {slug!r} belongs to banned vendor {vendor!r}; "
                "the deployment region does not permit it"
            )
