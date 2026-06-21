"""Tests for the synchronous LifiClient using mocked HTTP (respx)."""

from __future__ import annotations

import httpx
import pytest
import respx

from lifi_py import LifiClient
from lifi_py.exceptions import LifiAPIError, LifiRateLimitError
from lifi_py.models import Chain, Connection, Quote, Route, Status, Step, Token, Tool

from .conftest import (
    CHAINS_RESPONSE,
    CONNECTIONS_RESPONSE,
    QUOTE_RESPONSE,
    ROUTES_RESPONSE,
    STATUS_RESPONSE,
    STEP_TX_RESPONSE,
    TOKENS_RESPONSE,
    TOOLS_RESPONSE,
)

BASE = "https://li.quest/v1"


def test_default_base_url_and_no_auth_header() -> None:
    client = LifiClient()
    assert client.base_url == BASE
    # keyless: no api key header configured
    assert "x-lifi-api-key" not in client._http.headers


def test_api_key_sets_header() -> None:
    client = LifiClient(api_key="secret-key")
    assert client._http.headers["x-lifi-api-key"] == "secret-key"


def test_custom_base_url_and_header_name() -> None:
    client = LifiClient(
        base_url="https://staging.example.com/v1/",
        api_key="k",
        api_key_header="x-custom-key",
    )
    # trailing slash normalized away
    assert client.base_url == "https://staging.example.com/v1"
    assert client._http.headers["x-custom-key"] == "k"


@respx.mock
def test_get_quote_returns_quote_with_transaction_request() -> None:
    route = respx.get(f"{BASE}/quote").mock(return_value=httpx.Response(200, json=QUOTE_RESPONSE))
    client = LifiClient()
    quote = client.get_quote(
        from_chain=42161,
        to_chain=8453,
        from_token="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        to_token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        from_amount="1000000",
        from_address="0x47E2D28169738039755586743E2dfCF3bd643f86",
    )
    assert isinstance(quote, Quote)
    assert quote.tool == "across"
    assert quote.transaction_request is not None
    assert quote.transaction_request.to == "0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE"

    sent = route.calls.last.request
    params = httpx.URL(sent.url).params
    assert params["fromChain"] == "42161"
    assert params["toChain"] == "8453"
    assert params["fromToken"] == "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"
    assert params["fromAmount"] == "1000000"
    assert params["fromAddress"] == "0x47E2D28169738039755586743E2dfCF3bd643f86"


@respx.mock
def test_get_quote_optional_params_only_sent_when_set() -> None:
    route = respx.get(f"{BASE}/quote").mock(return_value=httpx.Response(200, json=QUOTE_RESPONSE))
    client = LifiClient()
    client.get_quote(
        from_chain=42161,
        to_chain=8453,
        from_token="A",
        to_token="B",
        from_amount="100",
        from_address="0xabc",
        to_address="0xdef",
        slippage=0.01,
        order="FASTEST",
        integrator="lifi-py",
    )
    params = httpx.URL(route.calls.last.request.url).params
    assert params["toAddress"] == "0xdef"
    assert params["slippage"] == "0.01"
    assert params["order"] == "FASTEST"
    assert params["integrator"] == "lifi-py"

    # Without optionals, they must be absent (not sent as "None").
    respx.get(f"{BASE}/quote").mock(return_value=httpx.Response(200, json=QUOTE_RESPONSE))
    client.get_quote(
        from_chain=1,
        to_chain=2,
        from_token="A",
        to_token="B",
        from_amount="1",
        from_address="0x",
    )
    params2 = httpx.URL(route.calls.last.request.url).params
    assert "slippage" not in params2
    assert "order" not in params2


