#!/usr/bin/env python3
"""Paper-only CLI for the deterministic Market Decision Ledger."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ledger import LedgerError, buy, create_state, deposit, load_policy, mark, sell, status


def _json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Paper-only, deterministic accounting CLI. No brokerage or network access."
    )
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path("runtime"),
        help="Local state directory (default: ./runtime; ignored by Git).",
    )
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("examples/policy.example.json"),
        help="Policy JSON used by buy operations.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="Create an empty local ledger state.")
    init.add_argument("--cash", required=True, help="Opening paper cash.")

    commands.add_parser("status", help="Print the current local state.")

    add_deposit = commands.add_parser("deposit", help="Add one dated paper deposit.")
    add_deposit.add_argument("amount")
    add_deposit.add_argument("--date", dest="on_date", help="YYYY-MM-DD; defaults to today.")

    purchase = commands.add_parser("buy", help="Record a policy-gated paper purchase.")
    purchase.add_argument("ticker")
    purchase.add_argument("usd")
    purchase.add_argument("--price", required=True)
    purchase.add_argument("--confidence", type=int, required=True)
    purchase.add_argument("--reason", required=True)

    sale = commands.add_parser("sell", help="Record a paper sale.")
    sale.add_argument("ticker")
    sale.add_argument("quantity", help='Positive number of shares or "all".')
    sale.add_argument("--price", required=True)
    sale.add_argument("--reason", required=True)

    valuation = commands.add_parser(
        "mark",
        help="Record an aggregate valuation from a complete set of position prices.",
    )
    valuation.add_argument("--prices", required=True, help='JSON object, e.g. {"ACME": 42.00}.')
    valuation.add_argument("--benchmark-close", help="Optional benchmark close.")

    args = parser.parse_args()

    try:
        if args.command == "init":
            result = create_state(args.state_dir, args.cash)
        elif args.command == "status":
            result = status(args.state_dir)
        elif args.command == "deposit":
            result = deposit(args.state_dir, args.amount, args.on_date)
        elif args.command == "buy":
            result = buy(
                args.state_dir,
                load_policy(args.policy),
                args.ticker,
                args.usd,
                args.price,
                args.confidence,
                args.reason,
            )
        elif args.command == "sell":
            result = sell(args.state_dir, args.ticker, args.quantity, args.price, args.reason)
        else:
            try:
                prices = json.loads(args.prices)
            except json.JSONDecodeError as exc:
                raise LedgerError("--prices must be a JSON object") from exc
            if not isinstance(prices, dict):
                raise LedgerError("--prices must be a JSON object")
            result = mark(args.state_dir, prices, args.benchmark_close)
    except LedgerError as exc:
        parser.error(str(exc))
        return 2

    _json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
