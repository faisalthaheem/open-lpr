## ADDED Requirements

### Requirement: Local plate text recognition stage
The pipeline SHALL provide a stage that reads the text from a single rectified plate crop using a local ONNX recognizer, producing recognized text and a confidence value.

#### Scenario: Text recognized from a clean plate crop
- **WHEN** the recognition stage is given a rectified plate crop with legible characters
- **THEN** it SHALL return the recognized character sequence and a confidence within zero and one

#### Scenario: Recognition result carries a confidence
- **WHEN** the recognition stage returns a result
- **THEN** it SHALL include a confidence value that reflects the model's certainty for that crop

#### Scenario: Illegible crop yields an empty result
- **WHEN** the recognition stage is given a crop with no legible characters
- **THEN** it SHALL return an empty text result and SHALL NOT fabricate characters to fill it

### Requirement: Stacked two-line plates are read as multiple rows
The recognition stage SHALL support plates whose characters are arranged in two stacked rows, and SHALL NOT concatenate the rows into a single unreadable sequence.

#### Scenario: Two-line plate is recognized row by row
- **WHEN** the recognition stage is given a rectified crop of a stacked two-line plate
- **THEN** it SHALL recognize each row separately and combine them into one result with the row order preserved

#### Scenario: Row separation is applied before recognition
- **WHEN** a crop is identified as a stacked two-line plate
- **THEN** the stage SHALL split the crop into its two rows prior to recognition, rather than recognizing the combined image as one line

#### Scenario: Single-row plate is not split
- **WHEN** the recognition stage is given a single-row plate crop
- **THEN** the crop SHALL NOT be split and SHALL be recognized as one line

#### Scenario: Row split does not corrupt a single-row plate
- **WHEN** the stage is configured to attempt row splitting for a crop that contains only one row of characters
- **THEN** the second row SHALL NOT introduce spurious characters into the result

### Requirement: Decoding is restricted to the configured charset profile
The recognition stage SHALL emit only characters present in the configured charset profile, and SHALL exclude any token outside it.

#### Scenario: Non-charset tokens are suppressed
- **WHEN** the model's decoding produces a token that is not a member of the configured charset
- **THEN** that token SHALL NOT appear in the returned text

#### Scenario: Characters absent from a region's plates are excluded by its profile
- **WHEN** a configured charset profile for a region excludes a character that region's plates do not use
- **THEN** the recognition stage SHALL NOT emit that character for any input

#### Scenario: Charset profile is selectable at runtime
- **WHEN** a different charset profile is selected
- **THEN** the recognition stage SHALL restrict its output to that profile's characters, without code changes

#### Scenario: Default profile is alphanumeric
- **WHEN** no charset profile is explicitly selected
- **THEN** the stage SHALL restrict its output to digits and Latin letters

### Requirement: Recognized text passes existing validation
Recognized text SHALL be validated by the existing OCR text validation logic before being reported, so implausible results are discarded on the same terms as the LLM backend.

#### Scenario: Implausible text is discarded
- **WHEN** the recognition stage returns text that the existing validation logic rejects as implausible
- **THEN** the text SHALL be discarded rather than reported as a plate result

#### Scenario: Validated text populates the detections result
- **WHEN** the recognition stage returns text that passes validation
- **THEN** the text and its confidence SHALL be recorded against the corresponding detection in the detections collection

### Requirement: One recognizer invocation per plate
Each detected plate SHALL be passed to the recognition stage exactly once, and the batch size SHALL be bounded by configuration. For a stacked two-line plate, the rows arising from one plate SHALL count as a single plate's recognition.

#### Scenario: Each plate recognized exactly once
- **WHEN** an image yields three plate detections
- **THEN** the recognition stage SHALL be invoked for three plates, and no plate SHALL be recognized twice

#### Scenario: Batch size bounds a single invocation
- **WHEN** the number of detected plates exceeds the configured recognition batch size
- **THEN** the plates SHALL be processed across multiple invocations, none exceeding the configured batch size