## ADDED Requirements

### Requirement: Training tooling is separate from the web runtime
Model training, ONNX export, and benchmarking SHALL live in a subpackage that the Django application does not import, and their dependencies SHALL NOT be required to run the web application.

#### Scenario: Web runtime does not import training modules
- **WHEN** the Django application starts and image processing is exercised
- **THEN** no training module SHALL be imported and no training dependency SHALL be loaded

#### Scenario: Training dependencies are declared separately
- **WHEN** a contributor installs the application's runtime dependencies
- **THEN** the training framework and other training-only dependencies SHALL not be required for the installation to succeed

#### Scenario: Training tooling runs standalone
- **WHEN** a training or export or benchmark script is invoked
- **THEN** it SHALL run as a standalone entry point and SHALL NOT require the Django settings or application startup

### Requirement: Annotated corpus is located outside the repository
The training tooling SHALL locate the annotated image corpus by a configurable path resolved from an environment variable with a documented default, and SHALL NOT expect the corpus to be committed to the repository.

#### Scenario: Corpus path comes from configuration
- **WHEN** a corpus path environment variable is set
- **THEN** the tooling SHALL load annotations and images from that location

#### Scenario: Documented default is used when unset
- **WHEN** the corpus path environment variable is unset
- **THEN** the tooling SHALL fall back to the documented default location and SHALL report the resolved path

#### Scenario: Missing corpus is reported clearly
- **WHEN** the resolved corpus location does not exist or lacks its annotation database
- **THEN** the tooling SHALL exit with an error naming the resolved path and stating what was expected there

#### Scenario: Corpus is absent from version control
- **WHEN** the repository is cloned
- **THEN** the corpus SHALL not be present in the working tree and its absence SHALL not prevent the application from starting, since the application does not read the corpus

### Requirement: Corpus annotations are loaded from the published schema
The training tooling SHALL load plate annotations from the corpus's annotation database, reading per-image records of file name, image dimensions, and a per-image region list containing coordinates, dimensions, and label, and SHALL resolve each annotation's file name to an image under the corpus's image directory. Regions whose coordinates are axis-aligned boxes SHALL be supported, since that is the geometry the corpus provides.

#### Scenario: Annotation record is parsed into a training sample
- **WHEN** an annotation record names an image, its dimensions, and a region for a plate
- **THEN** the tooling SHALL yield a sample pairing that image with the plate region and its label

#### Scenario: Region coordinates are expressed in absolute image pixels
- **WHEN** a region's coordinates and dimensions are read
- **THEN** the resulting box SHALL be positioned in the coordinate space of the full-size image, not of a resized copy

#### Scenario: Axis-aligned box regions are usable for training
- **WHEN** the corpus provides only axis-aligned region coordinates and no corner or polygon geometry
- **THEN** the tooling SHALL still produce usable training samples, and SHALL NOT require corner annotations that the corpus does not contain

#### Scenario: Annotation records lacking a plate region are skipped
- **WHEN** an annotation record contains no region or is marked as deleted, background, or unreviewed
- **THEN** the tooling SHALL exclude that record from the training set and count it as skipped

#### Scenario: Missing image file is reported
- **WHEN** an annotation names an image that is not present in the image directory
- **THEN** the tooling SHALL report the missing file name and its count rather than silently discarding it

#### Scenario: Multiple annotation databases are distinguished
- **WHEN** the corpus contains more than one annotation database
- **THEN** the tooling SHALL report which databases it found and which it used, rather than assuming a single authoritative split

### Requirement: Split is deterministic and reproducible
Training and validation partitions SHALL be produced by a seeded split so repeated runs evaluate on the same data, and the seed SHALL be configurable.

#### Scenario: Same seed yields the same split
- **WHEN** the corpus is split twice with the same seed
- **THEN** both splits SHALL assign identical images to training and validation

#### Scenario: Different seed yields a different split
- **WHEN** the corpus is split with a different seed
- **THEN** the resulting partition SHALL differ from the original

#### Scenario: No image appears in both partitions
- **WHEN** a split is produced
- **THEN** the intersection of the training and validation image sets SHALL be empty

### Requirement: Model identity is recorded
For each exported model artifact, the tooling SHALL record the artifact filename, its content checksum, and the training configuration and corpus version used to produce it, so a deployed model can be identified and reproduced.

#### Scenario: Export writes a manifest entry
- **WHEN** a model is exported to ONNX
- **THEN** a manifest entry SHALL be written containing the artifact filename, its checksum, the training configuration, and the corpus version

#### Scenario: Adopted model records upstream identity and license
- **WHEN** an upstream pretrained model is adopted rather than trained from scratch
- **THEN** its manifest entry SHALL record the upstream source, checkpoint identifier, and license alongside its checksum

#### Scenario: Deployed model is identifiable
- **WHEN** a model artifact is present in the model's configured path
- **THEN** the manifest entry for that filename SHALL reveal which training configuration and corpus version produced it, or which upstream checkpoint it came from

#### Scenario: Model artifacts are not committed
- **WHEN** a model artifact is written to the model's directory
- **THEN** that directory SHALL be excluded from version control, while the manifest remains reviewable