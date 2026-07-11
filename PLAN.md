# BioClaw Symbolic Implementation Plan

BioClaw is an OmegaClaw-based symbolic evidence layer for MORK
BioAtomspace. It is not a general chatbot. Its purpose is to make large
schema-backed biological atomspaces inspectable, auditable, and useful for
curation by extracting bounded evidence packets and applying focused symbolic
reasoning over those packets.

This plan follows the revised BioClaw architecture paper:

```text
MORK BioAtomspace
  -> schema-aware extraction
  -> bounded evidence packets / neighborhoods / schema paths
  -> OmegaClaw PLN/NAL symbolic reasoning
  -> curator-facing evidence objects and exports
```

The key constraint is that BioClaw must not reason globally over the full KG.
Every reasoning task must be grounded in a bounded retrieved slice of MORK.

## Implementation Rule

Follow the phase order below. Do not add more presentation/export work until
the active Phase 2 reasoning milestone is implemented or explicitly deferred.

When a feature is only formatting, call it formatting. When a feature is only a
Python heuristic, call it a Python heuristic. Do not label it PLN/NAL unless it
actually uses OmegaClaw's symbolic reasoning surface through `(metta ...)`,
`|~`, `|-`, or direct truth-value operators.

Experiments are allowed only when they answer a question from this plan. The
workflow is:

```text
experiment -> lesson -> update or confirm PLAN.md -> implement planned milestone
```

Do not drift from this plan by adding adjacent features. If an experiment shows
that the plan should change, update this document first and make the reason
explicit before implementation continues.

## OmegaClaw Symbolic Surface To Use

BioClaw should use more than PLN revision. OmegaClaw includes installed
symbolic reasoning surfaces that can support the Phase 2 plan:

- PLN public operator: `|~`
- NAL public operator: `|-`
- PLN truth functions:
  - `Truth__Revision`
  - `Truth__Deduction`
  - `Truth__Induction`
  - `Truth__Abduction`
  - `Truth__ModusPonens`
  - `Truth__SymmetricModusPonens`
  - `Truth__Negation`
  - inversion
  - equivalence-to-implication
  - transitive similarity
  - evaluation implication
  - member deduction

Revision is only one supported reasoning form. BioClaw should use revision
only when there are multiple comparable truth values for the same bounded
claim. For most BioKG work, the more important reasoning targets are
schema-path support propagation, bounded hypothesis support, and curation-state
assessment.

## Current Status

### Completed Or Partially Completed

- Schema-aware extraction foundation is implemented.
- Exact-edge MORK evidence packet extraction is implemented.
- Neighborhood extraction is implemented.
- Schema property-role handling is implemented through schema policy.
- Property auditing exists.
- Schema-path discovery and basic MORK path instance tracing exist.
- Exact packet dispatch through OmegaClaw `(metta ...)` mock-loop was proven.
- Bounded neighborhood curation-state atoms were dispatched through OmegaClaw
  `(metta ...)`.
- Evidence cards and JSON/CSV/markdown exports exist, but these are Phase 3
  presentation artifacts and should not be mistaken for new reasoning.

### Not Yet Done

- Real Phase 2 schema-path PLN reasoning is not implemented.
- Path-level support propagation is not implemented.
- NAL-style curation-state reasoning is not implemented; current labels are
  packet-local Python assessment labels.
- Exact-claim PLN revision is only partially implemented/proven and applies
  only when comparable truth values exist.
- Representative validation across relation classes is incomplete.

## Phase 1: Schema-Aware Evidence Extraction

**Description:** Build the foundation for BioClaw to inspect BioCypher/MORK
BioKGs through schema-guided retrieval. This phase identifies relation
capabilities from the schema and adapter configuration, then extracts bounded
evidence packets from MORK for selected biological claims, neighborhoods, and
schema paths.

### Milestone 1: Schema Capability Registry

Build a schema capability registry that maps:

- edge types;
- valid source and target classes;
- supported evidence properties;
- source/provenance metadata;
- score/confidence properties;
- evidence-code properties;
- reference properties;
- biological context properties;
- suitable reasoning modes.

The registry must be driven by the active BioCypher schema and schema policy,
not by hardcoded relation-specific biological assumptions.

### Milestone 2: MORK Evidence Packet Extraction

Implement MORK evidence packet extraction for:

- exact claims;
- relation neighborhoods;
- schema paths.

Packets should retrieve the edge atom plus attached atoms where available:

- source;
- score or confidence;
- evidence code;
- reference;
- biological context;
- source URL;
- node names and identifiers.

### Milestone 3: Extraction Validation Across Relation Classes

Validate extraction across representative relation classes, including:

- protein-protein interactions;
- enhancer-gene associations;
- gene-transcript-protein paths;
- pathway membership;
- disease/phenotype associations.

Validation should check that BioClaw retrieves the expected atoms and does not
confuse schema paths, edge labels, or source/target classes.

**Estimated deadline:** End of Month 1.

## Phase 2: Bounded Symbolic Reasoning

**Description:** Connect retrieved BioKG evidence packets to OmegaClaw's
symbolic reasoning substrate. BioClaw should not reason over the whole KG at
once. It should perform focused reasoning over query-relevant evidence packets,
neighborhoods, and schema paths.

