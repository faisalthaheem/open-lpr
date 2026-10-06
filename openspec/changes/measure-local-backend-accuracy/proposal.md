## Why

`add-onnx-plate-pipeline` shipped the local ONNX backend as opt-in with `llm` as the default, on the principle that the default should not flip "until a recorded accuracy comparison justifies it". The comparison has been run and the default has since been flipped to `local`. The measured numbers are in `COMPARISON.md` alongside this proposal.

What that comparison established:

| | Local ONNX | LLM (gemma-4-12b, llama.cpp) |
|---|---|---|
| Detection recall @ IoU 0.3 | **1.000** | 0.375 |
| Detection precision | **1.000** | 0.375 |
| Plates with text read | 0.95 | 0.375 |
| Mean latency per image | **60 ms** | 3611 ms |
| p95 latency per image | **78 ms** | 6678 ms |
| Median read confidence | 0.775 | 0.98 |

The local backend is now the default. **This change is about the one thing that comparison could not do.**

Text *accuracy* is unmeasured. The corpus annotates plate *boxes* and carries no transcription labels, so there is no ground truth to score a read against. What the table reports for text is read *coverage* — whether a plate produced any text — plus the model's own confidence. Neither is correctness.

That gap is now the project's largest open risk rather than a reason to defer a decision, because the default decision has been made. Concretely: the local backend reads 0.95 of detections against the LLM's 0.375, and misreads some plates it does find (`QG.260` becomes `0G260`, `IDH-4497` becomes `06260`). Nothing currently in the repository can tell those two facts apart from "the local backend reads everything correctly."

The LLM's median confidence of 0.98 against the local backend's 0.775 sharpens the question rather than answering it. Two readings fit that pattern, and they imply opposite decisions:

1. The LLM reads correctly what it reads, and misses the rest. The local backend's lower confidence is honest and its extra reads are correct — in which case the flip is validated and nothing needs changing.
2. The LLM is confidently wrong, and the local backend trades silent misses for wrong answers on every plate. In which case the flip traded a visible failure (no plate) for an invisible one (a wrong plate), which is worse: a downstream system gets a confident, wrong answer it has no way to distrust.

**The blocker is labels, not engineering.** Transcription for a few hundred validation plates is the whole of it; the images are already in place. The scoring harness already exists in `lpr_app/ml/compare_backends.py` and reports the axes that do not depend on labels, so extending it is a small job once the strings exist.

## What Changes

- **Add transcription labels for the validation split.** This is the substance. A `labels.json` mapping plate image (or plate box) to its registration text, covering a few hundred plates spanning both layouts.
- **Extend `compare_backends.py` to score recognition.** Character error rate and exact-match rate, reported per layout, alongside the coverage and confidence it already reports. Levenshtein over alphanumerics only, since the default charset profile emits only alphanumerics and comparing raw strings would charge the local backend for every non-Latin character it is configured not to emit.
- **Make the low-confidence read visible to callers.** Per reading (2) above, a low-confidence read currently looks identical to a confident correct one. Report confidence alongside every text result so a downstream consumer can threshold it — which is also the honest substitute for the escalation path the design rejected.
- **Set a read-confidence threshold from the measurement**, not from a guess, and log what it discards. The corpus can tell us the confidence distribution; it cannot tell us the accuracy-per-confidence-band, so the threshold has to be picked from labelled data and revisited when the labelled run lands.
- **Add a corpus-level accuracy check to CI's benchmark path** once labels exist, so a recognizer regression fails the build rather than being noticed in production.

**Non-goals:**

- No per-image or per-plate fallback to the LLM backend. The design rejected escalation and nothing measured revives it: it would make worst-case latency the LLM's 6.8s, and a confidence threshold that silently triggers escalation hides accuracy problems behind an unexplained bill rather than surfacing them as a detectable drop.
- No change to the backend default in this change. It is `local` and this change is about measuring whether that was right, not about reversing it in advance of the measurement.
- No retraining the recognizer. The corpus cannot train one — that is why PP-OCR was adopted rather than trained — and swapping the artifact stays a configuration change.

## Capabilities

### New Capabilities
- `local-plate-ocr`: Adds a recognition-accuracy requirement covering character error rate and exact-match rate against transcription labels, reported separately for single-row and stacked plates, and a confidence-threshold requirement covering how an implausibly low-confidence read is treated.

### Modified Capabilities

## Impact

- `lpr_app/ml/compare_backends.py` — gains CER and exact-match scoring; keeps reporting coverage and confidence
- `lpr_app/pipeline/stages/ocr.py` — reads gain a documented confidence threshold; `RecognitionResult` already carries confidence
- `lpr_app/pipeline/local_backend.py` — records what a confidence threshold discards
- A new labels file alongside the corpus, gitignored like the corpus itself, plus documentation of its format in `AGENTS.md`
- `lpr_app/tests/test_pipeline_backend_switch.py` — tests for the threshold behaviour and for the accuracy scoring