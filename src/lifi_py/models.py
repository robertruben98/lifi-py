"""Pydantic v2 models for LI.FI API responses.

Field names mirror Python conventions (snake_case) while accepting the API's
camelCase payloads via ``populate_by_name`` + ``alias``. All models tolerate
unknown fields so they keep working as the API evolves.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    """Base with camelCase aliasing and forward-compatible extra handling."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="ignore",
    )


class Token(_Model):
    address: str
    chain_id: int = Field(alias="chainId")
    symbol: str
    decimals: int
    name: str | None = None
    price_usd: str | None = Field(default=None, alias="priceUSD")
    coin_key: str | None = Field(default=None, alias="coinKey")
    logo_uri: str | None = Field(default=None, alias="logoURI")


class Chain(_Model):
    id: int
    key: str
    name: str
    chain_type: str | None = Field(default=None, alias="chainType")
    native_token: Token = Field(alias="nativeToken")
    logo_uri: str | None = Field(default=None, alias="logoURI")
    mainnet: bool | None = None


class Tool(_Model):
    key: str
    name: str
    logo_uri: str | None = Field(default=None, alias="logoURI")


class ToolDetails(_Model):
    key: str
    name: str
    logo_uri: str | None = Field(default=None, alias="logoURI")


def _hex_or_int(value: str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = value.strip()
    if text.lower().startswith("0x"):
        return int(text, 16)
    return int(text)


class TransactionRequest(_Model):
    """A ready-to-sign EVM transaction returned by ``/quote`` or step assembly."""

    to: str | None = None
    data: str | None = None
    value: str | None = None
    gas_limit: str | None = Field(default=None, alias="gasLimit")
    gas_price: str | None = Field(default=None, alias="gasPrice")
    chain_id: int | None = Field(default=None, alias="chainId")

    def as_web3_tx(self) -> dict[str, Any]:
        """Return a dict shaped for ``web3.eth.send_transaction`` / signing.

        Hex-encoded numeric fields (``value``, ``gasLimit``, ``gasPrice``) are
        decoded to ``int``; ``to``/``data`` are passed through unchanged.
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
    type: str | None = None
    amount: str | None = None
    amount_usd: str | None = Field(default=None, alias="amountUSD")
    token: Token | None = None


class FeeCost(_Model):
    name: str | None = None
    description: str | None = None
    amount: str | None = None
    amount_usd: str | None = Field(default=None, alias="amountUSD")
    percentage: str | None = None
    token: Token | None = None
    included: bool | None = None


class Estimate(_Model):
    tool: str | None = None
    from_amount: str | None = Field(default=None, alias="fromAmount")
    to_amount: str | None = Field(default=None, alias="toAmount")
    to_amount_min: str | None = Field(default=None, alias="toAmountMin")
    approval_address: str | None = Field(default=None, alias="approvalAddress")
    execution_duration: float | None = Field(default=None, alias="executionDuration")
    gas_costs: list[GasCost] = Field(default_factory=list, alias="gasCosts")
    fee_costs: list[FeeCost] = Field(default_factory=list, alias="feeCosts")


class Action(_Model):
    from_chain_id: int | None = Field(default=None, alias="fromChainId")
    to_chain_id: int | None = Field(default=None, alias="toChainId")
    from_token: Token | None = Field(default=None, alias="fromToken")
    to_token: Token | None = Field(default=None, alias="toToken")
    from_amount: str | None = Field(default=None, alias="fromAmount")
    from_address: str | None = Field(default=None, alias="fromAddress")
    to_address: str | None = Field(default=None, alias="toAddress")
    slippage: float | None = None


class Step(_Model):
    id: str
    type: str
    tool: str
    tool_details: ToolDetails | None = Field(default=None, alias="toolDetails")
    action: Action | None = None
    estimate: Estimate | None = None
    transaction_request: TransactionRequest | None = Field(
        default=None, alias="transactionRequest"
    )


class Quote(_Model):
    """A ``/quote`` result: a single best route with a ready-to-sign tx."""

    type: str
    id: str
    tool: str
    tool_details: ToolDetails | None = Field(default=None, alias="toolDetails")
    action: Action
    estimate: Estimate
    included_steps: list[Step] = Field(default_factory=list, alias="includedSteps")
    integrator: str | None = None
    transaction_request: TransactionRequest | None = Field(
        default=None, alias="transactionRequest"
    )
    transaction_id: str | None = Field(default=None, alias="transactionId")


class Route(_Model):
    id: str
    from_chain_id: int | None = Field(default=None, alias="fromChainId")
    to_chain_id: int | None = Field(default=None, alias="toChainId")
    from_amount: str | None = Field(default=None, alias="fromAmount")
    to_amount: str | None = Field(default=None, alias="toAmount")
    to_amount_min: str | None = Field(default=None, alias="toAmountMin")
    from_token: Token | None = Field(default=None, alias="fromToken")
    to_token: Token | None = Field(default=None, alias="toToken")
    steps: list[Step] = Field(default_factory=list)


class TransferInfo(_Model):
    tx_hash: str | None = Field(default=None, alias="txHash")
    tx_link: str | None = Field(default=None, alias="txLink")
    chain_id: int | None = Field(default=None, alias="chainId")
    amount: str | None = None
    token: Token | None = None


class Status(_Model):
    """Result of ``/status`` while tracking a cross-chain transfer."""

    status: str
    substatus: str | None = None
    substatus_message: str | None = Field(default=None, alias="substatusMessage")
    transaction_id: str | None = Field(default=None, alias="transactionId")
    tool: str | None = None
    sending: TransferInfo | None = None
    receiving: TransferInfo | None = None

    @property
    def is_done(self) -> bool:
        return self.status == "DONE"

    @property
    def is_failed(self) -> bool:
        return self.status in {"FAILED", "INVALID"}

    @property
    def is_terminal(self) -> bool:
        """True once the transfer reached a final state and won't change."""
        return self.is_done or self.is_failed


class Connection(_Model):
    from_chain_id: int = Field(alias="fromChainId")
    to_chain_id: int = Field(alias="toChainId")
    from_tokens: list[Token] = Field(default_factory=list, alias="fromTokens")
    to_tokens: list[Token] = Field(default_factory=list, alias="toTokens")
