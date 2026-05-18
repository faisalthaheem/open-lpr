## Context

The `retry_stuck_images` management command currently queries all stuck images (those in `processing` or `pending` state older than `PROCESSING_TIMEOUT_MINUTES`) and processes every one in a single synchronous loop. Each retry invokes the full three-phase LPR pipeline (detection, OCR, visualization), which makes blocking API calls to Qwen3-VL. If many images are stuck — e.g., after an extended outage — a single run could take hours, blocking subsequent cron invocations and creating an API load spike.

The command is intended to be called by cron every 1–2 minutes. Without a batch limit, overlapping runs or missed schedules become likely under high-stuck-image conditions.

## Goals / Non-Goals

**Goals:**
- Cap the number of stuck images processed per command invocation to a configurable batch size.
- Allow the batch size to be overridden via command-line option for ad-hoc use.
- Keep implementation minimal — just a queryset limit and a new setting.

**Non-Goals:**
- Parallel or concurrent processing of batches.
- Dynamic batch sizing based on API response times or load.
- Progress tracking across multiple invocations (the next cron run simply picks up where the last one left off).

## Decisions

**1. Django queryset slicing via `[:batch_size]`**

Apply the batch limit by slicing the queryset: `stuck_images[:batch_size]`. This is the standard Django pattern for limiting query results. It pushes the `LIMIT` clause to the database, so Django doesn't load all stuck images into memory.

Alternatives considered:
- *Python-side slicing after fetch*: Loads all stuck images into memory before discarding the excess. Wasteful with large stuck image counts.
- *Paginator utility*: Over-engineered for a simple integer limit on a single query.

**2. Configurable via python-decouple**

`RETRY_BATCH_SIZE` (default 5) follows the existing pattern in `settings.py` using `config()` from `python-decouple`. A `--batch-size` CLI option on the management command overrides the setting for ad-hoc use.

**3. Batch applies to total images picked up, not per-outcome**

The batch limit applies to the initial queryset — the command picks up at most `batch_size` stuck images, regardless of whether they end up retried or exhausted. This keeps the limit predictable and simple.

## Risks / Trade-offs

- **[Large backlog clears slowly at small batch sizes]** → Mitigation: Default of 5 with a 1-minute cron interval means ~300 images/hour. The `--batch-size` CLI option allows larger batches for manual catch-up. The setting can be increased if needed.
- **[Batch limit does not prevent long-running API calls within the batch]** → Mitigation: Each image is processed synchronously. If a single API call hangs, it blocks that slot in the batch. This is an existing limitation, not introduced by this change.
