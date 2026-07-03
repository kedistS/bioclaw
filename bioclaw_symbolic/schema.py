from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .yaml_compat import load_yaml


SOURCE_NAMES = {"source", "data_source", "knowledge_source", "provided_by"}
SCORE_NAMES = {"score", "edge_score", "confidence", "edge_confidence", "p_value", "q_value"}
EVIDENCE_NAMES = {"evidence", "evidence_code", "evidence_code_name"}
REFERENCE_NAMES = {"reference", "references", "db_reference", "pubmed_references", "source_url"}
CONTEXT_NAMES = {"biological_context", "interaction_context", "interaction_type", "reactome_pathway"}


@dataclass(frozen=True)
class EdgeCapability:
    name: str
    label: str
    source: Any
    target: Any
    properties: tuple[str, ...]

    @property
    def normalized_properties(self) -> set[str]:
        return {prop.lower() for prop in self.properties}

    @property
    def has_source(self) -> bool:
        return bool(SOURCE_NAMES.intersection(self.normalized_properties))

    @property
    def has_score(self) -> bool:
        props = self.normalized_properties
        return bool(SCORE_NAMES.intersection(props)) or any(prop.endswith("_score") for prop in props)

    @property
    def has_evidence(self) -> bool:
        return bool(EVIDENCE_NAMES.intersection(self.normalized_properties))

    @property
    def has_reference(self) -> bool:
        return bool(REFERENCE_NAMES.intersection(self.normalized_properties))

    @property
    def has_context(self) -> bool:
        return bool(CONTEXT_NAMES.intersection(self.normalized_properties))

    def reasoning_modes(self) -> list[str]:
        modes = ["edge_presence"]
        if self.has_source:
            modes.append("source_audit")
        if self.has_score:
            modes.append("confidence_revision")
        if self.has_evidence:
            modes.append("evidence_code_audit")
        if self.has_reference:
            modes.append("reference_audit")
        if self.has_context:
            modes.append("context_review")
        return modes

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "source": self.source,
            "target": self.target,
            "properties": list(self.properties),
            "reasoning_modes": self.reasoning_modes(),
        }


@dataclass
class SchemaRegistry:
    edges: list[EdgeCapability]

    @classmethod
    def from_file(cls, path: str | Path) -> "SchemaRegistry":
        data = load_yaml(Path(path)) or {}
        edges: list[EdgeCapability] = []
        for name, spec in data.items():
            if not isinstance(spec, dict) or spec.get("represented_as") != "edge":
                continue
            props = spec.get("properties") or {}
            label = spec.get("output_label") or spec.get("input_label") or name.replace(" ", "_")
            edges.append(
                EdgeCapability(
                    name=name,
                    label=label,
                    source=spec.get("source"),
                    target=spec.get("target"),
                    properties=tuple(sorted(str(key) for key in props.keys())),
                )
            )
        return cls(edges=edges)

    def by_label(self, label: str) -> list[EdgeCapability]:
        return [edge for edge in self.edges if edge.label == label or edge.name == label]

    def summary(self) -> dict[str, Any]:
        return {
            "edge_types": len(self.edges),
            "with_source": sum(edge.has_source for edge in self.edges),
            "with_score": sum(edge.has_score for edge in self.edges),
            "with_evidence": sum(edge.has_evidence for edge in self.edges),
            "with_reference": sum(edge.has_reference for edge in self.edges),
            "with_context": sum(edge.has_context for edge in self.edges),
        }
