# Security and privacy

## Public repository rule

Do not commit credentials, private research reports, portfolio state, broker information, personal identifiers, or generated archives.

The repository includes `scripts/check-public-safety.sh`, which scans Git-includable files for common credential formats, email addresses, home-directory paths, sensitive filenames, and the retired private project name.

```bash
bash scripts/check-public-safety.sh
```

This is a guardrail, not a substitute for reviewing a change before publishing it.

## Local-only state

Use a local runtime directory for any experiment:

```bash
python3 scripts/portfolio.py --state-dir runtime init --cash 1000
```

The `runtime/` directory is ignored by Git. All examples committed to this repository are synthetic.

## Reporting a vulnerability

Do not include tokens, personal information, screenshots, or private logs in a public issue. Remove or rotate sensitive material first, then describe the problem using a sanitized reproduction.

