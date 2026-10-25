## Purpose

Provides a curated, structured catalog of supported local models with capability, modality, size, and hardware requirement metadata.

## ADDED Requirements

### Requirement: Model Catalog Definitions
The system SHALL maintain a versioned catalog of supported local models. Each catalog entry MUST include a display name, exact Ollama model identifier and tag, model family and variant, supported input modalities (e.g., text, image), approximate download size when verified, compatibility constraints, recommendation status, catalog metadata version, and source of the catalog entry.

#### Scenario: Lookup model by identifier
- **WHEN** the system or user requests details for model identifier `gemma4:e2b`
- **THEN** the catalog returns entry metadata including display name "Gemma 4 E2B", input modalities including text and image, recommendation status, and verified download size.

#### Scenario: Unknown model query
- **WHEN** a query is made for a model identifier not in the catalog
- **THEN** the catalog indicates that the model is uncataloged and provides default fallback capability assumptions.

### Requirement: Capability and Modality Verification
The catalog SHALL explicitly declare supported input modalities and capability requirements for each model. The catalog MUST NOT assume that all Gemma-family models support multimodal/image inputs without explicit verification.

#### Scenario: Multimodal support flag check
- **WHEN** the system checks whether a selected model supports image input for multimodal folder classification
- **THEN** the system verifies the model's declared modalities in the catalog and rejects models lacking required modalities for multimodal features.

### Requirement: Hardware and Resource Warnings
The catalog SHALL provide advisory hardware requirements and memory guidelines. The system MUST evaluate the host device resources against the catalog model metadata and issue advisory warnings if the selected model is estimated to exceed practical memory limits (e.g., recommending lightweight models like Gemma 4 E2B on an 8 GB unified-memory host).

#### Scenario: Advisory warning on resource-constrained machine
- **WHEN** a user selects a larger model requiring 8+ GB RAM on an 8 GB unified-memory Mac
- **THEN** the system presents an advisory warning about potential memory pressure before proceeding.

#### Scenario: Explicit user override of recommendation
- **WHEN** the user acknowledges an advisory resource warning and chooses to proceed
- **THEN** the system honors the user's explicit override and proceeds with the selection.