@respx.mock
def test_get_status() -> None:
    route = respx.get(f"{BASE}/status").mock(return_value=httpx.Response(200, json=STATUS_RESPONSE))
    client = LifiClient()
    status = client.get_status(
        tx_hash="0xsendhash", bridge="across", from_chain=42161, to_chain=8453
    )
    assert isinstance(status, Status)
    assert status.is_done
    params = httpx.URL(route.calls.last.request.url).params
    assert params["txHash"] == "0xsendhash"
    assert params["bridge"] == "across"
    assert params["fromChain"] == "42161"
    assert params["toChain"] == "8453"


@respx.mock
def test_get_chains() -> None:
    respx.get(f"{BASE}/chains").mock(return_value=httpx.Response(200, json=CHAINS_RESPONSE))
    client = LifiClient()
    chains = client.get_chains()
    assert len(chains) == 2
    assert all(isinstance(c, Chain) for c in chains)
    assert chains[1].id == 42161


@respx.mock
def test_get_tokens() -> None:
    respx.get(f"{BASE}/tokens").mock(return_value=httpx.Response(200, json=TOKENS_RESPONSE))
    client = LifiClient()
    tokens = client.get_tokens()
    assert set(tokens.keys()) == {1, 42161}
    assert isinstance(tokens[42161][0], Token)
    assert tokens[42161][0].symbol == "USDC"


@respx.mock
def test_get_tools() -> None:
    respx.get(f"{BASE}/tools").mock(return_value=httpx.Response(200, json=TOOLS_RESPONSE))
    client = LifiClient()
    tools = client.get_tools()
    assert len(tools.bridges) == 2
    assert len(tools.exchanges) == 1
    assert isinstance(tools.bridges[0], Tool)
    assert tools.bridges[0].key == "across"


@respx.mock
def test_get_connections() -> None:
    route = respx.get(f"{BASE}/connections").mock(
        return_value=httpx.Response(200, json=CONNECTIONS_RESPONSE)
    )
    client = LifiClient()
    conns = client.get_connections(from_chain=42161, to_chain=8453)
    assert len(conns) == 1
    assert isinstance(conns[0], Connection)
    params = httpx.URL(route.calls.last.request.url).params
    assert params["fromChain"] == "42161"
    assert params["toChain"] == "8453"


@respx.mock
def test_get_routes_posts_body() -> None:
    route = respx.post(f"{BASE}/advanced/routes").mock(
        return_value=httpx.Response(200, json=ROUTES_RESPONSE)
    )
    client = LifiClient()
    routes = client.get_routes(
        from_chain=42161,
        to_chain=8453,
        from_token="0xaf88...",
        to_token="0x8335...",
        from_amount="1000000",
        options={"slippage": 0.005},
    )
    assert len(routes) == 1
    assert isinstance(routes[0], Route)
    import json as _json

    body = _json.loads(route.calls.last.request.content)
    assert body["fromChainId"] == 42161
    assert body["toChainId"] == 8453
    assert body["fromTokenAddress"] == "0xaf88..."
    assert body["fromAmount"] == "1000000"
    assert body["options"] == {"slippage": 0.005}


@respx.mock
def test_get_step_transaction_posts_step() -> None:
    route = respx.post(f"{BASE}/advanced/stepTransaction").mock(
        return_value=httpx.Response(200, json=STEP_TX_RESPONSE)
    )
    client = LifiClient()
    step_in = Step.model_validate(ROUTES_RESPONSE["routes"][0]["steps"][0])
    step = client.get_step_transaction(step_in)
    assert isinstance(step, Step)
    assert step.transaction_request is not None
    assert step.transaction_request.data == "0xstepdata"
    # the step is serialized back to camelCase in the body
    import json as _json

    body = _json.loads(route.calls.last.request.content)
    assert body["id"] == "step-1"
    assert body["tool"] == "across"


@respx.mock
def test_api_error_raised_on_400() -> None:
    respx.get(f"{BASE}/quote").mock(
        return_value=httpx.Response(400, json={"message": "bad request"})
    )
    client = LifiClient()
    with pytest.raises(LifiAPIError) as exc:
        client.get_quote(
            from_chain=1,
            to_chain=2,
            from_token="A",
            to_token="B",
            from_amount="1",
            from_address="0x",
        )
    assert exc.value.status_code == 400


