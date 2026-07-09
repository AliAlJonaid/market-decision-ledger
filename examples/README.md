# Synthetic examples

Everything in this directory is fictional and safe to publish.

- `policy.example.json` demonstrates a mechanical allow-list and portfolio limits.
- `decision-audit.example.md` demonstrates an evidence gate and HOLD-default record.

Run the local demo without touching committed fixtures:

```bash
python3 scripts/portfolio.py --state-dir /tmp/mdl-demo init --cash 1000
python3 scripts/portfolio.py --state-dir /tmp/mdl-demo buy ACME 250 \
  --price 50 --confidence 8 --reason "Synthetic example only"
python3 scripts/portfolio.py --state-dir /tmp/mdl-demo mark \
  --prices '{"ACME": 52}' --benchmark-close 100
```

