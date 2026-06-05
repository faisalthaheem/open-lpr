## ADDED Requirements

### Requirement: Result summary replaces status for completed images
The ImageCard component SHALL display a processing result summary instead of the raw status string for images with `processing_status` of "completed".

#### Scenario: Completed with one plate and one OCR result
- **WHEN** an image has `processing_status` "completed" with `plate_count` of 1 and `ocr_count` of 1 and a non-null `first_ocr_text`
- **THEN** the card SHALL display the OCR text value (e.g. '"ABC 1234"') as the primary result summary

#### Scenario: Completed with multiple plates or OCR results
- **WHEN** an image has `processing_status` "completed" and `plate_count` or `ocr_count` is greater than 1
- **THEN** the card SHALL display "<n> plates, <m> OCR" (e.g. "2 plates, 3 OCR")

#### Scenario: Completed with zero plates
- **WHEN** an image has `processing_status` "completed" and `plate_count` of 0
- **THEN** the card SHALL display "0 plates detected"

#### Scenario: Non-completed status
- **WHEN** an image has `processing_status` of "pending", "processing", or "failed"
- **THEN** the card SHALL display the status string with a color-coded badge, matching the current behavior

### Requirement: View Details link replaces filename
The ImageCard component SHALL replace the filename display with a "View Details" link that navigates to the image detail page.

#### Scenario: View Details link display
- **WHEN** an image card is rendered
- **THEN** the card SHALL show a "View Details" text link instead of the filename, linking to `/image/<id>`

### Requirement: Relative timestamp on cards
The ImageCard component SHALL display a relative time string with PST timezone indicator instead of an absolute date-time string.

#### Scenario: Recent image timestamp
- **WHEN** an image card is rendered and the image was uploaded recently (e.g. 5 minutes ago)
- **THEN** the card SHALL show a relative time string (e.g. "5 minutes ago · PST") instead of the full date-time

#### Scenario: Old image timestamp
- **WHEN** an image card is rendered and the image was uploaded more than 30 days ago
- **THEN** the card SHALL show "on <short date> · PST" instead of the full date-time
