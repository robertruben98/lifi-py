"""Pydantic v2 models for LI.FI API responses.

Field names mirror Python conventions (snake_case) while accepting the API's
camelCase payloads via ``populate_by_name`` + ``alias``. All models tolerate
unknown fields so they keep working as the API evolves.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    """Base with camelCase aliasing and forward-compatible extra handling."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )


class Token(_Model):
    """An ERC-20 (or native) token on a specific chain.

    Token amounts elsewhere in the API are expressed as integer strings in this
    token's smallest unit (i.e. scaled by ``10 ** decimals``).
    """

    address: str = Field(
        description="Token contract address; the zero address denotes the chain's native coin."
    )
    chain_id: int = Field(alias="chainId", description="Chain id this token lives on.")
    symbol: str = Field(description="Ticker symbol, e.g. ``USDC``.")
    decimals: int = Field(description="Number of decimals used to scale raw amounts.")
    name: Optional[str] = Field(default=None, description="Human-readable token name.")
    price_usd: Optional[str] = Field(
        default=None, alias="priceUSD", description="Indicative USD price per whole token."
    )
    coin_key: Optional[str] = Field(
        default=None, alias="coinKey", description="LI.FI internal coin identifier."
    )
    logo_uri: Optional[str] = Field(
        default=None, alias="logoURI", description="URL of the token logo image."
    )


class Chain(_Model):
    """A blockchain supported by LI.FI (returned by ``GET /chains``)."""

    id: int = Field(description="Numeric chain id, e.g. ``42161`` for Arbitrum.")
    key: str = Field(description="Short LI.FI chain key, e.g. ``arb``.")
    name: str = Field(description="Human-readable chain name, e.g. ``Arbitrum``.")
    chain_type: Optional[str] = Field(
        default=None, alias="chainType", description="Chain family, e.g. ``EVM`` or ``SVM``."
    )
    native_token: Token = Field(
        alias="nativeToken", description="The chain's native gas token (e.g. ETH)."
    )
    logo_uri: Optional[str] = Field(
        default=None, alias="logoURI", description="URL of the chain logo image."
    )
    mainnet: Optional[bool] = Field(
        default=None, description="True for a mainnet, False for a testnet."
    )


class Tool(_Model):
    """A bridge or exchange integrated by LI.FI (entry in ``GET /tools``)."""

    key: str = Field(description="Stable tool identifier, e.g. ``across`` or ``1inch``.")
    name: str = Field(description="Human-readable tool name.")
    logo_uri: Optional[str] = Field(
        default=None, alias="logoURI", description="URL of the tool logo image."
    )


class ToolDetails(_Model):
    """Identifying details of the tool selected for a quote or step."""

    key: str = Field(description="Stable tool identifier, e.g. ``across``.")
    name: str = Field(description="Human-readable tool name.")
    logo_uri: Optional[str] = Field(
        default=None, alias="logoURI", description="URL of the tool logo image."
    )


def _hex_or_int(value: Optional[str]) -> Optional[int]:
    """Decode a hex (``0x...``) or decimal numeric string to ``int``."""
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = value.strip()
    if text.lower().startswith("0x"):
        return int(text, 16)
    return int(text)


class TransactionRequest(_Model):
    """A ready-to-sign EVM transaction returned by ``/quote`` or step assembly.

    Numeric fields arrive as hex strings (``0x...``) as produced by the API; use
    :meth:`as_web3_tx` to obtain a dict with those fields decoded to ``int`` and
    keys renamed for ``web3.py``.
    """

    to: Optional[str] = Field(default=None, description="Target contract address to call.")
    data: Optional[str] = Field(default=None, description="ABI-encoded calldata (hex).")
    value: Optional[str] = Field(
        default=None, description="Native token value to send, as a hex string."
    )
    gas_limit: Optional[str] = Field(
        default=None, alias="gasLimit", description="Suggested gas limit, as a hex string."
    )
    gas_price: Optional[str] = Field(
        default=None, alias="gasPrice", description="Suggested gas price, as a hex string."
    )
    chain_id: Optional[int] = Field(
        default=None, alias="chainId", description="Chain id the transaction must be sent on."
    )

    def as_web3_tx(self) -> dict[str, Any]:
        """Return a dict shaped for ``web3.eth.send_transaction`` / signing.

        Hex-encoded numeric fields (``value``, ``gasLimit``, ``gasPrice``) are
        decoded to ``int`` and ``gasLimit`` is renamed to ``gas``; ``to``/``data``
        are passed through unchanged. Only fields that are set are included, so
        you can merge in your own ``nonce``/``from`` before signing.

        Returns:
            A mapping ready to pass to web3.py signing/sending APIs.

        Example:
            >>> tx = quote.transaction_request.as_web3_tx()
            >>> tx["nonce"] = w3.eth.get_transaction_count(account.address)
            >>> signed = account.sign_transaction(tx)
            >>> w3.eth.send_raw_transaction(signed.raw_transaction)
        """
        tx: dict[str, Any] = {}
        if self.to is not None:
            tx["to"] = self.to
        if self.data is not None:
            tx["data"] = self.data
        if self.value is not None:
            tx["value"] = _hex_or_int(self.value)
        if self.gas_limit is not None:
            tx["gas"] = _hex_or_int(self.gas_limit)
        if self.gas_price is not None:
            tx["gasPrice"] = _hex_or_int(self.gas_price)
        if self.chain_id is not None:
            tx["chainId"] = self.chain_id
        return tx


