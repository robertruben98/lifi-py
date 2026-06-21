"""Tests for pydantic response models parsing real LI.FI payloads."""

from __future__ import annotations

from lifi_py.models import (
    Chain,
    Connection,
    Quote,
    Route,
    Status,
    Step,
    Token,
    Tool,
    TransactionRequest,
)

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


def test_quote_parses_core_fields() -> None:
    quote = Quote.model_validate(QUOTE_RESPONSE)
    assert quote.id == "0x123abc"
    assert quote.tool == "across"
    assert quote.type == "lifi"
    assert quote.transaction_id == "0xtxid"


def test_quote_estimate_amounts() -> None:
    quote = Quote.model_validate(QUOTE_RESPONSE)
    assert quote.estimate.to_amount == "995000"
    assert quote.estimate.from_amount == "1000000"
    assert quote.estimate.execution_duration == 24.0
    assert len(quote.estimate.gas_costs) == 1
    assert len(quote.estimate.fee_costs) == 1


def test_quote_transaction_request_ready_to_sign() -> None:
    quote = Quote.model_validate(QUOTE_RESPONSE)
    tx = quote.transaction_request
    assert tx is not None
    assert tx.to == "0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE"
    assert tx.data == "0xdeadbeef"
    assert tx.chain_id == 42161
    assert tx.value == "0x0"


def test_quote_action_tokens() -> None:
    quote = Quote.model_validate(QUOTE_RESPONSE)
    assert quote.action.from_chain_id == 42161
    assert quote.action.to_chain_id == 8453
    assert quote.action.from_token is not None
    assert quote.action.from_token.symbol == "USDC"
    assert quote.action.from_amount == "1000000"


def test_quote_included_steps() -> None:
    quote = Quote.model_validate(QUOTE_RESPONSE)
    assert len(quote.included_steps) == 1
    assert quote.included_steps[0].tool == "across"


def test_quote_to_transaction_dict_for_web3() -> None:
    quote = Quote.model_validate(QUOTE_RESPONSE)
    tx = quote.transaction_request
    assert tx is not None
    d = tx.as_web3_tx()
    # hex strings should be converted to ints where web3 expects them
    assert d["chainId"] == 42161
    assert d["value"] == 0
    assert d["to"] == "0x1231DEB6f5749EF6cE6943a275A1D3E7486F4EaE"
    assert d["data"] == "0xdeadbeef"


def test_transaction_request_standalone() -> None:
    tx = TransactionRequest.model_validate(QUOTE_RESPONSE["transactionRequest"])
    assert tx.gas_limit == "0x7a120"
    assert tx.gas_price == "0x5f5e100"


def test_status_parses() -> None:
    status = Status.model_validate(STATUS_RESPONSE)
    assert status.status == "DONE"
    assert status.substatus == "COMPLETED"
    assert status.sending is not None
    assert status.sending.tx_hash == "0xsendhash"
    assert status.receiving is not None
    assert status.receiving.chain_id == 8453


def test_status_terminal_helpers() -> None:
    done = Status.model_validate(STATUS_RESPONSE)
    assert done.is_done is True
    assert done.is_failed is False
    assert done.is_terminal is True

    pending = Status.model_validate({**STATUS_RESPONSE, "status": "PENDING"})
    assert pending.is_done is False
    assert pending.is_terminal is False

    failed = Status.model_validate({**STATUS_RESPONSE, "status": "FAILED"})
    assert failed.is_failed is True
    assert failed.is_terminal is True


def test_chain_parses() -> None:
    chain = Chain.model_validate(CHAINS_RESPONSE["chains"][1])
    assert chain.id == 42161
    assert chain.key == "arb"
    assert chain.name == "Arbitrum"
    assert chain.native_token.symbol == "ETH"


def test_token_parses() -> None:
    token = Token.model_validate(TOKENS_RESPONSE["tokens"]["42161"][0])
    assert token.symbol == "USDC"
    assert token.decimals == 6
    assert token.chain_id == 42161


def test_tool_parses() -> None:
    bridge = Tool.model_validate(TOOLS_RESPONSE["bridges"][0])
    assert bridge.key == "across"
    assert bridge.name == "Across"


def test_connection_parses() -> None:
    conn = Connection.model_validate(CONNECTIONS_RESPONSE["connections"][0])
    assert conn.from_chain_id == 42161
    assert conn.to_chain_id == 8453
    assert conn.from_tokens[0].symbol == "USDC"


def test_route_parses() -> None:
    route = Route.model_validate(ROUTES_RESPONSE["routes"][0])
    assert route.id == "route-1"
    assert route.to_amount == "995000"
    assert len(route.steps) == 1


def test_step_with_transaction_request() -> None:
    step = Step.model_validate(STEP_TX_RESPONSE)
    assert step.id == "step-1"
    assert step.transaction_request is not None
    assert step.transaction_request.data == "0xstepdata"


def test_models_ignore_unknown_fields() -> None:
    # API adds fields over time; models must not break on extras.
    payload = {**QUOTE_RESPONSE, "someNewField": {"nested": True}}
    quote = Quote.model_validate(payload)
    assert quote.id == "0x123abc"
