from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def atom(label: str, identifier: str) -> str:
    return f"({label} {identifier})"


def edge_atom(edge_type: str, source_label: str, source_id: str, target_label: str, target_id: str) -> str:
    return f"({edge_type} {atom(source_label, source_id)} {atom(target_label, target_id)})"


@dataclass(frozen=True)
class EntityRef:
    label: str
    identifier: str

    @classmethod
    def parse(cls, value: str) -> "EntityRef":
        if ":" not in value:
            raise ValueError(f"entity must be label:id, got {value!r}")
        label, identifier = value.split(":", 1)
        label = label.strip()
        identifier = identifier.strip()
        if not label or not identifier:
            raise ValueError(f"entity must be label:id, got {value!r}")
        return cls(label=label, identifier=identifier)

    def atom(self) -> str:
        return atom(self.label, self.identifier)


@dataclass
class EvidencePacket:
    edge_type: str
    source: EntityRef
    target: EntityRef
    exists: bool
    annotations: dict[str, list[str]] = field(default_factory=dict)

    @property
    def edge_atom(self) -> str:
        return edge_atom(
            self.edge_type,
            self.source.label,
            self.source.identifier,
            self.target.label,
            self.target.identifier,
        )

    def values(self, *names: str) -> list[str]:
        out: list[str] = []
        for name in names:
            out.extend(self.annotations.get(name, []))
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge": self.edge_atom,
            "edge_type": self.edge_type,
            "source": {"label": self.source.label, "id": self.source.identifier},
            "target": {"label": self.target.label, "id": self.target.identifier},
            "exists": self.exists,
            "annotations": self.annotations,
        }

    def short_summary(self) -> str:
        if not self.exists:
            return f"No edge atom found for {self.edge_atom}."
        parts = [f"Found edge atom {self.edge_atom}."]
        sources = self.values("source", "data_source", "knowledge_source")
        if sources:
            parts.append(f"Sources: {', '.join(sorted(set(sources)))}.")
        scores = self.values("score", "edge_score", "confidence", "edge_confidence")
        if scores:
            parts.append(f"Confidence-bearing values: {', '.join(scores)}.")
        refs = self.values("reference", "references", "db_reference", "pubmed_references", "source_url")
        if refs:
            parts.append(f"References/context ids: {', '.join(refs[:8])}.")
        return " ".join(parts)
