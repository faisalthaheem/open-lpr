## ADDED Requirements

### Requirement: Plate region is rectified to a layout-appropriate aspect ratio
The system SHALL map each detected plate region through a perspective transform to a rectangular image at an aspect ratio appropriate to the plate's layout, so that recognition receives a deskewed plate.

#### Scenario: Skewed plate is deskewed
- **WHEN** a detection's plate is rotated or non-rectangular
- **THEN** the rectified crop SHALL have the glyphs upright and the plate edges parallel to the crop edges

#### Scenario: Aspect ratio is configurable rather than a single global constant
- **WHEN** a canonical aspect ratio is configured for the active layout
- **THEN** the output crop SHALL use that ratio, and the system SHALL NOT force a single ratio across layouts whose proportions differ

#### Scenario: Stacked two-line plates are rectified to a proportion suited to two rows
- **WHEN** the detected plate is a stacked two-line plate
- **THEN** the rectified crop SHALL preserve both rows of characters legibly, and SHALL NOT compress the plate into a single-row proportion

#### Scenario: Output dimensions are fixed
- **WHEN** rectification is configured with an output width and height
- **THEN** the output crop SHALL have exactly those dimensions, so that the recognizer receives a consistent input shape

### Requirement: Rectification works from a bounding region when corner geometry is unavailable
The system SHALL accept an axis-aligned bounding region as input to rectification and SHALL derive corner positions from it when explicit corner geometry is unavailable.

#### Scenario: Only a bounding box is available
- **WHEN** a detection provides only an axis-aligned bounding region and no corner points
- **THEN** rectification SHALL proceed using that region's corners and SHALL still produce a rectified crop

#### Scenario: Explicit corners are used when provided
- **WHEN** a detection provides corner geometry
- **THEN** rectification SHALL use those corners rather than the bounding region's corners

### Requirement: Rectification does not use a model
The rectification stage SHALL compute its transform using classical image processing and SHALL NOT load a learned model or perform inference.

#### Scenario: No artifact is loaded
- **WHEN** the rectification stage executes
- **THEN** it SHALL perform no model inference and SHALL declare no model artifact

#### Scenario: Rectification contributes negligible latency
- **WHEN** rectification runs for a batch of plates
- **THEN** its measured duration SHALL be recorded and SHALL be reported per-stage so its cost is distinguishable from model inference

### Requirement: Degenerate regions are handled explicitly
When a detected plate region is degenerate, self-intersecting, or smaller than a configured minimum area, the system SHALL treat rectification as failed rather than producing a corrupt crop.

#### Scenario: Self-intersecting geometry is rejected
- **WHEN** four explicit corner points do not form a simple quadrilateral
- **THEN** rectification SHALL be reported as failed and no crop SHALL be produced for that detection

#### Scenario: Too-small detection is rejected
- **WHEN** the plate region's area is below the configured minimum area
- **THEN** rectification SHALL be reported as failed and no crop SHALL be produced

#### Scenario: Failed rectification yields no recognition result
- **WHEN** rectification fails for a detection
- **THEN** the recognition stage SHALL receive no crop for that detection, SHALL be skipped for it, and the detection SHALL report no recognized text

### Requirement: Rectification can be bypassed
The system SHALL allow rectification to be disabled by configuration, in which case the detection's rectangular bounding region is passed onward unchanged.

#### Scenario: Rectification disabled
- **WHEN** the pipeline is configured to bypass rectification
- **THEN** the crop passed to recognition SHALL be derived from the detection's bounding region rather than from a perspective transform, and no rectification SHALL be performed