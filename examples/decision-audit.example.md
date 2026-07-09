# Synthetic decision-audit example

> This example is fictional. Symbols, prices, sources, and outcomes are illustrative only.

## Proposed action

**Decision:** HOLD  
**Candidate:** ACME  
**Confidence:** 6 / 10

## Evidence gate

| Requirement | Result |
|---|---|
| Source dated for the decision session | Pass |
| Price snapshot complete | Pass |
| Symbol on the example allow-list | Pass |
| Confidence meets minimum policy threshold | **Fail** |

## Decision rationale

The available evidence was directionally positive, but it did not meet the configured confidence floor. The system records HOLD rather than manufacturing a trade.

## What would change the decision?

- A second independent source supports the same thesis.
- The next complete price snapshot confirms the expected trend.
- Confidence reaches the configured minimum without violating position limits.

## Audit note

This is an example of decision documentation, not investment advice, a recommendation, or a record of real market activity.

