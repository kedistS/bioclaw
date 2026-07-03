# BioClaw Symbolic

BioClaw Symbolic is a focused OmegaClaw-aligned evidence layer for a MORK
BioAtomspace.

This branch is intentionally different from the earlier IRC multi-agent demo.
It removes the conductor/assistant/reasoner overlay and keeps the work centered
on the part that is not already solved by ordinary assistant systems:

- inspect the loaded BioCypher schema and adapter-derived edge capabilities;
- extract bounded evidence packets from MORK BioAtomspace;
- preserve atom-level provenance, score, evidence, context, and references;
- classify retrieved annotations through schema roles before reasoning;
- run focused symbolic reasoning over the retrieved packet roles;
- produce auditable evidence objects for curators and downstream pipelines.

BioClaw does not treat LLM text or workflow memory as biological truth. The
source of biological evidence is the MORK BioAtomspace.

## Architecture

```text
User / API request
    |
    v
Planner / CLI / future skill
    |
    +--> Schema capability registry
    |       Reads BioCypher schema and exposes relation classes, source/target
    |       types, evidence-bearing properties, scores, references, and context.
    |
    +--> MORK evidence extractor
    |       Retrieves a bounded packet: edge atom + attached source, score,
    |       evidence, reference, and context atoms.
    |
    +--> Symbolic reasoner
    |       Applies packet-local PLN/NAL-style operations over schema roles:
    |       source aggregation, revision over confidence-bearing evidence,
    |       schema-path trace status, and curation-state labels.
    |
    +--> Report / export
            Emits JSON evidence objects and concise curator-facing summaries.
```

The important constraint is scale: BioClaw should not try to load the full
BioAtomspace into PLN/NAL. It retrieves a small, schema-valid evidence packet
and reasons over that bounded packet.

## Repository Layout

```text
bioclaw/
├── bioclaw_symbolic/
│   ├── cli.py          # command-line entrypoint
│   ├── evidence.py     # evidence packet data model and summaries
│   ├── mork.py         # MORK export client and packet extraction
│   ├── reasoning.py    # bounded symbolic evidence operations
│   ├── schema.py       # BioCypher schema capability registry
│   └── schema_policy.py # configurable property-role policy
├── config/
│   ├── reasoning.yaml  # neutral default reasoning policy
│   └── schema_roles.yaml # schema property-role mapping
├── examples/
│   └── ppi-edge.json   # example exact-edge request
├── pyproject.toml
└── README.md
```

## Setup

Install in editable mode from this directory:

```bash
python3 -m pip install -e .
```

If dependencies are already available and you do not want to install the
package, run commands with:

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli --help
```

## Inputs

BioClaw expects:

- a reachable MORK service;
- a BioCypher schema YAML matching the loaded data;
- a schema role policy YAML that maps schema properties to roles such as
  source, score, evidence, reference, context, name, xref, and description;
- optional reasoning policy YAML for thresholds and no-schema fallback names.

For the PPI experiment, the MORK service was loaded separately on port `8037`
with STRING, Reactome, and UniProt MeTTa files. The MORK namespace used by the
BioCypher loader is usually `annotation`.

## Inspect Schema Capabilities

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli schema \
  --schema /path/to/biocypher-kg/config/hsa/hsa_schema_config.yaml \
  --schema-policy config/schema_roles.yaml
```

This prints relation classes and whether schema properties map to useful
evidence roles such as source, score, evidence code, references, or context.
The mapping is not embedded in Python; it comes from `config/schema_roles.yaml`
and can be replaced for a different MORK BioAtomspace.

When a command receives `--schema`, BioClaw queries edge annotations from the
properties declared for that edge class in the schema and attaches each
annotation's role to the evidence packet. Summaries, multi-source filtering,
symbolic assessment, and CSV exports then use roles such as `source`, `score`,
`reference`, and `context` instead of fixed annotation names.

If a MORK atom has an extra annotation that is not declared by the active
schema, BioClaw treats that as a schema/adapter alignment issue rather than
silently relying on a Python hardcoded property list.

## Extract An Exact Edge Evidence Packet

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli edge \
  --mork http://localhost:8037 \
  --namespace annotation \
  --source protein:P20645 \
  --edge interacts_with \
  --target protein:P51151 \
  --schema /path/to/biocypher-kg/config/hsa/hsa_schema_config.yaml \
  --include-node-details
```

Expected shape for the current PPI test atomspace depends on the active schema.
For `interacts_with`, the schema-driven output includes declared edge
properties such as:

```json
{
  "edge": "(interacts_with (protein P20645) (protein P51151))",
  "exists": true,
  "annotations": {
    "source": ["STRING", "Reactome"],
    "score": ["0.547"],
    "source_url": ["https://reactome.org/", "https://string-db.org/"],
    "interaction_type": ["physical_association"]
  }
}
```

## Run Bounded Symbolic Interpretation

Add `--reason` to compute a small symbolic summary over the packet:

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli edge \
  --mork http://localhost:8037 \
  --namespace annotation \
  --source protein:P20645 \
  --edge interacts_with \
  --target protein:P51151 \
  --schema /path/to/biocypher-kg/config/hsa/hsa_schema_config.yaml \
  --include-node-details \
  --reason
```

