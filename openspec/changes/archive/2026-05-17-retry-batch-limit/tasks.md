## 1. Settings

- [x] 1.1 Add `RETRY_BATCH_SIZE` to `settings.py` using `python-decouple` `config()` with default 5.
- [x] 1.2 Add `RETRY_BATCH_SIZE` to `.env.example` and `.env.llamacpp.example` with comments.

## 2. Management Command

- [x] 2.1 Add `--batch-size` command-line option to `retry_stuck_images` management command that overrides `settings.RETRY_BATCH_SIZE` for ad-hoc use.
- [x] 2.2 Apply batch size limit to the stuck images queryset using Django slicing (`[:batch_size]`), ensuring the database handles the `LIMIT` clause.

## 3. Verification

- [x] 3.1 Run `python manage.py retry_stuck_images --help` and verify `--batch-size` option appears.
