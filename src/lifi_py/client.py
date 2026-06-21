"""Synchronous and asynchronous clients for the LI.FI API."""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Any, Union

import httpx

from . import _transport as _t
from ._transport import (
    DEFAULT_BASE_URL,
    RateLimit,
    RateLimitState,
    backoff_seconds,
    build_query,
    parse_response,
)
from .models import Chain, Connection, Quote, Route, Status, Step, Token, Tool

DEFAULT_API_KEY_HEADER = "x-lifi-api-key"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 3

# Chain/token identifiers accept ids or keys/symbols. Written with ``Union`` (not
# ``X | Y``) so this runtime alias stays importable on the 3.9 floor.
ChainRef = Union[int, str]  # noqa: UP007


class Tools:
    """Container for the ``/tools`` response (bridges + exchanges)."""

    def __init__(self, bridges: list[Tool], exchanges: list[Tool]) -> None:
        self.bridges = bridges
        self.exchanges = exchanges


def _build_headers(api_key: str | None, api_key_header: str) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers[api_key_header] = api_key
    return headers


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _quote_query(
    *,
    from_chain: ChainRef,
    to_chain: ChainRef,
    from_token: str,
    to_token: str,
    from_amount: str,
    from_address: str,
    to_address: str | None,
    slippage: float | None,
    order: str | None,
    integrator: str | None,
) -> dict[str, str]:
    return build_query(
        fromChain=from_chain,
        toChain=to_chain,
        fromToken=from_token,
        toToken=to_token,
        fromAmount=from_amount,
        fromAddress=from_address,
        toAddress=to_address,
        slippage=slippage,
        order=order,
        integrator=integrator,
    )


def _routes_body(
    *,
    from_chain: int,
    to_chain: int,
    from_token: str,
    to_token: str,
    from_amount: str,
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "fromChainId": from_chain,
        "toChainId": to_chain,
        "fromTokenAddress": from_token,
        "toTokenAddress": to_token,
        "fromAmount": from_amount,
    }
    if options is not None:
        body["options"] = options
    return body


def _parse_tokens(payload: Any) -> dict[int, list[Token]]:
    raw = payload.get("tokens", {}) if isinstance(payload, dict) else {}
    return {
        int(chain_id): [Token.model_validate(t) for t in token_list]
        for chain_id, token_list in raw.items()
    }


def _parse_tools(payload: Any) -> Tools:
    bridges = [Tool.model_validate(b) for b in payload.get("bridges", [])]
    exchanges = [Tool.model_validate(e) for e in payload.get("exchanges", [])]
    return Tools(bridges=bridges, exchanges=exchanges)