Phase 2 is the current priority.

### Milestone 1: PLN-Style Exact-Claim Evidence Revision

Implement PLN-style evidence revision for exact claims supported by multiple
comparable truth values.

Use this only when the extracted packet contains semantically comparable
support for the same bounded claim, for example:

```text
(claim A) source_1 score/confidence x
(claim A) source_2 score/confidence y
```

Required behavior:

- preserve source-specific scores, evidence codes, references, and caveats;
- call OmegaClaw's real symbolic surface, not only Python math;
- emit `Truth__Revision` or `|~` calls where appropriate;
- report when revision is not applicable because there is only one comparable
  truth value.

Important: exact-claim revision is not the main BioClaw reasoning story. It is
one supported mode.

### Milestone 2: PLN Schema-Path Reasoning

Implement schema-path reasoning for bounded biological paths, such as:

```text
gene -> transcript -> protein
gene -> transcript -> protein -> interaction
gene -> transcript -> protein -> interaction -> pathway/context
```

This is the next implementation target.

Required behavior:

- retrieve explicit MORK path instances;
- convert each path edge into truth-valued support;
- preserve the full path trace;
- apply OmegaClaw PLN rules beyond revision where meaningful, especially:
  - `Truth__Deduction` for path support propagation;
  - `Truth__ModusPonens` for rule-like implication over supported facts;
  - `Truth__Abduction` for bounded hypothesis candidates when an observed
    downstream relation suggests a possible upstream biological explanation;
  - `Truth__Induction` only where multiple instances support a generalization;
- return a KG-derived hypothesis with traceable support, not a new asserted
  biological fact.

Example target:

```text
IMPACT
  -> transcribes_to transcript
  -> translates_to protein
  -> interacts_with protein
```

Expected output:

- path instance;
- edge support values;
- PLN-derived path support;
- caveat;
- next suggested check.

### Milestone 3: NAL-Style Curation State Labels

Implement NAL-style curation state reasoning for claims and neighborhoods.

Current Python labels are only interim. The Phase 2 target is to emit and test
symbolic state reasoning through OmegaClaw's NAL or symbolic rule surface.

States include:

- actionable;
- weak support;
- single-source support;
- multi-source support;
- missing evidence;
- conflicting support;
- prediction-only;
- curated-support;
- hypothesis candidate;
- needs curator review.

Required behavior:

- state labels must be derived from evidence atoms and schema roles;
- each state must include the evidence condition that produced it;
- missing evidence should be represented as an audit state, not as evidence of
  biological absence;
- NAL-style states should support follow-up audit workflows.

**Estimated deadline:** End of Month 2.

## Phase 3: Evidence Reports, Exports, And Validation

**Description:** Turn BioClaw's retrieval and reasoning outputs into practical
curator-facing artifacts. This phase should happen after Phase 2 reasoning
outputs exist for the relevant workflow.

### Milestone 1: Evidence Cards

Build evidence-card outputs that include:

- biological claim;
- schema path, where applicable;
- supporting atoms;
- source breakdown;
- scores/evidence codes;
- references/context;
- symbolic reasoning result;
- caveats;
- suggested next checks.

Evidence cards have already started, but they must be updated to display real
Phase 2 reasoning outputs once those are implemented.

### Milestone 2: Structured Exports

Add JSON/CSV export for:

- evidence packets;
- ranked multi-source claims;
- schema-path hypotheses;
- KG quality findings;
- curation-state findings.

Exports should be usable by downstream analysis pipelines.

### Milestone 3: Representative Validation

Validate BioClaw on selected biological workflows:

- multi-source PPI reconciliation;
- enhancer-gene support review;
- gene-product-path completeness;
- disease/phenotype evidence audit.

Validation must check:

- entity resolution correctness;
- source extraction correctness;
- score/evidence/reference preservation;
- path trace correctness;
- PLN/NAL reasoning output correctness;
- usefulness of reports for curator review.

**Estimated deadline:** End of Month 3.

## Immediate Next Work Item

Implement **Phase 2 Milestone 2: PLN schema-path reasoning**.

Do not continue expanding evidence-card formatting first.

Concrete next implementation:

1. Add a path reasoning payload for existing schema-path instances.
2. Start with a bounded path such as:

   ```text
   gene -> transcript -> protein
   ```

3. Extend to:

   ```text
   gene -> transcript -> protein -> interacts_with -> protein
   ```

4. Convert each path edge into support atoms.
5. Emit OmegaClaw `(metta ...)` calls using PLN deduction or modus ponens where
   applicable.
6. Generate a mock-loop test proving that the path-level PLN call is dispatched
   through OmegaClaw.
7. Only after dispatch is proven, parse or report the derived path support.

## Non-Goals For This Quarter

- Global reasoning over the full BioAtomspace.
- Rebuilding a general chatbot interface.
- Treating memory as biological truth.
- Claiming PLN/NAL when only Python labels were used.
- Turning all heterogeneous evidence into one scalar without a traceable rule.
- Hardcoding relation-specific behavior for a small demo graph.
- Continuing Phase 3 formatting work before Phase 2 reasoning milestones are
  implemented.
