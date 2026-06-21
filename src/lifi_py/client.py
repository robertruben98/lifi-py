"""Synchronous and asynchronous clients for the LI.FI API."""

from __future__ import annotations

import asyncio
import warnings
from types import TracebackType
from typing import Any, Optional, Union

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
ChainRef = Union[int, str]


class Tools:
    """Container for the ``GET /tools`` response.

    Attributes:
        bridges: The cross-chain bridges LI.FI can route through.
        exchanges: The on-chain DEX aggregators/exchanges available for swaps.
    """

    def __init__(self, bridges: list[Tool], exchanges: list[Tool]) -> None:
        self.bridges = bridges
        self.exchanges = exchanges


def _build_headers(api_key: Optional[str], api_key_header: str) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if api_key:
        headers[api_key_header] = api_key
    return headers


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _warn_ignored_args_for_injected_client(
    *,
    base_url: str,
    api_key: Optional[str],
    api_key_header: str,
) -> None:
    """Warn that base_url/auth are ignored when an http_client is injected.

    An injected client is an escape hatch: it owns its own ``base_url`` and
    headers, so any conflicting constructor args are silently dropped. Surface
    that instead of letting requests mysteriously hit the wrong host.
    """
    ignored = []
    if base_url != DEFAULT_BASE_URL:
        ignored.append("base_url")
    if api_key is not None:
        ignored.append("api_key")
    if api_key_header != DEFAULT_API_KEY_HEADER:
        ignored.append("api_key_header")
    if ignored:
        warnings.warn(
            "An explicit http_client was provided; "
            f"{', '.join(ignored)} {'is' if len(ignored) == 1 else 'are'} ignored. "
            "Configure base_url and auth headers on the injected client instead.",
            UserWarning,
            stacklevel=3,
        )


