"""Scout — an agentic research assistant (CLI).

Takes a topic, plans sub-questions, searches the web, refines queries,
and synthesizes a cited markdown report.
"""

from .agent import ResearchAgent
from .llm import LLMProvider, MockLLM, GroqLLM

__all__ = ["ResearchAgent", "LLMProvider", "MockLLM", "GroqLLM"]
__version__ = "0.1.0"
