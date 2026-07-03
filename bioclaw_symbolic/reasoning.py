from __future__ import annotations

from dataclasses import dataclass
from math import prod
from pathlib import Path
from typing import Any

from .evidence import EvidencePacket
from .yaml_compat import load_yaml


@dataclass(frozen=True)
class SymbolicAssessment:
    labels: list[str]
    stv: tuple[float, float]
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "labels": self.labels,
            "stv": {"strength": self.stv[0], "confidence": self.stv[1]},
            "explanation": self.explanation,
        }


def load_policy(path: str | None) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "default_stv": [1.0, 0.5],
        "action_threshold": 0.5,
        "confidence_annotations": ["confidence", "edge_confidence", "staging_confidence"],
        "score_annotations": ["score", "edge_score"],
        "source_annotations": ["source", "data_source", "knowledge_source"],
        "evidence_annotations": ["evidence", "evidence_code", "evidence_code_name"],
        "reference_annotations": ["reference", "references", "db_reference", "pubmed_references", "source_url"],
        "context_annotations": ["biological_context", "interaction_context", "interaction_type", "reactome_pathway"],
    }
    if not path:
        return defaults
    data = load_yaml(Path(path)) or {}
    merged = dict(defaults)
    merged.update(data)
    return merged


def _numeric_values(packet: EvidencePacket, names: list[str]) -> list[float]:
    values: list[float] = []
    for name in names:
        for raw in packet.annotations.get(name, []):
            try:
                values.append(float(raw))
            except ValueError:
                continue
    return [max(0.0, min(1.0, value)) for value in values]


def _unique_values(packet: EvidencePacket, names: list[str]) -> list[str]:
    values: list[str] = []
    for name in names:
        values.extend(packet.annotations.get(name, []))
    return sorted(set(values))


def packet_assessment(packet: EvidencePacket, policy: dict[str, Any] | None = None) -> SymbolicAssessment:
    policy = policy or load_policy(None)
    labels: list[str] = []

    if not packet.exists:
        return SymbolicAssessment(
            labels=["missing_edge"],
            stv=(0.0, 0.0),
            explanation="The requested edge atom was not found in the MORK BioAtomspace.",
        )

    labels.append("edge_present")
    sources = _unique_values(packet, policy["source_annotations"])
    scores = _numeric_values(packet, policy["confidence_annotations"]) + _numeric_values(packet, policy["score_annotations"])
    evidence = _unique_values(packet, policy["evidence_annotations"])
    references = _unique_values(packet, policy["reference_annotations"])
    context = _unique_values(packet, policy["context_annotations"])

    if len(sources) > 1:
        labels.append("multi_source")
    elif len(sources) == 1:
        labels.append("single_source")
    else:
        labels.append("source_missing")

    if scores:
        labels.append("scored")
        # Packet-local confidence combination. This is intentionally bounded and
        # transparent: independent confidence-bearing annotations increase
        # confidence without inventing new biological facts.
        confidence = 1.0 - prod(1.0 - score for score in scores)
        strength = max(scores)
    else:
        labels.append("score_missing")
        strength, confidence = policy["default_stv"]

    if evidence:
        labels.append("evidence_code_present")
    if references:
        labels.append("reference_present")
    if context:
        labels.append("context_present")

    threshold = float(policy.get("action_threshold", 0.5))
    labels.append("actionable" if confidence >= threshold else "needs_review")

    pieces = [f"Edge exists with labels: {', '.join(labels)}."]
    if sources:
        pieces.append(f"Source support: {', '.join(sources)}.")
    if scores:
        pieces.append(f"Confidence-bearing values from packet: {', '.join(f'{score:.3f}' for score in scores)}.")
    if evidence:
        pieces.append(f"Evidence annotations: {', '.join(evidence)}.")
    if references:
        pieces.append(f"References: {', '.join(references[:8])}.")
    if context:
        pieces.append(f"Context: {', '.join(context[:8])}.")

    return SymbolicAssessment(labels=labels, stv=(round(strength, 6), round(confidence, 6)), explanation=" ".join(pieces))
