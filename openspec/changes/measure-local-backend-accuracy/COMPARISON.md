# Backend comparison, recorded

The numbers behind the `local` default flip. Measured on the same images,
through the same code paths production uses, with `lpr_app/ml/compare_backends.py`.

Reproduce with:

```bash
python -m lpr_app.ml.compare_backends --data <dataset-root> --limit 40
```

## What was measured

40 images from the frame-grouped validation split of the annotated plate corpus
(480 images, 487 plate annotations, zero perceptual-hash overlap with training and
a minimum frame distance of 51). The split matters: the corpus's published split
leaks 10 images directly and a random split leaks far more through adjacent
near-identical frames, so metrics computed on it would be inflated.

## Results

| | Local ONNX | LLM |
|---|---|---|
| Detection recall @ IoU 0.3 | **1.000** | 0.375 |
| Detection precision | **1.000** | 0.375 |
| False positives | 0 | 25 |
| Plates producing text | 0.95 | 0.375 |
| Read coverage, single-line (14) | **0.93** | 0.57 |
| Read coverage, stacked (26) | **0.96** | 0.27 |
| Median read confidence | 0.775 | 0.98 |
| Mean latency | **59.7 ms** | 3610.9 ms |
| Median latency | **58.1 ms** | 3385.2 ms |
| p95 latency | **77.6 ms** | 6678.1 ms |
| Max latency | **86.7 ms** | 6815.4 ms |
| Within the 0.5s budget | yes (8.4x margin) | no (7.2x over) |

The LLM backend is the one currently in production, measured against a
gemma-4-12b-it Q4_K_XL GGUF served over llama.cpp — the model
`QWEN_MODEL` is actually configured to on this host, not Qwen3-VL. A different
model would produce different numbers, and the detection gap in particular is
model-specific.

### The detection gap was verified, not assumed

The LLM's low recall is bad enough that it warranted checking against a harness
bug rather than reporting it directly. Rendering the LLM's box against the ground
truth for `1050.jpg` shows it placing the box **89px below the plate**, capturing
the bumper and the caption strip rather than the plate. This is the model's own
error, not a coordinate-scaling or matching defect in the comparison script:

- the LLM's x-range is correct (516–714 against a truth of 516–724)
- only the y placement is wrong, which no scaling mistake produces, since a
  scale error would distort both axes
- the mismatch is consistent across images, giving 25 false positives against 15
  true matches

The 4B-class Qwen3-VL that the project was originally developed against is a
different model, and a deployment running it will not see these numbers. That
caveat is the reason this proposal does not treat the LLM column as settled.

### What these numbers cannot tell us

**Text accuracy is unmeasured.** The corpus annotates plate *boxes*. It carries no
transcription labels, so there is no ground truth to score a read against. The
text rows above are read *coverage* — did the plate produce any text — and the
model's own confidence. Neither is correctness.

This matters most for the LLM's higher median confidence of 0.98 against the local
backend's 0.775. Two readings fit that pattern:

1. The LLM reads correctly what it reads, and misses the rest.
2. The LLM is confidently wrong, and the local backend's lower confidence is
   honest.

The local backend demonstrably misreads — `QG.260` becomes `0G260`, and
`IDH-4497` becomes `06260` — so its lower confidence is at least calibrated to
something. Whether the LLM's 0.98 is calibrated to correctness is exactly what
labels would answer and what this run cannot.

**The stacked-plate figures are not a layout result.** 26 of the 40 plates are
classified stacked by aspect ratio alone, which cannot distinguish a genuinely
two-line plate from a single-line plate carrying a caption. The local backend's
0.96 stacked coverage is therefore coverage on a *mixture*, not evidence it handles
stacked plates. See `DETECTOR.md` for why this is unresolved and why row splitting
defaults to off.

## Decision

**The default is now `local`.** The maintainer's call, made on the latency and
detection numbers above rather than on a text-accuracy result, since none exists
to weigh.

That is a defensible trade — 60ms against 3600ms is a 60x cost difference for an
unmeasured text read rate, and the local backend's detection is strictly better —
but it should be recorded as a trade rather than as a validated improvement. The
specific risk it carries is that **coverage was substituted for accuracy**: the
local backend reads more plates and the comparison cannot show whether those
reads are correct. It demonstrably misreads some (`QG.260` -> `0G260`,
`IDH-4497` -> `06260`), so if its errors cluster rather than scatter, a consumer
receives confidently wrong text where the LLM backend would have returned nothing.

Nothing in the current repository can distinguish those cases. That is the gap the
`measure-local-backend-accuracy` change exists to close:

1. **Transcription labels for a few hundred validation plates.** The images are
   already in place; only the strings are missing.
2. **Re-run with CER and exact-match scoring per layout**, so the local backend's
   higher coverage is either confirmed as higher accuracy or shown to be
   confident noise.

Until (1) and (2) land, this comparison supports the decision that was made and
does not verify it. Those are different things, and the difference is what would
surface a silent accuracy regression as an alertable metric drop rather than as a
slow accumulation of wrong numbers nobody notices.
