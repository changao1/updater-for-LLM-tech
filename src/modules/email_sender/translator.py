"""Translate content from English to Chinese using Claude API."""

from __future__ import annotations

import logging
import os

import anthropic
import yaml

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_PROMPT = (
    "You are a professional translator specializing in AI/ML technical content. "
    "Translate the following content from English to Chinese. "
    "Keep all technical terms, paper titles, repo names, and URLs in their original form. "
    "Keep the Markdown formatting intact. "
    "Make the translation natural and readable for a Chinese technical audience."
)


class Translator:
    """Translate text using Claude API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        system_prompt: str | None = None,
        settings_path: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("LLM_API_KEY", "")
        self.model = model or DEFAULT_MODEL
        self.system_prompt = system_prompt or DEFAULT_PROMPT

        # Load settings from config if available
        if settings_path:
            try:
                with open(settings_path, "r") as f:
                    settings = yaml.safe_load(f)
                t_config = settings.get("translation", {})
                if not model:
                    self.model = t_config.get("model", self.model)
                if not system_prompt and t_config.get("prompt"):
                    self.system_prompt = t_config["prompt"]
            except Exception as e:
                logger.warning(f"Could not load translation settings: {e}")

        if not self.api_key:
            logger.warning("LLM_API_KEY not configured, translation will be disabled")

    def translate_to_chinese(self, text: str) -> str:
        """Translate English text to Chinese.

        Args:
            text: English Markdown content.

        Returns:
            Chinese translated Markdown content.
            Returns original text if translation fails.
        """
        if not self.api_key:
            logger.error("No API key configured, returning original text")
            return text

        if not text.strip():
            return text

        try:
            client = anthropic.Anthropic(api_key=self.api_key)

            # Split long content into chunks if needed (Claude has input limits)
            # For typical daily/weekly reports, this should be well within limits
            message = client.messages.create(
                model=self.model,
                max_tokens=8192,
                system=self.system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": f"Please translate the following content:\n\n{text}",
                    }
                ],
            )

            translated = message.content[0].text
            logger.info(
                f"Translation completed: {len(text)} chars -> {len(translated)} chars"
            )
            return translated

        except anthropic.APIError as e:
            logger.error(f"Claude API error during translation: {e}")
            return text
        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return text
