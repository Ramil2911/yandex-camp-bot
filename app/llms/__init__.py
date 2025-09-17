"""
LLM Components Package

This package contains LLM-related components for the YandexGPT bot:
- Base abstract class for LLM components
- Dialogue bot for conversational interactions

Note: Moderator components are located in app.security package
"""

from .base import LLMBase
from .dialogue import DialogueBot, dialogue_bot, create_dialogue_bot

__all__ = [
    # Base classes
    "LLMBase",

    # Dialogue components
    "DialogueBot",
    "dialogue_bot",
    "create_dialogue_bot",
]

# Version info
__version__ = "1.0.0"