class GasCost(_Model):
    """Estimated gas cost of executing a step, denominated in a token."""

    type: Optional[str] = Field(
        default=None, description="Cost category, e.g. ``SEND`` or ``APPROVE``."
    )
    amount: Optional[str] = Field(
        default=None, description="Gas cost as an integer string in the token's smallest unit."
    )
    amount_usd: Optional[str] = Field(
        default=None, alias="amountUSD", description="Gas cost in USD."
    )
    token: Optional[Token] = Field(
        default=None, description="Token the gas cost is paid in (usually the native coin)."
    )


class FeeCost(_Model):
    """A protocol/bridge fee charged as part of a route."""

    name: Optional[str] = Field(default=None, description="Fee name, e.g. ``LP Fee``.")
    description: Optional[str] = Field(default=None, description="Human-readable fee explanation.")
    amount: Optional[str] = Field(
        default=None, description="Fee amount as an integer string in the token's smallest unit."
    )
    amount_usd: Optional[str] = Field(
        default=None, alias="amountUSD", description="Fee amount in USD."
    )
    percentage: Optional[str] = Field(
        default=None, description="Fee as a fraction of the amount, e.g. ``0.005``."
    )
    token: Optional[Token] = Field(default=None, description="Token the fee is charged in.")
    included: Optional[bool] = Field(
        default=None, description="True if the fee is already deducted from the output amount."
    )


class Estimate(_Model):
    """Quantitative estimate for a route or step: amounts, duration, costs."""

    tool: Optional[str] = Field(default=None, description="Tool the estimate was produced by.")
    from_amount: Optional[str] = Field(
        default=None, alias="fromAmount", description="Input amount in the source token's unit."
    )
    to_amount: Optional[str] = Field(
        default=None,
        alias="toAmount",
        description="Expected output amount in the dest token's unit.",
    )
    to_amount_min: Optional[str] = Field(
        default=None,
        alias="toAmountMin",
        description="Guaranteed minimum output after slippage.",
    )
    approval_address: Optional[str] = Field(
        default=None,
        alias="approvalAddress",
        description="Spender to approve for the source token (ERC-20 only).",
    )
    execution_duration: Optional[float] = Field(
        default=None,
        alias="executionDuration",
        description="Estimated end-to-end execution time in seconds.",
    )
    gas_costs: list[GasCost] = Field(
        default_factory=list, alias="gasCosts", description="Per-transaction gas cost estimates."
    )
    fee_costs: list[FeeCost] = Field(
        default_factory=list, alias="feeCosts", description="Protocol/bridge fees for this route."
    )


class Action(_Model):
    """The requested action a quote/step fulfills (the user's intent)."""

    from_chain_id: Optional[int] = Field(
        default=None, alias="fromChainId", description="Source chain id."
    )
    to_chain_id: Optional[int] = Field(
        default=None, alias="toChainId", description="Destination chain id."
    )
    from_token: Optional[Token] = Field(
        default=None, alias="fromToken", description="Token being sold/sent."
    )
    to_token: Optional[Token] = Field(
        default=None, alias="toToken", description="Token to receive."
    )
    from_amount: Optional[str] = Field(
        default=None, alias="fromAmount", description="Input amount in the source token's unit."
    )
    from_address: Optional[str] = Field(
        default=None, alias="fromAddress", description="Wallet sending the funds."
    )
    to_address: Optional[str] = Field(
        default=None,
        alias="toAddress",
        description="Recipient on the destination chain (defaults to from_address).",
    )
    slippage: Optional[float] = Field(
        default=None, description="Allowed slippage as a fraction, e.g. ``0.005`` for 0.5%."
    )


class Step(_Model):
    """One executable step of a route (a bridge or a swap).

    A simple transfer has a single step; complex routes chain several. After
    fetching calldata (``POST /advanced/stepTransaction``) the step carries a
    populated :attr:`transaction_request`.
    """

    id: str = Field(description="Unique step identifier within the route.")
    type: str = Field(description="Step kind, e.g. ``swap``, ``cross`` or ``lifi``.")
    tool: str = Field(description="Tool executing this step, e.g. ``across``.")
    tool_details: Optional[ToolDetails] = Field(
        default=None, alias="toolDetails", description="Identifying details of the tool."
    )
    action: Optional[Action] = Field(default=None, description="The action this step performs.")
    estimate: Optional[Estimate] = Field(
        default=None, description="Amount/cost/duration estimate for this step."
    )
    transaction_request: Optional[TransactionRequest] = Field(
        default=None,
        alias="transactionRequest",
        description="Ready-to-sign tx for this step (present after stepTransaction).",
    )


