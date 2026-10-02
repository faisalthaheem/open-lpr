# detection-schema-simplification Specification

## Purpose
Covers the single supported JSON-array shape of the detections collection, coordinate scaling against that shape, and removal of back-compat constants for superseded prompt templates.

## Requirements

### Requirement: Single supported detections schema
Application code SHALL support exactly one shape for the `detections` collection, which SHALL be a JSON array of detection objects.

#### Scenario: Detections read as a list
- **WHEN** a stored API response contains `detections` as a JSON array
- **THEN** plate count, OCR count, and first OCR text SHALL be derived from that array

#### Scenario: Non-array detections are not special-cased
- **WHEN** application code reads a stored API response whose `detections` value is not a JSON array
- **THEN** the code SHALL NOT contain a dedicated legacy branch for that shape, and aggregate values SHALL be reported as zero

#### Scenario: No legacy text format branching
- **WHEN** OCR text is read from a detection
- **THEN** the code SHALL NOT contain a branch for a text-keyed map format, reading text from the supported field only

### Requirement: Coordinate scaling operates on the supported schema
Coordinate scaling SHALL handle the array form of `detections` and SHALL NOT contain branches for the legacy mapping form.

#### Scenario: Array detections are scaled
- **WHEN** a parsed response contains `detections` as a JSON array and original image dimensions are supplied
- **THEN** plate and OCR coordinates for each array element SHALL be scaled into original image dimensions

#### Scenario: No mapping-form branch
- **WHEN** coordinate scaling is implemented
- **THEN** the implementation SHALL NOT iterate detections as a mapping of keys to detections

### Requirement: Unused back-compat constants removed
Constants retained for backward compatibility with superseded prompt templates SHALL be removed when no code path references them.

#### Scenario: No unused combined-prompt constant
- **WHEN** the inference module is inspected
- **THEN** it SHALL NOT contain a combined detect-and-OCR prompt constant that no code path uses

#### Scenario: Multi-phase prompts remain
- **WHEN** the inference module is inspected
- **THEN** it SHALL retain the separate detection-phase and OCR-phase prompt constants used by the current pipeline