The first reasoning target is exact-edge evidence audit. With `--schema`, this
audit is role-based:

- does the edge exist?
- which annotations have the `source` role and what sources support it?
- which annotations have `score` or `confidence` roles?
- which annotations have `reference`, `context`, or `evidence` roles?
- is it single-source, multi-source, scored, referenced, or missing support?

## Extract A Neighborhood

Exact-edge lookup is useful for debugging, but BioClaw becomes more valuable
when it extracts a bounded neighborhood and identifies source support across
many related edges.

For example, inspect all `interacts_with` edges around one protein:

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli neighborhood \
  --mork http://localhost:8037 \
  --namespace annotation \
  --entity protein:P20645 \
  --edge interacts_with \
  --direction both \
  --max-total 100 \
  --schema /path/to/biocypher-kg/config/hsa/hsa_schema_config.yaml \
  --include-node-details \
  --reason
```

The output summarizes:

- total incident edges found;
- source counts across the neighborhood;
- how many edges have multi-source support;
- which edges are actionable under the configured reasoning policy;
- whether results were truncated by the safety cap.

Use `--only-multisource` to return only edges that have more than one source
annotation within the bounded retrieval result:

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli neighborhood \
  --mork http://localhost:8037 \
  --namespace annotation \
  --entity protein:P20645 \
  --edge interacts_with \
  --direction both \
  --max-total 1000 \
  --only-multisource \
  --schema /path/to/biocypher-kg/config/hsa/hsa_schema_config.yaml \
  --include-node-details \
  --reason
```

Use `--include-packets` when you want every edge packet in the JSON output:

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli neighborhood \
  --mork http://localhost:8037 \
  --namespace annotation \
  --entity protein:P20645 \
  --edge interacts_with \
  --schema /path/to/biocypher-kg/config/hsa/hsa_schema_config.yaml \
  --include-node-details \
  --include-packets \
  --reason
```

Use `--export` to write the returned packet set to a file:

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli neighborhood \
  --mork http://localhost:8037 \
  --namespace annotation \
  --entity protein:P20645 \
  --edge interacts_with \
  --direction both \
  --max-total 1000 \
  --only-multisource \
  --schema /path/to/biocypher-kg/config/hsa/hsa_schema_config.yaml \
  --include-node-details \
  --reason \
  --export p20645_multisource_interactions.json \
  --format json
```

Supported export formats are `json`, `jsonl`, and `csv`. JSON/JSONL retain raw
annotation names plus their schema-derived roles. CSV keeps stable role-based
columns (`sources`, `scores`, `evidence`, `references`, `context`) so downstream
pipelines do not need to know every source-specific annotation name.

Current pagination status: this is bounded retrieval plus export. Native MORK
cursor pagination is not used yet, so `--max-total` is still a safety cap and
`truncated=true` means the result is partial. For full-scale analysis, increase
`--max-total` deliberately and export to JSONL or CSV.

`--include-node-details` is schema-aware. BioClaw reads node properties from the
loaded BioCypher schema, classifies their roles through `config/schema_roles.yaml`,
then queries those properties from MORK. This keeps node enrichment data-driven
instead of hardcoding protein/gene/pathway property names in the code. Use
`--schema-policy /path/to/schema_roles.yaml` to swap the policy for another
atomspace.

## Audit Schema / Atomspace Alignment

Because BioClaw is schema-driven, it can also find mismatches between what the
schema declares and what MORK actually contains. This is useful for large KG
quality control.

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli audit-properties \
  --mork http://localhost:8037 \
  --namespace annotation \
  --schema /path/to/biocypher-kg/config/hsa/hsa_schema_config.yaml \
  --schema-policy config/schema_roles.yaml \
  --entity protein:P20645 \
  --edge interacts_with \
  --direction both \
  --max-total 1000
```

The report compares:

- schema-declared edge properties;
- observed MORK annotation predicates on sampled edge atoms;
- observed properties missing from the schema;
- schema-declared properties not observed in the sampled atomspace.

If MORK contains an annotation such as `pubmed_references` but the active schema
does not declare it for the edge type, this command should report it as
`missing_from_schema`. That should be fixed in the schema/adapter layer rather
than patched into BioClaw Python code.

## What Was Removed From The Old System

This branch deliberately removes:

- IRC/Telegram channel adapters;
- conductor, AssistantOC, and ReasonerOC prompt files;
- internal RPC routing;
- the old monolithic `biokg.py` tool layer;
- Docker image overlays for OmegaClaw demo agents;
- staging/proposal demo commands.

Those pieces were useful for the earlier demo, but they are not the core of the
symbolic BioClaw plan. They can be reintroduced later as wrappers around this
library if needed.

## Current Scope

This branch is the foundation, not the final product. The immediate milestones
are:

1. schema capability registry;
2. MORK evidence packet extraction;
3. exact-edge source/provenance audit;
4. bounded symbolic reasoning over packet-local evidence;
5. JSON/CSV exports for downstream analysis;
6. later OmegaClaw skill integration over these functions.
