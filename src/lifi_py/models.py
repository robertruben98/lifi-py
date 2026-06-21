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
    address: str
    chain_id: int = Field(alias="chainId")
    symbol: str
    decimals: int
    name: Optional[str] = None
    price_usd: Optional[str] = Field(default=None, alias="priceUSD")
    coin_key: Optional[str] = Field(default=None, alias="coinKey")
    logo_uri: Optional[str] = Field(default=None, alias="logoURI")


class Chain(_Model):
    id: int
    key: str
    name: str
    chain_type: Optional[str] = Field(default=None, alias="chainType")
    native_token: Token = Field(alias="nativeToken")
    logo_uri: Optional[str] = Field(default=None, alias="logoURI")
    mainnet: Optional[bool] = None


class Tool(_Model):
    key: str
    name: str
    logo_uri: Optional[str] = Field(default=None, alias="logoURI")


class ToolDetails(_Model):
    key: str
    name: str
    logo_uri: Optional[str] = Field(default=None, alias="logoURI")


def _hex_or_int(value: Optional[str]) -> Optional[int]:
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

    to: Optional[str] = None
    data: Optional[str] = None
    value: Optional[str] = None
    gas_limit: Optional[str] = Field(default=None, alias="gasLimit")
    gas_price: Optional[str] = Field(default=None, alias="gasPrice")
    chain_id: Optional[int] = Field(default=None, alias="chainId")

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
    type: Optional[str] = None
    amount: Optional[str] = None
    amount_usd: Optional[str] = Field(default=None, alias="amountUSD")
    token: Optional[Token] = None


class FeeCost(_Model):
    name: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[str] = None
    amount_usd: Optional[str] = Field(default=None, alias="amountUSD")
    percentage: Optional[str] = None
    token: Optional[Token] = None
    included: Optional[bool] = None


class Estimate(_Model):
    tool: Optional[str] = None
    from_amount: Optional[str] = Field(default=None, alias="fromAmount")
    to_amount: Optional[str] = Field(default=None, alias="toAmount")
    to_amount_min: Optional[str] = Field(default=None, alias="toAmountMin")
    approval_address: Optional[str] = Field(default=None, alias="approvalAddress")
    execution_duration: Optional[float] = Field(default=None, alias="executionDuration")
    gas_costs: list[GasCost] = Field(default_factory=list, alias="gasCosts")
    fee_costs: list[FeeCost] = Field(default_factory=list, alias="feeCosts")


class Action(_Model):
    from_chain_id: Optional[int] = Field(default=None, alias="fromChainId")
    to_chain_id: Optional[int] = Field(default=None, alias="toChainId")
    from_token: Optional[Token] = Field(default=None, alias="fromToken")
    to_token: Optional[Token] = Field(default=None, alias="toToken")
    from_amount: Optional[str] = Field(default=None, alias="fromAmount")
    from_address: Optional[str] = Field(default=None, alias="fromAddress")
    to_address: Optional[str] = Field(default=None, alias="toAddress")
    slippage: Optional[float] = None


class Step(_Model):
    id: str
    type: str
    tool: str
    tool_details: Optional[ToolDetails] = Field(default=None, alias="toolDetails")
    action: Optional[Action] = None
    estimate: Optional[Estimate] = None
    transaction_request: Optional[TransactionRequest] = Field(
        default=None, alias="transactionRequest"
    )


class Quote(_Model):
    """A ``/quote`` result: a single best route with a ready-to-sign tx."""

    type: str
    id: str
    tool: str
    tool_details: Optional[ToolDetails] = Field(default=None, alias="toolDetails")
    action: Action
    estimate: Estimate
    included_steps: list[Step] = Field(default_factory=list, alias="includedSteps")
    integrator: Optional[str] = None
    transaction_request: Optional[TransactionRequest] = Field(
        default=None, alias="transactionRequest"
    )
    transaction_id: Optional[str] = Field(default=None, alias="transactionId")


class Route(_Model):
    id: str
    from_chain_id: Optional[int] = Field(default=None, alias="fromChainId")
    to_chain_id: Optional[int] = Field(default=None, alias="toChainId")
    from_amount: Optional[str] = Field(default=None, alias="fromAmount")
    to_amount: Optional[str] = Field(default=None, alias="toAmount")
    to_amount_min: Optional[str] = Field(default=None, alias="toAmountMin")
    from_token: Optional[Token] = Field(default=None, alias="fromToken")
    to_token: Optional[Token] = Field(default=None, alias="toToken")
    steps: list[Step] = Field(default_factory=list)


class TransferInfo(_Model):
    tx_hash: Optional[str] = Field(default=None, alias="txHash")
    tx_link: Optional[str] = Field(default=None, alias="txLink")
    chain_id: Optional[int] = Field(default=None, alias="chainId")
    amount: Optional[str] = None
    token: Optional[Token] = None


class Status(_Model):
    """Result of ``/status`` while tracking a cross-chain transfer."""

    status: str
    substatus: Optional[str] = None
    substatus_message: Optional[str] = Field(default=None, alias="substatusMessage")
    transaction_id: Optional[str] = Field(default=None, alias="transactionId")
    tool: Optional[str] = None
    sending: Optional[TransferInfo] = None
    receiving: Optional[TransferInfo] = None

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
