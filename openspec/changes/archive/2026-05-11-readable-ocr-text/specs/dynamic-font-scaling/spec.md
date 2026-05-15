## ADDED Requirements

### Requirement: Font size scales proportionally to image height
The system SHALL compute the annotation font size as a function of the source image height, ensuring text remains legible across all image resolutions.

#### Scenario: Large image gets proportionally large font
- **WHEN** a 1920×1080 image is processed
- **THEN** the font size used for labels SHALL be at least 20px

#### Scenario: Small image gets minimum readable font
- **WHEN** a 320×240 image is processed
- **THEN** the font size SHALL be clamped to a minimum of 16px

#### Scenario: Very large image does not produce excessively large font
- **WHEN** a 4000×3000 image is processed
- **THEN** the font size SHALL be capped at a maximum of 64px

### Requirement: TrueType font loaded at computed size
The system SHALL attempt to load a scalable TrueType font at the computed size, falling back gracefully when no TrueType font is available.

#### Scenario: TrueType font available
- **WHEN** a TrueType font file exists at a known system path
- **THEN** the system SHALL load it at the computed font size

#### Scenario: No TrueType font available
- **WHEN** no TrueType font file is found
- **THEN** the system SHALL fall back to PIL's default font and log a warning

### Requirement: Label background adapts to dynamic font size
The label background rectangle and text positioning SHALL automatically adapt to the actual rendered text dimensions, regardless of font size.

#### Scenario: Background rectangle fits label text
- **WHEN** a label is drawn with a dynamically sized font
- **THEN** the background rectangle SHALL fully enclose the rendered text with at least 4px padding
