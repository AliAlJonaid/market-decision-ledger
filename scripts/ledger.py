"""Deterministic, paper-only accounting primitives for Market Decision Ledger.

This module intentionally has no brokerage, market-data, or network integration.
Prices and decisions are supplied by the caller and recorded locally.
"""
from __future__ import annotations

import csv
import json
import os
import re
import tempfile
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any


class LedgerError(ValueError):
    """Raised when a transaction violates a deterministic ledger rule."""


MONEY_QUANTUM = Decimal("0.01")
PRICE_QUANTUM = Decimal("0.0001")
SHARE_QUANTUM = Decimal("0.000001")
TICKER_RE = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")


def _decimal(value: Any, label: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise LedgerError(f"{label} must be numeric") from exc


def _positive(value: Any, label: str) -> Decimal:
    parsed = _decimal(value, label)
    if parsed <= 0:
        raise LedgerError(f"{label} must be greater than zero")
    return parsed


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _price(value: Decimal) -> Decimal:
    return value.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_UP)


def _shares(value: Decimal) -> Decimal:
    return value.quantize(SHARE_QUANTUM, rounding=ROUND_HALF_UP)


def _number(value: Decimal) -> str:
    return format(value, "f")


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _valid_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError) as exc:
        raise LedgerError("date must use YYYY-MM-DD") from exc


def _state_paths(state_dir: Path) -> dict[str, Path]:
    return {
        "state": state_dir / "state.json",
        "events": state_dir / "events.csv",
        "history": state_dir / "history.csv",
    }


def _atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=".state-", delete=False
    ) as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary_path = Path(handle.name)
    os.replace(temporary_path, path)


