from decimal import Decimal
from typing import TypedDict

from typing import Protocol


class UsageLike(Protocol):
    input_tokens: int
    output_tokens: int


class ModelPricing(TypedDict):
    """Prices in USD per 1M tokens."""

    input: Decimal
    output: Decimal
    cache_write: Decimal | None  # if model supports cache_control
    cache_read: Decimal | None


PRICING: dict[str, ModelPricing] = {
    # DeepSeek V4 Flash — main workhorse for parsing & scoring
    "deepseek-v4-flash": {
        "input": Decimal("0.14"),
        "output": Decimal("0.28"),
        "cache_write": None,  # no cache_control via /anthropic
        "cache_read": Decimal("0.028"),  # automatic server-side cache
    },
    # DeepSeek V4 Pro — for harder reasoning tasks (investigator)
    # NOTE: prices below are POST-PROMO (full price). Until 2026-05-31
    # there's a 75% off promo: input miss $0.435, output $0.87, cache hit $0.03625.
    # Update this entry on June 1, 2026.
    "deepseek-v4-pro": {
        "input": Decimal("1.74"),
        "output": Decimal("3.48"),
        "cache_write": None,
        "cache_read": Decimal("0.145"),
    },
    "claude-haiku-4-5": {
        "input": Decimal("1.00"),
        "output": Decimal("5.00"),
        "cache_write": Decimal("1.25"),
        "cache_read": Decimal("0.10"),
    },
    "claude-sonnet-4-6": {
        "input": Decimal("3.00"),
        "output": Decimal("15.00"),
        "cache_write": Decimal("3.75"),
        "cache_read": Decimal("0.30"),
    },
}


class UnknownModelError(ValueError):
    """Raised when pricing data is missing for a model."""


def calculate_cost(model: str, usage: UsageLike) -> Decimal:
    """
    Calculate USD cost of a single LLM call.

    Args:
        model: Model name as it appears in PRICING table.
        usage: anthropic.types.Usage or compatible object with
               input_tokens, output_tokens, and optionally
               cache_creation_input_tokens / cache_read_input_tokens.

    Returns:
        Cost in USD as Decimal (precise, not float).

    Raises:
        UnknownModelError: if model is not in PRICING table.
    """
    if model not in PRICING:
        raise UnknownModelError(
            f"No pricing data for model {model!r}. Add it to PRICING in pricing.py."
        )

    rates = PRICING[model]

    # Helper: tokens × rate per 1M
    def cost_for(tokens: int, rate: Decimal) -> Decimal:
        return (Decimal(tokens) * rate) / Decimal(1_000_000)

    cost = cost_for(usage.input_tokens, rates["input"])
    cost += cost_for(usage.output_tokens, rates["output"])

    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0

    if cache_write and rates["cache_write"] is not None:
        cost += cost_for(cache_write, rates["cache_write"])
    if cache_read and rates["cache_read"] is not None:
        cost += cost_for(cache_read, rates["cache_read"])

    return cost.quantize(Decimal("0.000001"))
