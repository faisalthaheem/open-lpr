## Why

The `retry_stuck_images` management command processes all qualifying stuck images in a single run with no limit. If hundreds of images are stuck, a single invocation processes them all sequentially — each making synchronous API calls to Qwen3-VL — which can run for a very long time, block other cron runs, and create a burst of API load. A batch limit would allow controlled, predictable processing per invocation.

## What Changes

- Add a configurable `RETRY_BATCH_SIZE` setting (default 5) that caps the number of images processed per `retry_stuck_images` invocation.
- Add a `--batch-size` command-line option to override the setting for ad-hoc use.
- The command will process at most `batch_size` stuck images per run, leaving the rest for subsequent invocations.

## Capabilities

### New Capabilities

### Modified Capabilities
- `stuck-image-retry`: Adds a batch size limit to the retry execution requirement, capping the number of images processed per command invocation.

## Impact

- `lpr_project/settings.py` — new `RETRY_BATCH_SIZE` setting
- `lpr_app/management/commands/retry_stuck_images.py` — apply batch limit to queryset
- `.env.example`, `.env.llamacpp.example` — document new env var