def _append_csv(path: Path, fieldnames: list[str], row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def _load_state(state_dir: Path) -> dict[str, Any]:
    path = _state_paths(state_dir)["state"]
    if not path.exists():
        raise LedgerError("state does not exist; run init first")
    try:
        with path.open(encoding="utf-8") as handle:
            state = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerError("state file cannot be read") from exc

    required = {"schema_version", "cash", "total_deposited", "positions", "deposit_dates"}
    if not isinstance(state, dict) or not required.issubset(state):
        raise LedgerError("state file is missing required fields")
    if not isinstance(state["positions"], dict) or not isinstance(state["deposit_dates"], list):
        raise LedgerError("state file has an invalid structure")
    return state


def _save_state(state_dir: Path, state: dict[str, Any]) -> None:
    state["updated_at"] = _timestamp()
    _atomic_json_write(_state_paths(state_dir)["state"], state)


def _clean_ticker(ticker: str) -> str:
    normalized = ticker.strip().upper()
    if not TICKER_RE.fullmatch(normalized):
        raise LedgerError("ticker must be a short uppercase market symbol")
    return normalized


def _require_reason(reason: str) -> str:
    normalized = reason.strip()
    if not normalized:
        raise LedgerError("reason is required")
    return normalized


def create_state(state_dir: Path, opening_cash: Any) -> dict[str, Any]:
    opening = _money(_positive(opening_cash, "opening cash"))
    paths = _state_paths(state_dir)
    if paths["state"].exists():
        raise LedgerError("state already exists; choose an empty state directory")
    state = {
        "schema_version": 1,
        "cash": _number(opening),
        "total_deposited": _number(opening),
        "positions": {},
        "deposit_dates": [],
        "created_at": _timestamp(),
        "updated_at": _timestamp(),
    }
    _atomic_json_write(paths["state"], state)
    return state


def load_policy(path: Path) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise LedgerError("policy file cannot be read") from exc

    try:
        allowed = {_clean_ticker(item) for item in raw["allowed_tickers"]}
        minimum_confidence = int(raw["minimum_confidence"])
        max_positions = int(raw["max_positions"])
        max_position_usd = _money(_positive(raw["max_position_usd"], "max_position_usd"))
    except (KeyError, TypeError, ValueError) as exc:
        raise LedgerError("policy file is invalid") from exc

    if not allowed:
        raise LedgerError("policy must define at least one allowed ticker")
    if not 1 <= minimum_confidence <= 10:
        raise LedgerError("minimum_confidence must be from 1 to 10")
    if max_positions < 1:
        raise LedgerError("max_positions must be at least 1")

    return {
        "allowed_tickers": allowed,
        "minimum_confidence": minimum_confidence,
        "max_positions": max_positions,
        "max_position_usd": max_position_usd,
    }


def deposit(state_dir: Path, amount: Any, on_date: str | None = None) -> dict[str, Any]:
    state = _load_state(state_dir)
    amount_value = _money(_positive(amount, "deposit"))
    deposit_date = _valid_date(on_date or _today())

    if deposit_date in state["deposit_dates"]:
        raise LedgerError(f"a deposit already exists for {deposit_date}")

    cash = _money(_decimal(state["cash"], "cash") + amount_value)
    total_deposited = _money(_decimal(state["total_deposited"], "total_deposited") + amount_value)
    state["cash"] = _number(cash)
    state["total_deposited"] = _number(total_deposited)
    state["deposit_dates"].append(deposit_date)
    _save_state(state_dir, state)

    _append_csv(
        _state_paths(state_dir)["events"],
        ["timestamp", "action", "ticker", "shares", "price", "value_usd", "cash_after", "reason"],
        {
            "timestamp": _timestamp(),
            "action": "DEPOSIT",
            "ticker": "CASH",
            "shares": "",
            "price": "",
            "value_usd": _number(amount_value),
            "cash_after": _number(cash),
            "reason": f"paper deposit for {deposit_date}",
        },
    )
    return {"action": "DEPOSIT", "date": deposit_date, "cash": _number(cash)}


def buy(
    state_dir: Path,
    policy: dict[str, Any],
    ticker: str,
    usd: Any,
    price: Any,
    confidence: int,
    reason: str,
) -> dict[str, Any]:
    state = _load_state(state_dir)
    symbol = _clean_ticker(ticker)
    value = _money(_positive(usd, "purchase amount"))
    unit_price = _price(_positive(price, "price"))
    rationale = _require_reason(reason)

    if symbol not in policy["allowed_tickers"]:
        raise LedgerError(f"{symbol} is not in the policy allow-list")
    if not 1 <= confidence <= 10:
        raise LedgerError("confidence must be from 1 to 10")
    if confidence < policy["minimum_confidence"]:
        raise LedgerError("confidence is below the policy minimum")

    cash = _decimal(state["cash"], "cash")
    if value > cash:
        raise LedgerError("insufficient paper cash")

    positions = state["positions"]
    existing = positions.get(symbol)
    if existing is None and len(positions) >= policy["max_positions"]:
        raise LedgerError("policy maximum position count reached")

    existing_shares = _decimal(existing["shares"], "shares") if existing else Decimal("0")
    existing_cost = existing_shares * _decimal(existing["avg_cost"], "avg_cost") if existing else Decimal("0")
    if _money(existing_cost + value) > policy["max_position_usd"]:
        raise LedgerError("purchase would exceed the policy position cap")

    purchased_shares = _shares(value / unit_price)
    if purchased_shares <= 0:
        raise LedgerError("purchase is too small for the selected price")
    total_shares = _shares(existing_shares + purchased_shares)
    average_cost = _price((existing_cost + value) / total_shares)

    positions[symbol] = {
        "shares": _number(total_shares),
        "avg_cost": _number(average_cost),
    }
    cash_after = _money(cash - value)
    state["cash"] = _number(cash_after)
    _save_state(state_dir, state)

    _append_csv(
        _state_paths(state_dir)["events"],
        ["timestamp", "action", "ticker", "shares", "price", "value_usd", "cash_after", "reason"],
        {
            "timestamp": _timestamp(),
            "action": "BUY",
            "ticker": symbol,
            "shares": _number(purchased_shares),
            "price": _number(unit_price),
            "value_usd": _number(value),
            "cash_after": _number(cash_after),
            "reason": rationale,
        },
    )
    return {
        "action": "BUY",
        "ticker": symbol,
        "shares": _number(purchased_shares),
        "cash": _number(cash_after),
    }


def sell(
    state_dir: Path,
    ticker: str,
    quantity: str,
    price: Any,
    reason: str,
) -> dict[str, Any]:
    state = _load_state(state_dir)
    symbol = _clean_ticker(ticker)
    rationale = _require_reason(reason)
    unit_price = _price(_positive(price, "price"))
    positions = state["positions"]

    if symbol not in positions:
        raise LedgerError(f"no open position in {symbol}")

    held_shares = _decimal(positions[symbol]["shares"], "shares")
    sold_shares = held_shares if quantity.lower() == "all" else _shares(_positive(quantity, "quantity"))
    if sold_shares > held_shares:
        raise LedgerError("cannot sell more shares than are held")

    proceeds = _money(sold_shares * unit_price)
    remaining = _shares(held_shares - sold_shares)
    if remaining == 0:
        del positions[symbol]
    else:
        positions[symbol]["shares"] = _number(remaining)

    cash_after = _money(_decimal(state["cash"], "cash") + proceeds)
    state["cash"] = _number(cash_after)
    _save_state(state_dir, state)

    _append_csv(
        _state_paths(state_dir)["events"],
        ["timestamp", "action", "ticker", "shares", "price", "value_usd", "cash_after", "reason"],
        {
            "timestamp": _timestamp(),
            "action": "SELL",
            "ticker": symbol,
            "shares": _number(sold_shares),
            "price": _number(unit_price),
            "value_usd": _number(proceeds),
            "cash_after": _number(cash_after),
            "reason": rationale,
        },
    )
    return {
        "action": "SELL",
        "ticker": symbol,
        "shares": _number(sold_shares),
        "cash": _number(cash_after),
    }


def mark(state_dir: Path, prices: dict[str, Any], benchmark_close: Any | None = None) -> dict[str, Any]:
    state = _load_state(state_dir)
    normalized_prices = {_clean_ticker(symbol): _price(_positive(value, "price")) for symbol, value in prices.items()}

    positions_value = Decimal("0")
    missing = []
    for symbol, position in state["positions"].items():
        if symbol not in normalized_prices:
            missing.append(symbol)
            continue
        positions_value += _decimal(position["shares"], "shares") * normalized_prices[symbol]

    if missing:
        raise LedgerError("missing prices for: " + ", ".join(sorted(missing)))

    cash = _decimal(state["cash"], "cash")
    total_value = _money(cash + positions_value)
    benchmark = "" if benchmark_close is None else _number(_price(_positive(benchmark_close, "benchmark_close")))

    _append_csv(
        _state_paths(state_dir)["history"],
        ["timestamp", "cash", "positions_value", "total_value", "total_deposited", "benchmark_close"],
        {
            "timestamp": _timestamp(),
            "cash": _number(cash),
            "positions_value": _number(_money(positions_value)),
            "total_value": _number(total_value),
            "total_deposited": state["total_deposited"],
            "benchmark_close": benchmark,
        },
    )
    return {
        "action": "MARK",
        "cash": _number(cash),
        "positions_value": _number(_money(positions_value)),
        "total_value": _number(total_value),
        "total_deposited": state["total_deposited"],
    }


def status(state_dir: Path) -> dict[str, Any]:
    return _load_state(state_dir)

