from __future__ import annotations

import urllib.parse
import urllib.request
from dataclasses import dataclass

from .evidence import EntityRef, EvidencePacket, edge_atom


DEFAULT_ANNOTATIONS = [
    "source",
    "data_source",
    "knowledge_source",
    "score",
    "edge_score",
    "confidence",
    "edge_confidence",
    "evidence",
    "evidence_code",
    "evidence_code_name",
    "db_reference",
    "reference",
    "references",
    "pubmed_references",
    "source_url",
    "biological_context",
    "interaction_context",
    "interaction_type",
    "reactome_pathway",
]


@dataclass
class MorkClient:
    base_url: str
    namespace: str = "annotation"
    timeout: int = 30

    def _wrap(self, expression: str) -> str:
        namespace = self.namespace.strip()
        if not namespace or namespace == "-":
            return expression
        return f"({namespace} {expression})"

    def export(self, pattern: str, template: str) -> list[str]:
        url = "{}/export/{}/{}/".format(
            self.base_url.rstrip("/"),
            urllib.parse.quote(pattern, safe=""),
            urllib.parse.quote(template, safe=""),
        )
        request = urllib.request.Request(url, headers={"User-Agent": "bioclaw-symbolic/0.1"})
        data = urllib.request.urlopen(request, timeout=self.timeout).read().decode()
        return [line.strip() for line in data.splitlines() if line.strip()]

    def atom_exists(self, expression: str) -> bool:
        rows = self.export(self._wrap(expression), expression)
        return any(row == expression for row in rows)

    def annotation_values(self, expression: str, annotation: str) -> list[str]:
        template = f"({annotation} $v)"
        rows = self.export(self._wrap(f"({annotation} {expression} $v)"), template)
        prefix = f"({annotation} "
        values = []
        for row in rows:
            if row.startswith(prefix) and row.endswith(")"):
                values.append(row[len(prefix) : -1].strip())
        return values

    def evidence_packet(
        self,
        edge_type: str,
        source: EntityRef,
        target: EntityRef,
        annotations: list[str] | None = None,
    ) -> EvidencePacket:
        expression = edge_atom(edge_type, source.label, source.identifier, target.label, target.identifier)
        exists = self.atom_exists(expression)
        packet_annotations: dict[str, list[str]] = {}
        for annotation in annotations or DEFAULT_ANNOTATIONS:
            values = self.annotation_values(expression, annotation)
            if values:
                packet_annotations[annotation] = values
        return EvidencePacket(
            edge_type=edge_type,
            source=source,
            target=target,
            exists=exists,
            annotations=packet_annotations,
        )