def _quote_query(
    *,
    from_chain: ChainRef,
    to_chain: ChainRef,
    from_token: str,
    to_token: str,
    from_amount: str,
    from_address: str,
    to_address: Optional[str],
    slippage: Optional[float],
    order: Optional[str],
    integrator: Optional[str],
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
    options: Optional[dict[str, Any]],
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
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        api_key_header: str = DEFAULT_API_KEY_HEADER,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[httpx.Client] = None,
    ) -> None:
        """Create a client.

        Args:
            api_key: Optional LI.FI API key. All endpoints work without one; a
                key only raises your rate limits. Sent in the ``api_key_header``.
            base_url: API base URL. Override to target a staging/proxy host.
            api_key_header: Header name used to send ``api_key``.
            timeout: Per-request timeout in seconds.
            max_retries: Maximum number of 429 retries before raising
                :class:`~lifi_py.LifiRateLimitError`.
            http_client: An existing ``httpx.Client`` to reuse. When provided it
                is used as-is and any conflicting ``base_url``/``api_key``/
                ``api_key_header`` are ignored (with a warning); ``self.base_url``
                then reflects the injected client's own base URL.
        """
        self.max_retries = max_retries
        self._rate = RateLimitState()
        if http_client is not None:
            _warn_ignored_args_for_injected_client(
                base_url=base_url, api_key=api_key, api_key_header=api_key_header
            )
            self._http = http_client
            # base_url must reflect the client actually in use, not the ignored arg.
            self.base_url = _normalize_base_url(str(http_client.base_url))
        else:
            self.base_url = _normalize_base_url(base_url)
            self._http = httpx.Client(
                base_url=self.base_url,
                headers=_build_headers(api_key, api_key_header),
                timeout=timeout,
            )

    @property
    def rate_limit(self) -> Optional[RateLimit]:
        """The most recent rate-limit snapshot, or ``None`` before any call."""
        if self._rate.current.limit is None and self._rate.current.remaining is None:
            return None
        return self._rate.current

    def __enter__(self) -> LifiClient:
        """Enter a context manager; returns ``self``."""
        return self

    def __exit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Exit the context manager, closing the underlying HTTP client."""
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP client and release its connections."""
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
        to_address: Optional[str] = None,
        slippage: Optional[float] = None,
        order: Optional[str] = None,
        integrator: Optional[str] = None,
    ) -> Quote:
        """Get the best single-step quote with a ready-to-sign transaction.

        This is the headline call: the returned :class:`~lifi_py.Quote` carries a
        :attr:`~lifi_py.Quote.transaction_request` you can sign and broadcast
        directly — no separate assembly step.

        Args:
            from_chain: Source chain id (or LI.FI chain key).
            to_chain: Destination chain id (or LI.FI chain key).
            from_token: Source token address (zero address for native).
            to_token: Destination token address.
            from_amount: Amount to send, as an integer string in the source
                token's smallest unit (e.g. ``"1000000"`` for 1 USDC).
            from_address: Wallet sending the funds.
            to_address: Recipient on the destination chain. Defaults to
                ``from_address`` when omitted.
            slippage: Allowed slippage as a fraction, e.g. ``0.005`` for 0.5%.
            order: Routing preference, e.g. ``"CHEAPEST"`` or ``"FASTEST"``.
            integrator: Integrator string attributed to the request.

        Returns:
            The best route, including a ready-to-sign ``transaction_request``.

        Raises:
            LifiAPIError: The API rejected the request (e.g. unsupported route).
            LifiRateLimitError: Rate limited after exhausting retries.

        Example:
            >>> client = LifiClient()
            >>> quote = client.get_quote(
            ...     from_chain=42161, to_chain=8453,  # Arbitrum -> Base
            ...     from_token="0xaf88d065e77c8cC2239327C5EDb3A432268e5831",  # USDC
            ...     to_token="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",  # USDC
            ...     from_amount="1000000",  # 1 USDC
            ...     from_address="0x47E2D28169738039755586743E2dfCF3bd643f86",
            ... )
            >>> quote.estimate.to_amount  # doctest: +SKIP
            '995000'
            >>> quote.transaction_request.to  # doctest: +SKIP
            '0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE'
        """
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
        bridge: Optional[str] = None,
        from_chain: Optional[ChainRef] = None,
        to_chain: Optional[ChainRef] = None,
    ) -> Status:
        """Track the status of a cross-chain transfer by its source tx hash.

        Args:
            tx_hash: The source-chain transaction hash to look up.
            bridge: The bridge/tool key used (e.g. ``"across"``); narrows the
                lookup and speeds it up.
            from_chain: Source chain id, to disambiguate the lookup.
            to_chain: Destination chain id, to disambiguate the lookup.

        Returns:
            A :class:`~lifi_py.Status` describing the transfer's current state.

        Raises:
            LifiAPIError: The status request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
        params = build_query(txHash=tx_hash, bridge=bridge, fromChain=from_chain, toChain=to_chain)
        return Status.model_validate(self._request("GET", "/status", params=params))

    def get_chains(self) -> list[Chain]:
        """List all chains supported by LI.FI (``GET /chains``).

        Returns:
            Every supported :class:`~lifi_py.Chain`, each with its native token.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
        payload = self._request("GET", "/chains")
        return [Chain.model_validate(c) for c in payload.get("chains", [])]

    def get_tokens(self) -> dict[int, list[Token]]:
        """Fetch the supported-token catalog (``GET /tokens``).

        Returns:
            A mapping of chain id to the list of :class:`~lifi_py.Token` objects
            supported on that chain.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
        return _parse_tokens(self._request("GET", "/tokens"))

    def get_tools(self) -> Tools:
        """List integrated bridges and exchanges (``GET /tools``).

        Returns:
            A :class:`Tools` container with ``bridges`` and ``exchanges`` lists.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
        return _parse_tools(self._request("GET", "/tools"))

    def get_connections(
        self,
        *,
        from_chain: Optional[ChainRef] = None,
        to_chain: Optional[ChainRef] = None,
    ) -> list[Connection]:
        """List possible routes between chains (``GET /connections``).

        Args:
            from_chain: Restrict to this source chain id/key (optional).
            to_chain: Restrict to this destination chain id/key (optional).

        Returns:
            The reachable :class:`~lifi_py.Connection` pairs and their tokens.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
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
        options: Optional[dict[str, Any]] = None,
    ) -> list[Route]:
        """Get multiple candidate routes (``POST /advanced/routes``).

        Unlike :meth:`get_quote`, this returns several routes without calldata;
        fetch calldata per step with :meth:`get_step_transaction`.

        Args:
            from_chain: Source chain id.
            to_chain: Destination chain id.
            from_token: Source token address.
            to_token: Destination token address.
            from_amount: Amount to send, as an integer string in the source
                token's smallest unit.
            options: Optional routing options (e.g. ``{"slippage": 0.005}``)
                passed through to the API.

        Returns:
            A list of candidate :class:`~lifi_py.Route` objects.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
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
        """Get calldata for a single route step (``POST /advanced/stepTransaction``).

        Args:
            step: A :class:`~lifi_py.Step` from a :class:`~lifi_py.Route` returned
                by :meth:`get_routes`.

        Returns:
            The same step with its :attr:`~lifi_py.Step.transaction_request`
            populated and ready to sign.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
        body = step.model_dump(by_alias=True, exclude_none=True)
        payload = self._request("POST", "/advanced/stepTransaction", json=body)
        return Step.model_validate(payload)

    def poll_status(
        self,
        *,
        tx_hash: str,
        bridge: Optional[str] = None,
        from_chain: Optional[ChainRef] = None,
        to_chain: Optional[ChainRef] = None,
        interval: float = 5.0,
        timeout: float = 300.0,
        max_interval: float = 30.0,
    ) -> Status:
        """Poll ``/status`` with exponential backoff until DONE or FAILED.

        Repeatedly calls :meth:`get_status`, sleeping between attempts with the
        delay doubling from ``interval`` up to ``max_interval``, until the
        transfer reaches a terminal state.

        Args:
            tx_hash: The source-chain transaction hash to track.
            bridge: The bridge/tool key used (recommended; speeds up lookups).
            from_chain: Source chain id, to disambiguate the lookup.
            to_chain: Destination chain id, to disambiguate the lookup.
            interval: Initial delay between polls, in seconds.
            timeout: Maximum total time to wait, in seconds.
            max_interval: Cap on the (exponentially growing) poll delay.

        Returns:
            The terminal :class:`~lifi_py.Status` (``DONE`` or ``FAILED``).

        Raises:
            TimeoutError: No terminal state was reached within ``timeout``.
            LifiAPIError: A status request failed.
            LifiRateLimitError: Rate limited after exhausting retries.

        Example:
            >>> client = LifiClient()
            >>> final = client.poll_status(tx_hash="0x...", bridge="across")  # doctest: +SKIP
            >>> final.is_done  # doctest: +SKIP
            True
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
    """Asynchronous client for the LI.FI API.

    A coroutine-based mirror of :class:`LifiClient` with identical endpoints,
    parameters and return types. Use it as an async context manager so the
    underlying HTTP connections are closed on exit.

    The API key is optional (it only raises rate limits); all endpoints work
    keyless. The client tracks the ``ratelimit-*`` response headers, pauses
    proactively when the quota is exhausted, and retries 429s with backoff.

    Example:
        >>> import asyncio
        >>> async def main():
        ...     async with AsyncLifiClient() as client:
        ...         return await client.get_chains()
        >>> chains = asyncio.run(main())  # doctest: +SKIP
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        api_key_header: str = DEFAULT_API_KEY_HEADER,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        """Create an async client.

        Args:
            api_key: Optional LI.FI API key. All endpoints work without one; a
                key only raises your rate limits. Sent in the ``api_key_header``.
            base_url: API base URL. Override to target a staging/proxy host.
            api_key_header: Header name used to send ``api_key``.
            timeout: Per-request timeout in seconds.
            max_retries: Maximum number of 429 retries before raising
                :class:`~lifi_py.LifiRateLimitError`.
            http_client: An existing ``httpx.AsyncClient`` to reuse. When
                provided it is used as-is and any conflicting ``base_url``/
                ``api_key``/``api_key_header`` are ignored (with a warning);
                ``self.base_url`` then reflects the injected client's base URL.
        """
        self.max_retries = max_retries
        self._rate = RateLimitState()
        if http_client is not None:
            _warn_ignored_args_for_injected_client(
                base_url=base_url, api_key=api_key, api_key_header=api_key_header
            )
            self._http = http_client
            # base_url must reflect the client actually in use, not the ignored arg.
            self.base_url = _normalize_base_url(str(http_client.base_url))
        else:
            self.base_url = _normalize_base_url(base_url)
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                headers=_build_headers(api_key, api_key_header),
                timeout=timeout,
            )

    @property
    def rate_limit(self) -> Optional[RateLimit]:
        """The most recent rate-limit snapshot, or ``None`` before any call."""
        if self._rate.current.limit is None and self._rate.current.remaining is None:
            return None
        return self._rate.current

    async def __aenter__(self) -> AsyncLifiClient:
        """Enter the async context manager; returns ``self``."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> None:
        """Exit the async context manager, closing the HTTP client."""
        await self.close()

    async def close(self) -> None:
        """Close the underlying async HTTP client and release its connections."""
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
        to_address: Optional[str] = None,
        slippage: Optional[float] = None,
        order: Optional[str] = None,
        integrator: Optional[str] = None,
    ) -> Quote:
        """Get the best single-step quote with a ready-to-sign transaction.

        Async counterpart of :meth:`LifiClient.get_quote`.

        Args:
            from_chain: Source chain id (or LI.FI chain key).
            to_chain: Destination chain id (or LI.FI chain key).
            from_token: Source token address (zero address for native).
            to_token: Destination token address.
            from_amount: Amount to send, as an integer string in the source
                token's smallest unit.
            from_address: Wallet sending the funds.
            to_address: Recipient on the destination chain (defaults to
                ``from_address``).
            slippage: Allowed slippage as a fraction, e.g. ``0.005``.
            order: Routing preference, e.g. ``"CHEAPEST"`` or ``"FASTEST"``.
            integrator: Integrator string attributed to the request.

        Returns:
            The best route, including a ready-to-sign ``transaction_request``.

        Raises:
            LifiAPIError: The API rejected the request.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
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
        bridge: Optional[str] = None,
        from_chain: Optional[ChainRef] = None,
        to_chain: Optional[ChainRef] = None,
    ) -> Status:
        """Track the status of a cross-chain transfer by its source tx hash.

        Async counterpart of :meth:`LifiClient.get_status`.

        Args:
            tx_hash: The source-chain transaction hash to look up.
            bridge: The bridge/tool key used (e.g. ``"across"``); speeds lookups.
            from_chain: Source chain id, to disambiguate the lookup.
            to_chain: Destination chain id, to disambiguate the lookup.

        Returns:
            A :class:`~lifi_py.Status` describing the transfer's current state.

        Raises:
            LifiAPIError: The status request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
        params = build_query(txHash=tx_hash, bridge=bridge, fromChain=from_chain, toChain=to_chain)
        return Status.model_validate(await self._request("GET", "/status", params=params))

    async def get_chains(self) -> list[Chain]:
        """List all chains supported by LI.FI (``GET /chains``).

        Async counterpart of :meth:`LifiClient.get_chains`.

        Returns:
            Every supported :class:`~lifi_py.Chain`, each with its native token.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
        payload = await self._request("GET", "/chains")
        return [Chain.model_validate(c) for c in payload.get("chains", [])]

    async def get_tokens(self) -> dict[int, list[Token]]:
        """Fetch the supported-token catalog (``GET /tokens``).

        Async counterpart of :meth:`LifiClient.get_tokens`.

        Returns:
            A mapping of chain id to the list of :class:`~lifi_py.Token` objects
            supported on that chain.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
        return _parse_tokens(await self._request("GET", "/tokens"))

    async def get_tools(self) -> Tools:
        """List integrated bridges and exchanges (``GET /tools``).

        Async counterpart of :meth:`LifiClient.get_tools`.

        Returns:
            A :class:`Tools` container with ``bridges`` and ``exchanges`` lists.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
        return _parse_tools(await self._request("GET", "/tools"))

    async def get_connections(
        self,
        *,
        from_chain: Optional[ChainRef] = None,
        to_chain: Optional[ChainRef] = None,
    ) -> list[Connection]:
        """List possible routes between chains (``GET /connections``).

        Async counterpart of :meth:`LifiClient.get_connections`.

        Args:
            from_chain: Restrict to this source chain id/key (optional).
            to_chain: Restrict to this destination chain id/key (optional).

        Returns:
            The reachable :class:`~lifi_py.Connection` pairs and their tokens.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
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
        options: Optional[dict[str, Any]] = None,
    ) -> list[Route]:
        """Get multiple candidate routes (``POST /advanced/routes``).

        Async counterpart of :meth:`LifiClient.get_routes`.

        Args:
            from_chain: Source chain id.
            to_chain: Destination chain id.
            from_token: Source token address.
            to_token: Destination token address.
            from_amount: Amount to send, as an integer string in the source
                token's smallest unit.
            options: Optional routing options passed through to the API.

        Returns:
            A list of candidate :class:`~lifi_py.Route` objects.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
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
        """Get calldata for a single route step (``POST /advanced/stepTransaction``).

        Async counterpart of :meth:`LifiClient.get_step_transaction`.

        Args:
            step: A :class:`~lifi_py.Step` from a route returned by
                :meth:`get_routes`.

        Returns:
            The same step with its ``transaction_request`` populated.

        Raises:
            LifiAPIError: The request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
        body = step.model_dump(by_alias=True, exclude_none=True)
        payload = await self._request("POST", "/advanced/stepTransaction", json=body)
        return Step.model_validate(payload)

    async def poll_status(
        self,
        *,
        tx_hash: str,
        bridge: Optional[str] = None,
        from_chain: Optional[ChainRef] = None,
        to_chain: Optional[ChainRef] = None,
        interval: float = 5.0,
        timeout: float = 300.0,
        max_interval: float = 30.0,
    ) -> Status:
        """Poll ``/status`` with exponential backoff until DONE or FAILED.

        Async counterpart of :meth:`LifiClient.poll_status`. Awaits between
        polls so it does not block the event loop.

        Args:
            tx_hash: The source-chain transaction hash to track.
            bridge: The bridge/tool key used (recommended; speeds up lookups).
            from_chain: Source chain id, to disambiguate the lookup.
            to_chain: Destination chain id, to disambiguate the lookup.
            interval: Initial delay between polls, in seconds.
            timeout: Maximum total time to wait, in seconds.
            max_interval: Cap on the (exponentially growing) poll delay.

        Returns:
            The terminal :class:`~lifi_py.Status` (``DONE`` or ``FAILED``).

        Raises:
            TimeoutError: No terminal state was reached within ``timeout``.
            LifiAPIError: A status request failed.
            LifiRateLimitError: Rate limited after exhausting retries.
        """
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
