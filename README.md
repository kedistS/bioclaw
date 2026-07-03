# BioClaw Symbolic

BioClaw Symbolic is a focused OmegaClaw-aligned evidence layer for a MORK
BioAtomspace.

This branch is intentionally different from the earlier IRC multi-agent demo.
It removes the conductor/assistant/reasoner overlay and keeps the work centered
on the part that is not already solved by ordinary assistant systems:

- inspect the loaded BioCypher schema and adapter-derived edge capabilities;
- extract bounded evidence packets from MORK BioAtomspace;
- preserve atom-level provenance, score, evidence, context, and references;
- run focused symbolic reasoning over the retrieved packet;
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
    |       Applies packet-local PLN/NAL-style operations such as source
    |       aggregation, revision over confidence-bearing evidence, schema-path
    |       trace status, and curation-state labels.
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
│   └── schema.py       # BioCypher schema capability registry
├── config/
│   └── reasoning.yaml  # neutral default reasoning policy
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
- optional reasoning policy YAML.

For the PPI experiment, the MORK service was loaded separately on port `8037`
with STRING, Reactome, and UniProt MeTTa files. The MORK namespace used by the
BioCypher loader is usually `annotation`.

## Inspect Schema Capabilities

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli schema \
  --schema /path/to/biocypher-kg/config/hsa/hsa_schema_config.yaml
```

This prints relation classes and whether the schema declares useful evidence
properties such as source, score, evidence code, references, or context.

## Extract An Exact Edge Evidence Packet

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli edge \
  --mork http://localhost:8037 \
  --namespace annotation \
  --source protein:P20645 \
  --edge interacts_with \
  --target protein:P51151
```

Expected shape for the current PPI test atomspace:

```json
{
  "edge": "(interacts_with (protein P20645) (protein P51151))",
  "exists": true,
  "annotations": {
    "source": ["STRING", "Reactome"],
    "score": ["0.547"],
    "interaction_context": ["R-HSA-6814662"],
    "pubmed_references": ["19490898", "21421921"],
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
  --reason
```

The first reasoning target is exact-edge evidence audit:

- does the edge exist?
- which sources support it?
- does it have confidence-bearing score/confidence annotations?
- does it have literature/context/evidence annotations?
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
  --limit 100 \
  --reason
```

The output summarizes:

- total incident edges found;
- source counts across the neighborhood;
- how many edges have multi-source support;
- which edges are actionable under the configured reasoning policy;
- whether results were truncated by the limit.

Use `--include-packets` when you want every edge packet in the JSON output:

```bash
PYTHONPATH=. python3 -m bioclaw_symbolic.cli neighborhood \
  --mork http://localhost:8037 \
  --namespace annotation \
  --entity protein:P20645 \
  --edge interacts_with \
  --include-packets \
  --reason
```

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
