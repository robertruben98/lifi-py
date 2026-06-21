"""Tests for the asynchronous AsyncLifiClient using mocked HTTP (respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from lifi_py import AsyncLifiClient
from lifi_py.exceptions import LifiRateLimitError
from lifi_py.models import Chain, Quote, Status, Step

from .conftest import (
    CHAINS_RESPONSE,
    QUOTE_RESPONSE,
    ROUTES_RESPONSE,
    STATUS_RESPONSE,
    STEP_TX_RESPONSE,
)

BASE = "https://li.quest/v1"


@respx.mock
async def test_async_get_quote() -> None:
    respx.get(f"{BASE}/quote").mock(return_value=httpx.Response(200, json=QUOTE_RESPONSE))
    async with AsyncLifiClient() as client:
        quote = await client.get_quote(
            from_chain=42161,
            to_chain=8453,
            from_token="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
            to_token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
            from_amount="1000000",
            from_address="0x47E2D28169738039755586743E2dfCF3bd643f86",
        )
    assert isinstance(quote, Quote)
    assert quote.transaction_request is not None
    assert quote.tool == "across"


@respx.mock
async def test_async_get_status_and_chains() -> None:
    respx.get(f"{BASE}/status").mock(return_value=httpx.Response(200, json=STATUS_RESPONSE))
    respx.get(f"{BASE}/chains").mock(return_value=httpx.Response(200, json=CHAINS_RESPONSE))
    async with AsyncLifiClient() as client:
        status = await client.get_status(tx_hash="0xsendhash")
        chains = await client.get_chains()
    assert isinstance(status, Status)
    assert status.is_done
    assert len(chains) == 2
    assert isinstance(chains[0], Chain)


@respx.mock
async def test_async_step_transaction() -> None:
    respx.post(f"{BASE}/advanced/stepTransaction").mock(
        return_value=httpx.Response(200, json=STEP_TX_RESPONSE)
    )
    step_in = Step.model_validate(ROUTES_RESPONSE["routes"][0]["steps"][0])
    async with AsyncLifiClient() as client:
        step = await client.get_step_transaction(step_in)
    assert step.transaction_request is not None
    assert step.transaction_request.data == "0xstepdata"


@respx.mock
async def test_async_429_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(s: float) -> None:
        sleeps.append(s)

    monkeypatch.setattr("lifi_py.client.asyncio.sleep", fake_sleep)

    route = respx.get(f"{BASE}/chains")
    route.side_effect = [
        httpx.Response(429, headers={"ratelimit-reset": "1"}, json={"message": "slow"}),
        httpx.Response(200, json=CHAINS_RESPONSE),
    ]
    async with AsyncLifiClient(max_retries=2) as client:
        chains = await client.get_chains()
    assert len(chains) == 2
    assert route.call_count == 2
    assert sleeps and sleeps[0] >= 1.0


@respx.mock
async def test_async_429_exhausted_raises() -> None:
    respx.get(f"{BASE}/chains").mock(
        return_value=httpx.Response(429, headers={"ratelimit-reset": "5"}, json={"message": "x"})
    )
    async with AsyncLifiClient(max_retries=0) as client:
        with pytest.raises(LifiRateLimitError) as exc:
            await client.get_chains()
    assert exc.value.retry_after == 5.0


@respx.mock
async def test_async_poll_status_until_done(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_sleep(s: float) -> None:
        return None

    monkeypatch.setattr("lifi_py.client.asyncio.sleep", fake_sleep)

    route = respx.get(f"{BASE}/status")
    route.side_effect = [
        httpx.Response(200, json={**STATUS_RESPONSE, "status": "PENDING"}),
        httpx.Response(200, json={**STATUS_RESPONSE, "status": "PENDING"}),
        httpx.Response(200, json={**STATUS_RESPONSE, "status": "DONE"}),
    ]
    async with AsyncLifiClient() as client:
        status = await client.poll_status(tx_hash="0xsendhash", interval=0.01)
    assert status.is_done
    assert route.call_count == 3
