from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ledger import LedgerError, buy, create_state, deposit, load_policy, mark, sell, status


class LedgerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temporary.name) / "state"
        self.policy_path = Path(self.temporary.name) / "policy.json"
        self.policy_path.write_text(
            json.dumps(
                {
                    "allowed_tickers": ["ACME", "ORBIT", "NOVA"],
                    "minimum_confidence": 7,
                    "max_positions": 2,
                    "max_position_usd": 400,
                }
            ),
            encoding="utf-8",
        )
        create_state(self.state_dir, "1000")
        self.policy = load_policy(self.policy_path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_deposit_cannot_repeat_on_the_same_date(self) -> None:
        deposit(self.state_dir, "25", "2026-01-01")
        with self.assertRaisesRegex(LedgerError, "already exists"):
            deposit(self.state_dir, "25", "2026-01-01")

    def test_buy_enforces_allow_list_and_confidence(self) -> None:
        with self.assertRaisesRegex(LedgerError, "allow-list"):
            buy(self.state_dir, self.policy, "UNLISTED", "100", "10", 8, "synthetic test")

        with self.assertRaisesRegex(LedgerError, "below the policy minimum"):
            buy(self.state_dir, self.policy, "ACME", "100", "10", 6, "synthetic test")

    def test_buy_enforces_position_cap_and_maximum_count(self) -> None:
        with self.assertRaisesRegex(LedgerError, "position cap"):
            buy(self.state_dir, self.policy, "ACME", "401", "10", 8, "synthetic test")

        buy(self.state_dir, self.policy, "ACME", "300", "10", 8, "synthetic test")
        buy(self.state_dir, self.policy, "ORBIT", "300", "20", 8, "synthetic test")

        with self.assertRaisesRegex(LedgerError, "maximum position count"):
            buy(self.state_dir, self.policy, "NOVA", "101", "10", 8, "synthetic test")

    def test_sell_rejects_invalid_quantity(self) -> None:
        buy(self.state_dir, self.policy, "ACME", "100", "10", 8, "synthetic test")
        with self.assertRaisesRegex(LedgerError, "greater than zero"):
            sell(self.state_dir, "ACME", "0", "11", "synthetic test")
        with self.assertRaisesRegex(LedgerError, "cannot sell more"):
            sell(self.state_dir, "ACME", "11", "11", "synthetic test")

    def test_mark_requires_a_complete_price_snapshot(self) -> None:
        buy(self.state_dir, self.policy, "ACME", "100", "10", 8, "synthetic test")
        with self.assertRaisesRegex(LedgerError, "missing prices"):
            mark(self.state_dir, {})

    def test_end_to_end_paper_ledger(self) -> None:
        buy_result = buy(self.state_dir, self.policy, "ACME", "200", "20", 8, "synthetic test")
        self.assertEqual(buy_result["ticker"], "ACME")

        mark_result = mark(self.state_dir, {"ACME": "22"}, "100")
        self.assertEqual(mark_result["total_value"], "1020.00")

        sell_result = sell(self.state_dir, "ACME", "all", "22", "synthetic exit")
        self.assertEqual(sell_result["cash"], "1020.00")
        self.assertEqual(status(self.state_dir)["positions"], {})


if __name__ == "__main__":
    unittest.main(verbosity=2)