class LifiClient:
    """Synchronous client for the LI.FI API.

    The API key is optional (it only raises rate limits); all endpoints work
    keyless. The client tracks the ``ratelimit-*`` response headers and will
    proactively pause when the quota is exhausted, and retry 429s with backoff.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        api_key_header: str = DEFAULT_API_KEY_HEADER,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.max_retries = max_retries
        self._rate = RateLimitState()
        self._http = http_client or httpx.Client(
            base_url=self.base_url,
            headers=_build_headers(api_key, api_key_header),
            timeout=timeout,
        )

    @property
    def rate_limit(self) -> RateLimit | None:
        """The most recent rate-limit snapshot, or ``None`` before any call."""
        if self._rate.current.limit is None and self._rate.current.remaining is None:
            return None
        return self._rate.current

    def __enter__(self) -> LifiClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        wait = self._rate.proactive_wait()
        if wait > 0:
            _t.time.sleep(wait)

        attempt = 0
        while True:
            response = self._http.request(method, path, **kwargs)
            self._rate.update(response.headers)
            if response.status_code == 429 and attempt < self.max_retries:
                _t.time.sleep(backoff_seconds(attempt, response))
                attempt += 1
                continue
            return parse_response(response)

    # -- Endpoints -----------------------------------------------------------

    def get_quote(
        self,
        *,
        from_chain: ChainRef,
        to_chain: ChainRef,
        from_token: str,
        to_token: str,
        from_amount: str,
        from_address: str,
        to_address: str | None = None,
        slippage: float | None = None,
        order: str | None = None,
        integrator: str | None = None,
    ) -> Quote:
        """Get the best single-step quote with a ready-to-sign transaction."""
        params = _quote_query(
            from_chain=from_chain,
            to_chain=to_chain,
            from_token=from_token,
            to_token=to_token,
            from_amount=from_amount,
            from_address=from_address,
            to_address=to_address,
            slippage=slippage,
            order=order,
            integrator=integrator,
        )
        return Quote.model_validate(self._request("GET", "/quote", params=params))

    def get_status(
        self,
        *,
        tx_hash: str,
        bridge: str | None = None,
        from_chain: ChainRef | None = None,
        to_chain: ChainRef | None = None,
    ) -> Status:
        """Track the status of a cross-chain transfer by its source tx hash."""
        params = build_query(txHash=tx_hash, bridge=bridge, fromChain=from_chain, toChain=to_chain)
        return Status.model_validate(self._request("GET", "/status", params=params))

    def get_chains(self) -> list[Chain]:
        payload = self._request("GET", "/chains")
        return [Chain.model_validate(c) for c in payload.get("chains", [])]

    def get_tokens(self) -> dict[int, list[Token]]:
        return _parse_tokens(self._request("GET", "/tokens"))

    def get_tools(self) -> Tools:
        return _parse_tools(self._request("GET", "/tools"))

    def get_connections(
        self,
        *,
        from_chain: ChainRef | None = None,
        to_chain: ChainRef | None = None,
    ) -> list[Connection]:
        params = build_query(fromChain=from_chain, toChain=to_chain)
        payload = self._request("GET", "/connections", params=params)
        return [Connection.model_validate(c) for c in payload.get("connections", [])]

    def get_routes(
        self,
        *,
        from_chain: int,
        to_chain: int,
        from_token: str,
        to_token: str,
        from_amount: str,
        options: dict[str, Any] | None = None,
    ) -> list[Route]:
        """Get multiple candidate routes (POST /advanced/routes)."""
        body = _routes_body(
            from_chain=from_chain,
            to_chain=to_chain,
            from_token=from_token,
            to_token=to_token,
            from_amount=from_amount,
            options=options,
        )
        payload = self._request("POST", "/advanced/routes", json=body)
        return [Route.model_validate(r) for r in payload.get("routes", [])]

    def get_step_transaction(self, step: Step) -> Step:
        """Get calldata for a single route step (POST /advanced/stepTransaction)."""
        body = step.model_dump(by_alias=True, exclude_none=True)
        payload = self._request("POST", "/advanced/stepTransaction", json=body)
        return Step.model_validate(payload)

    def poll_status(
        self,
        *,
        tx_hash: str,
        bridge: str | None = None,
        from_chain: ChainRef | None = None,
        to_chain: ChainRef | None = None,
        interval: float = 5.0,
        timeout: float = 300.0,
        max_interval: float = 30.0,
    ) -> Status:
        """Poll ``/status`` with exponential backoff until DONE or FAILED.

        Raises ``TimeoutError`` if no terminal state is reached within
        ``timeout`` seconds.
        """
        elapsed = 0.0
        delay = interval
        while True:
            status = self.get_status(
                tx_hash=tx_hash, bridge=bridge, from_chain=from_chain, to_chain=to_chain
            )
            if status.is_terminal:
                return status
            if elapsed >= timeout:
                raise TimeoutError(
                    f"status for {tx_hash} not terminal after {timeout}s "
                    f"(last status: {status.status})"
                )
            _t.time.sleep(delay)
            elapsed += delay
            delay = min(delay * 2, max_interval)


class AsyncLifiClient:
    """Asynchronous client for the LI.FI API. Mirrors :class:`LifiClient`."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        api_key_header: str = DEFAULT_API_KEY_HEADER,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.base_url = _normalize_base_url(base_url)
        self.max_retries = max_retries
        self._rate = RateLimitState()
        self._http = http_client or httpx.AsyncClient(
            base_url=self.base_url,
            headers=_build_headers(api_key, api_key_header),
            timeout=timeout,
        )

    @property
    def rate_limit(self) -> RateLimit | None:
        if self._rate.current.limit is None and self._rate.current.remaining is None:
            return None
        return self._rate.current

    async def __aenter__(self) -> AsyncLifiClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        wait = self._rate.proactive_wait()
        if wait > 0:
            await asyncio.sleep(wait)

        attempt = 0
        while True:
            response = await self._http.request(method, path, **kwargs)
            self._rate.update(response.headers)
            if response.status_code == 429 and attempt < self.max_retries:
                await asyncio.sleep(backoff_seconds(attempt, response))
                attempt += 1
                continue
            return parse_response(response)

    async def get_quote(
        self,
        *,
        from_chain: ChainRef,
        to_chain: ChainRef,
        from_token: str,
        to_token: str,
        from_amount: str,
        from_address: str,
        to_address: str | None = None,
        slippage: float | None = None,
        order: str | None = None,
        integrator: str | None = None,
    ) -> Quote:
        params = _quote_query(
            from_chain=from_chain,
            to_chain=to_chain,
            from_token=from_token,
            to_token=to_token,
            from_amount=from_amount,
            from_address=from_address,
            to_address=to_address,
            slippage=slippage,
            order=order,
            integrator=integrator,
        )
        return Quote.model_validate(await self._request("GET", "/quote", params=params))

    async def get_status(
        self,
        *,
        tx_hash: str,
        bridge: str | None = None,
        from_chain: ChainRef | None = None,
        to_chain: ChainRef | None = None,
    ) -> Status:
        params = build_query(txHash=tx_hash, bridge=bridge, fromChain=from_chain, toChain=to_chain)
        return Status.model_validate(await self._request("GET", "/status", params=params))

    async def get_chains(self) -> list[Chain]:
        payload = await self._request("GET", "/chains")
        return [Chain.model_validate(c) for c in payload.get("chains", [])]

    async def get_tokens(self) -> dict[int, list[Token]]:
        return _parse_tokens(await self._request("GET", "/tokens"))

    async def get_tools(self) -> Tools:
        return _parse_tools(await self._request("GET", "/tools"))

    async def get_connections(
        self,
        *,
        from_chain: ChainRef | None = None,
        to_chain: ChainRef | None = None,
    ) -> list[Connection]:
        params = build_query(fromChain=from_chain, toChain=to_chain)
        payload = await self._request("GET", "/connections", params=params)
        return [Connection.model_validate(c) for c in payload.get("connections", [])]

    async def get_routes(
        self,
        *,
        from_chain: int,
        to_chain: int,
        from_token: str,
        to_token: str,
        from_amount: str,
        options: dict[str, Any] | None = None,
    ) -> list[Route]:
        body = _routes_body(
            from_chain=from_chain,
            to_chain=to_chain,
            from_token=from_token,
            to_token=to_token,
            from_amount=from_amount,
            options=options,
        )
        payload = await self._request("POST", "/advanced/routes", json=body)
        return [Route.model_validate(r) for r in payload.get("routes", [])]

    async def get_step_transaction(self, step: Step) -> Step:
        body = step.model_dump(by_alias=True, exclude_none=True)
        payload = await self._request("POST", "/advanced/stepTransaction", json=body)
        return Step.model_validate(payload)

    async def poll_status(
        self,
        *,
        tx_hash: str,
        bridge: str | None = None,
        from_chain: ChainRef | None = None,
        to_chain: ChainRef | None = None,
        interval: float = 5.0,
        timeout: float = 300.0,
        max_interval: float = 30.0,
    ) -> Status:
        elapsed = 0.0
        delay = interval
        while True:
            status = await self.get_status(
                tx_hash=tx_hash, bridge=bridge, from_chain=from_chain, to_chain=to_chain
            )
            if status.is_terminal:
                return status
            if elapsed >= timeout:
                raise TimeoutError(
                    f"status for {tx_hash} not terminal after {timeout}s "
                    f"(last status: {status.status})"
                )
            await asyncio.sleep(delay)
            elapsed += delay
            delay = min(delay * 2, max_interval)
