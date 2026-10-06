# Recognition scoring

CER and exact-match scoring for plate reads, and the annotation format that feeds it.

## The gap this closes

`compare_backends.py` could report whether a plate was *read* but never whether it
was read *correctly*. The corpus annotates plate boxes only — verified at the
source, where each `imgareas` entry has an `lbltxt` field whose only value across
all 2,701 regions is the class name `plate`. There is no transcription to score
against, so coverage stood in for accuracy and nobody could tell "reads
everything" from "reads everything wrongly".

## Scoring

Levenshtein distance over alphanumerics only, because the default charset profile
(`alphanumeric`) emits only alphanumerics — comparing raw strings would charge the
backend for every separator it is configured not to emit. `IDH-4497` and `IDH4497`
both normalise to `IDH4497`.

A detected-but-unread plate scores as a full-length deletion, the strictest
available choice: an empty read can never look better than a partial one. It is
also reported separately as `unread`, because a corpus where everything is silently
deleted and one where everything is confidently misread need opposite fixes.

Aggregated three ways: overall, per layout, and per confidence band. The bands are
the point — if accuracy rises with confidence, a threshold is a real lever; if not,
thresholding only discards reads at random. On the 20-plate pilot it rises
monotonically (CER 0.68 / 0.53 / 0.04), but 20 plates cannot set a value.

## Producing labels

```bash
# 1. write a crop per plate plus a labels.json to fill in
python -m lpr_app.ml.compare_backends --data <dataset-root> --limit 200 --dump-label-template labels/

# 2. transcribe from labels/crops/, overwriting every value in labels/labels.json

# 3. score both backends against it
python -m lpr_app.ml.compare_backends --data <dataset-root> --limit 200 --labels labels/labels.json
```

Format is a flat JSON object of `"<image file>#<plate index>"` to registration text.
A list of `{key, text}` is also accepted, for spreadsheet export. Blanks are
dropped: a blank means "not transcribed", and scoring it would charge a backend for
a plate nobody could read.

`--dump-label-template` pre-fills each value with the local backend's own read.
**Overwrite those. Do not confirm them.** Confirming would turn the resulting CER
into a measurement of how well the model agrees with itself, which is the one thing
this exercise must not be.

Crops are upscaled to 160px minimum. The corpus median plate is 61px tall and its
10th percentile is 36px, and transcription accuracy collapses below that.

## What it will not tell you

**Per-layout accuracy is not reportable.** `layout_of()` classifies aspect ratios
outside 1.5–2.6 and records the rest as `unknown` — 17 of 20 plates on the pilot.
Geometry cannot distinguish a two-row plate from a single-row plate carrying a
caption: `EG·209` (one line, caption beneath, ratio 1.91) and `L802 WGK` (two rows,
ratio 1.9) are indistinguishable. A single threshold gets one of them wrong and
attributes errors to the wrong cause. This needs a layout classifier trained on
captioned examples, which the corpus does not provide.

**Labels are not in the repository**, and `.gitignore` keeps them out. A partly
transcribed file would look like authoritative ground truth in history; an
unannotated one is worse, scored as though every blank were a real registration.