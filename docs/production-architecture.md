# Production Architecture and Demo Boundary

## Production lineage

This demo is a clean-room reduction of a production strategic-buyer operating system. The production system coordinates bounded agents and deterministic mechanics across this lifecycle:

```text
intake
  -> scoring-matrix design
  -> multi-channel sourcing
  -> scoring
  -> human exclusion gate
  -> client-safe deliverable
  -> client review
  -> contact enrichment
  -> personalized copy
  -> campaign launch
  -> reply and closeout processing
```

Agents own evidence collection and bounded judgment. Code owns exact joins, deduplication, weighted arithmetic, contract validation, artifact generation, integration calls, cost attribution, and closeout state. Human operators retain authority at asymmetric-risk boundaries.

## Why artifacts are the handoff

Each stage writes a versioned JSON artifact rather than relying on conversational memory. That makes the workflow:

- resumable after a context reset;
- inspectable before the next stage runs;
- independently testable;
- cheaper to operate because later agents receive only the slice they need;
- safer because malformed outputs fail at the boundary.

The demo preserves that design with `intake.json`, `sourcing_buyers.json`, `scored_buyers.json`, `gate_review.json`, and a final manifest.

## Deterministic and agent-owned work

| Concern | Owner |
|---|---|
| Candidate discovery and evidence interpretation | Bounded research agents |
| Strategic-fit and urgency sub-scores | Bounded judgment agent |
| Deduplication and provenance merge | Deterministic code |
| Composite arithmetic and tier assignment | Deterministic code |
| Inclusion decision | Human operator |
| Deliverable field filtering and export | Deterministic code |

This separation prevents language models from doing arithmetic, silently changing the stage order, approving their own work, or deciding which internal fields may cross the client boundary.

## Sanitized demo boundary

The public repository deliberately omits:

- production campaign artifacts and buyer records;
- client identities, contact information, financials, and deal terms;
- live CRM, enrichment, sequencing, and messaging identifiers;
- credentials and environment files;
- historical operating logs and internal performance data.

Agent outputs are replayed from synthetic fixtures so reviewers can reproduce the pipeline without paid services or credentials. The same contracts can sit behind a live agent runtime without changing deterministic downstream mechanics.
