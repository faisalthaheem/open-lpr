## MODIFIED Requirements

### Requirement: Configurable fixed-pixel padding for OCR crop regions
The system SHALL apply a configurable fixed-pixel padding (default 25px) to each side of the bounding box when cropping detected license plates for Phase 2 OCR processing. The padding amount SHALL be read from the `OCR_CROP_PADDING_PX` Django setting. When plate rectification is enabled in the pipeline, the rectified plate crop SHALL be the input to recognition and fixed-pixel padding SHALL NOT be applied, because the perspective transform has already established the crop boundary. Fixed-pixel padding SHALL continue to apply to the LLM backend path and to any pipeline path where rectification is bypassed.

#### Scenario: Standard padding applied on all sides
- **WHEN** a detected plate bounding box is more than 25px from all four image edges
- **THEN** the system SHALL add exactly 25px of padding to each side of the crop region

#### Scenario: Padding clamped at image boundary
- **WHEN** a detected plate bounding box is less than 25px from one or more image edges
- **THEN** the system SHALL use as much padding as available on the constrained side(s), up to the configured amount, without exceeding image boundaries

#### Scenario: Zero available padding
- **WHEN** a detected plate bounding box touches an image edge (0px available)
- **THEN** the system SHALL apply 0px padding on that side

#### Scenario: Custom padding via setting
- **WHEN** `OCR_CROP_PADDING_PX` is set to a value other than 25 in settings
- **THEN** the system SHALL use that value as the padding amount for all sides

#### Scenario: Rectified crop supersedes padding
- **WHEN** the pipeline runs with rectification enabled
- **THEN** recognition SHALL receive the rectified crop directly and SHALL NOT additionally expand it by `OCR_CROP_PADDING_PX`

#### Scenario: Padding still applies when rectification is bypassed
- **WHEN** the pipeline runs with rectification disabled
- **THEN** the crop passed to recognition SHALL be expanded by `OCR_CROP_PADDING_PX` on each side, clamped to image boundaries

### Requirement: Backward-compatible crop_region method
The `ImageProcessor.crop_region()` method SHALL accept a `padding_px` parameter for fixed-pixel padding. When `padding_px` is provided, it SHALL be used instead of the percentage-based `padding_pct`. The `padding_pct` parameter SHALL remain functional for callers that do not pass `padding_px`. The method SHALL remain the cropping mechanism for the LLM backend path and for pipeline paths that bypass rectification, so that adding rectification does not change this method's signature or behavior.

#### Scenario: Fixed-pixel padding takes precedence
- **WHEN** `crop_region` is called with `padding_px=30`
- **THEN** the method SHALL apply 30px padding to each side, clamped to image boundaries, ignoring `padding_pct`

#### Scenario: Percentage padding still works
- **WHEN** `crop_region` is called without `padding_px`
- **THEN** the method SHALL behave exactly as before, using `padding_pct` (default 0.1)