@respx.mock
def test_429_raises_rate_limit_error_with_retry_after() -> None:
    respx.get(f"{BASE}/chains").mock(
        return_value=httpx.Response(
            429,
            headers={"ratelimit-reset": "42", "ratelimit-limit": "100", "ratelimit-remaining": "0"},
            json={"message": "rate limited"},
        )
    )
    client = LifiClient(max_retries=0)
    with pytest.raises(LifiRateLimitError) as exc:
        client.get_chains()
    assert exc.value.retry_after == 42.0
    assert exc.value.status_code == 429


@respx.mock
def test_429_then_success_retries_with_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    import lifi_py._transport as transport

    monkeypatch.setattr(transport.time, "sleep", lambda s: sleeps.append(s))

    route = respx.get(f"{BASE}/chains")
    route.side_effect = [
        httpx.Response(429, headers={"ratelimit-reset": "1"}, json={"message": "slow down"}),
        httpx.Response(200, json=CHAINS_RESPONSE),
    ]
    client = LifiClient(max_retries=2)
    chains = client.get_chains()
    assert len(chains) == 2
    assert route.call_count == 2
    # honored the reset window from the header
    assert sleeps and sleeps[0] >= 1.0


@respx.mock
def test_ratelimit_headers_exposed_after_call() -> None:
    respx.get(f"{BASE}/chains").mock(
        return_value=httpx.Response(
            200,
            headers={
                "ratelimit-limit": "100",
                "ratelimit-remaining": "57",
                "ratelimit-reset": "60",
            },
            json=CHAINS_RESPONSE,
        )
    )
    client = LifiClient()
    client.get_chains()
    assert client.rate_limit is not None
    assert client.rate_limit.limit == 100
    assert client.rate_limit.remaining == 57
    assert client.rate_limit.reset == 60.0


@respx.mock
def test_proactive_throttle_when_remaining_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    import lifi_py._transport as transport

    monkeypatch.setattr(transport.time, "sleep", lambda s: sleeps.append(s))

    # First call leaves remaining=0 with a reset window; the next call should
    # proactively sleep before firing.
    route = respx.get(f"{BASE}/chains")
    route.side_effect = [
        httpx.Response(
            200,
            headers={"ratelimit-limit": "100", "ratelimit-remaining": "0", "ratelimit-reset": "3"},
            json=CHAINS_RESPONSE,
        ),
        httpx.Response(200, json=CHAINS_RESPONSE),
    ]
    client = LifiClient()
    client.get_chains()
    client.get_chains()
    assert sleeps and sleeps[0] >= 3.0


@respx.mock
def test_poll_status_until_done(monkeypatch: pytest.MonkeyPatch) -> None:
    import lifi_py._transport as transport

    monkeypatch.setattr(transport.time, "sleep", lambda s: None)
    route = respx.get(f"{BASE}/status")
    route.side_effect = [
        httpx.Response(200, json={**STATUS_RESPONSE, "status": "PENDING"}),
        httpx.Response(200, json={**STATUS_RESPONSE, "status": "DONE"}),
    ]
    client = LifiClient()
    status = client.poll_status(tx_hash="0xsendhash", interval=0.01)
    assert status.is_done
    assert route.call_count == 2


@respx.mock
def test_poll_status_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    import lifi_py._transport as transport

    monkeypatch.setattr(transport.time, "sleep", lambda s: None)
    respx.get(f"{BASE}/status").mock(
        return_value=httpx.Response(200, json={**STATUS_RESPONSE, "status": "PENDING"})
    )
    client = LifiClient()
    with pytest.raises(TimeoutError):
        client.poll_status(tx_hash="0xsendhash", interval=1.0, timeout=2.0)


def test_context_manager_closes() -> None:
    with LifiClient() as client:
        assert client._http.is_closed is False
    assert client._http.is_closed is True
