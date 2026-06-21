"""Live smoke tests against the real LI.FI API.

Deselected by default (``addopts = -m 'not integration'``). Run explicitly with:

    pytest -m integration

These hit the keyless public endpoints; no API key required.
"""

from __future__ import annotations

import pytest

from lifi_py import LifiClient

pytestmark = pytest.mark.integration


def test_live_chains() -> None:
    with LifiClient() as client:
        chains = client.get_chains()
    assert len(chains) > 0
    assert any(c.id == 42161 for c in chains)  # Arbitrum present


def test_live_quote_usdc_arbitrum_to_base() -> None:
    with LifiClient() as client:
        quote = client.get_quote(
            from_chain=42161,
            to_chain=8453,
            from_token="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            to_token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            from_amount="1000000",
            from_address="0x47E2D28169738039755586743E2dfCF3bd643f86",
        )
    assert quote.transaction_request is not None
    assert quote.transaction_request.to is not None
    assert quote.estimate.to_amount is not None
    assert int(quote.estimate.to_amount) > 0