class Quote(_Model):
    """A ``GET /quote`` result: the single best route with a ready-to-sign tx.

    This is the headline object. :attr:`transaction_request` can be signed and
    broadcast directly — no separate assembly step is required.
    """

    type: str = Field(description="Result type, typically ``lifi``.")
    id: str = Field(description="Unique quote identifier.")
    tool: str = Field(description="Tool chosen for this route, e.g. ``across``.")
    tool_details: Optional[ToolDetails] = Field(
        default=None, alias="toolDetails", description="Identifying details of the chosen tool."
    )
    action: Action = Field(description="The action this quote fulfills.")
    estimate: Estimate = Field(description="Expected amounts, duration and costs.")
    included_steps: list[Step] = Field(
        default_factory=list,
        alias="includedSteps",
        description="Underlying steps composing this route.",
    )
    integrator: Optional[str] = Field(
        default=None, description="Integrator string attributed to the request."
    )
    transaction_request: Optional[TransactionRequest] = Field(
        default=None,
        alias="transactionRequest",
        description="Ready-to-sign transaction implementing the quote.",
    )
    transaction_id: Optional[str] = Field(
        default=None,
        alias="transactionId",
        description="LI.FI transaction id, useful for status tracking.",
    )


class Route(_Model):
    """A candidate route returned by ``POST /advanced/routes``.

    Unlike :class:`Quote`, a route does not include calldata up front; fetch it
    per step via ``get_step_transaction`` (``POST /advanced/stepTransaction``).
    """

    id: str = Field(description="Unique route identifier.")
    from_chain_id: Optional[int] = Field(
        default=None, alias="fromChainId", description="Source chain id."
    )
    to_chain_id: Optional[int] = Field(
        default=None, alias="toChainId", description="Destination chain id."
    )
    from_amount: Optional[str] = Field(
        default=None, alias="fromAmount", description="Input amount in the source token's unit."
    )
    to_amount: Optional[str] = Field(
        default=None, alias="toAmount", description="Expected output amount."
    )
    to_amount_min: Optional[str] = Field(
        default=None, alias="toAmountMin", description="Guaranteed minimum output after slippage."
    )
    from_token: Optional[Token] = Field(
        default=None, alias="fromToken", description="Token being sold/sent."
    )
    to_token: Optional[Token] = Field(
        default=None, alias="toToken", description="Token to receive."
    )
    steps: list[Step] = Field(
        default_factory=list, description="Ordered steps composing the route."
    )


class TransferInfo(_Model):
    """On-chain details of one leg (source or destination) of a transfer."""

    tx_hash: Optional[str] = Field(
        default=None, alias="txHash", description="Transaction hash for this leg."
    )
    tx_link: Optional[str] = Field(
        default=None, alias="txLink", description="Block-explorer URL for the transaction."
    )
    chain_id: Optional[int] = Field(
        default=None, alias="chainId", description="Chain id this leg executed on."
    )
    amount: Optional[str] = Field(
        default=None, description="Amount transferred in the token's smallest unit."
    )
    token: Optional[Token] = Field(default=None, description="Token transferred on this leg.")


class Status(_Model):
    """Result of ``GET /status`` while tracking a cross-chain transfer.

    :attr:`status` is one of ``NOT_FOUND``, ``PENDING``, ``DONE`` or ``FAILED``
    (``INVALID`` may also appear). Use :attr:`is_done`, :attr:`is_failed` and
    :attr:`is_terminal` instead of comparing strings.
    """

    status: str = Field(description="Transfer state: NOT_FOUND, PENDING, DONE, FAILED or INVALID.")
    substatus: Optional[str] = Field(
        default=None, description="Finer-grained state within :attr:`status`."
    )
    substatus_message: Optional[str] = Field(
        default=None, alias="substatusMessage", description="Human-readable substatus explanation."
    )
    transaction_id: Optional[str] = Field(
        default=None, alias="transactionId", description="LI.FI transaction id."
    )
    tool: Optional[str] = Field(default=None, description="Tool/bridge handling the transfer.")
    sending: Optional[TransferInfo] = Field(default=None, description="Source-chain leg details.")
    receiving: Optional[TransferInfo] = Field(
        default=None, description="Destination-chain leg details."
    )

    @property
    def is_done(self) -> bool:
        """True when the transfer completed successfully (``status == "DONE"``)."""
        return self.status == "DONE"

    @property
    def is_failed(self) -> bool:
        """True when the transfer failed (``status`` is ``FAILED`` or ``INVALID``)."""
        return self.status in {"FAILED", "INVALID"}

    @property
    def is_terminal(self) -> bool:
        """True once the transfer reached a final state and won't change."""
        return self.is_done or self.is_failed


class Connection(_Model):
    """A possible route between two chains (entry in ``GET /connections``).

    Enumerates which source tokens can be bridged/swapped into which
    destination tokens for a given chain pair.
    """

    from_chain_id: int = Field(alias="fromChainId", description="Source chain id.")
    to_chain_id: int = Field(alias="toChainId", description="Destination chain id.")
    from_tokens: list[Token] = Field(
        default_factory=list, alias="fromTokens", description="Supported source tokens."
    )
    to_tokens: list[Token] = Field(
        default_factory=list, alias="toTokens", description="Reachable destination tokens."
    )
