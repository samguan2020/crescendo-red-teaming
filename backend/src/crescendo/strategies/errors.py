"""Strategy-level control-flow exceptions."""


class StrategyUnavailable(Exception):
    """Raised when a strategy cannot produce a prompt (e.g. attacker LLM
    refused or returned garbage), so the fallback chain can cascade."""
