## ADDED Requirements

### Requirement: Local plate detection stage
The pipeline SHALL provide a stage that detects license plates in a single image using a local ONNX detector, producing for each detection a plate region and a confidence score.

#### Scenario: Plate detected in a single-plate image
- **WHEN** the detection stage is given an image containing one license plate
- **THEN** it SHALL return one detection whose region bounds the plate and whose confidence is within zero and one

#### Scenario: Multiple plates detected
- **WHEN** the detection stage is given an image containing several license plates
- **THEN** it SHALL return one detection per plate with distinct regions

#### Scenario: Stacked two-line plate is detected as one plate
- **WHEN** the detection stage is given an image containing a plate whose characters are arranged in two stacked rows
- **THEN** it SHALL return a single detection covering both rows, not one detection per row

#### Scenario: Image with no plates
- **WHEN** the detection stage is given an image containing no license plate
- **THEN** it SHALL return an empty detection list rather than a low-confidence spurious detection

#### Scenario: Low-confidence detections are discarded
- **WHEN** the stage produces a detection whose confidence is below the configured confidence threshold
- **THEN** that detection SHALL be discarded before being passed to downstream stages

#### Scenario: Duplicate detections are suppressed
- **WHEN** the stage produces two detections with substantially the same region
- **THEN** it SHALL retain at most one of them, chosen by higher confidence, and discard the other

### Requirement: Detection coordinates map to the original image
Detections produced from a resized or downscaled input SHALL be expressed in the coordinate space of the original image.

#### Scenario: Detection input is downscaled for speed
- **WHEN** the detector consumes an image resized from the original dimensions
- **THEN** the returned coordinates SHALL be scaled back to the original image dimensions

#### Scenario: Aspect ratio is preserved by resizing
- **WHEN** the input image is resized for detection
- **THEN** the resize SHALL preserve the original aspect ratio so that returned coordinates do not distort the detected plate

#### Scenario: Coordinates are clamped to image bounds
- **WHEN** a scaled coordinate would fall outside the original image bounds
- **THEN** it SHALL be clamped to the corresponding image edge

### Requirement: Detector is selectable as the detection backend
The system SHALL allow plate detection to be performed by either the local ONNX detector or the existing LLM backend, selected by configuration, with the LLM as the default until accuracy is validated.

#### Scenario: LLM backend remains the default
- **WHEN** no backend override is configured
- **THEN** plate detection SHALL be performed by the LLM backend

#### Scenario: Local backend selected explicitly
- **WHEN** the backend is configured to select the local detector
- **THEN** plate detection SHALL be performed by the ONNX detector and the LLM SHALL not be invoked for detection

#### Scenario: Both backends produce the same detections shape
- **WHEN** detection is performed by either backend
- **THEN** the result SHALL populate the same detections collection shape, so callers and the API do not branch on which backend ran

### Requirement: Detector weights are licensed compatibly with the project
Detector weights SHALL be distributed under a license compatible with the project's own license, and the license SHALL be recorded with the artifact.

#### Scenario: AGPL-licensed detector is not adopted
- **WHEN** a candidate detector's weights or code are licensed under AGPL-3.0
- **THEN** that detector SHALL NOT be adopted for distribution with this Apache-2.0 application

#### Scenario: Selected detector's license is recorded
- **WHEN** a detector is selected for the pipeline
- **THEN** its license identifier SHALL be recorded alongside its artifact provenance, and the artifact SHALL NOT be used until that license is recorded