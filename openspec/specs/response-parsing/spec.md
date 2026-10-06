# response-parsing Specification

## Purpose
Covers the single shared JSON extraction helper for fenced model responses, tolerance of unterminated fences, and the unchanged public parser entry points.

## Requirements

### Requirement: Single JSON extraction implementation
Model response parsing SHALL use one shared implementation for extracting a JSON payload from a response that may be wrapped in markdown code fences.

#### Scenario: No duplicated extraction logic
- **WHEN** more than one parser needs to extract JSON from a model response
- **THEN** all parsers SHALL delegate to the same shared extraction helper

### Requirement: Fenced JSON extraction
The shared extractor SHALL return the contents of a fenced block when the response is wrapped in one.

#### Scenario: JSON-tagged fence
- **WHEN** the response contains a fence tagged `json` followed by a closing fence
- **THEN** the extractor SHALL return the content between the opening and closing fences, stripped of surrounding whitespace

#### Scenario: Untagged fence
- **WHEN** the response contains a bare fence followed by a closing fence
- **THEN** the extractor SHALL return the content between the fences

#### Scenario: No fence
- **WHEN** the response contains no fence markers
- **THEN** the extractor SHALL return the whole response stripped of surrounding whitespace

### Requirement: Unterminated fence tolerance
The shared extractor SHALL handle a response containing an opening fence with no matching closing fence, without truncating the payload.

#### Scenario: Opening fence without closing fence
- **WHEN** the response contains an opening fence and no closing fence
- **THEN** the extractor SHALL return the content from the opening fence to the end of the response

#### Scenario: Valid JSON after an unterminated fence parses successfully
- **WHEN** a response contains an opening fence followed by a complete valid JSON document and no closing fence
- **THEN** parsing SHALL succeed and SHALL NOT fail due to the missing closing fence

### Requirement: Parser entry points are unchanged
The existing public parser functions SHALL retain their current names, parameters, and return shapes.

#### Scenario: Existing callers are unaffected
- **WHEN** an existing caller invokes any parser with its current arguments
- **THEN** the parser SHALL accept the same arguments and return the same shape, returning no result on unparseable input
