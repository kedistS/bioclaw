from __future__ import annotations

import urllib.parse
import urllib.request
from dataclasses import dataclass

from .evidence import EntityRef, EvidencePacket, NeighborhoodPacket, edge_atom


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

    @staticmethod
    def _parse_neighbor_rows(rows: list[str], tag: str) -> list[tuple[str, str]]:
        parsed: list[tuple[str, str]] = []
        prefix = f"({tag} "
        for row in rows:
            if not (row.startswith(prefix) and row.endswith(")")):
                continue
            body = row[len(prefix) : -1].strip()
            parts = body.split(maxsplit=1)
            if len(parts) != 2:
                continue
            parsed.append((parts[0], parts[1]))
        return parsed

    def neighborhood(
        self,
        edge_type: str,
        focus: EntityRef,
        direction: str = "both",
        limit: int = 100,
        annotations: list[str] | None = None,
    ) -> NeighborhoodPacket:
        if direction not in {"incoming", "outgoing", "both"}:
            raise ValueError("direction must be incoming, outgoing, or both")

        packets: list[EvidencePacket] = []
        seen: set[str] = set()
        truncated = False

        queries: list[tuple[str, str]] = []
        if direction in {"outgoing", "both"}:
            queries.append(("outgoing", f"({edge_type} {focus.atom()} ($other_label $other_id))"))
        if direction in {"incoming", "both"}:
            queries.append(("incoming", f"({edge_type} ($other_label $other_id) {focus.atom()})"))

        for query_direction, pattern in queries:
            tag = f"bioclaw_neighbor_{query_direction}"
            rows = self.export(self._wrap(pattern), f"({tag} $other_label $other_id)")
            for other_label, other_id in self._parse_neighbor_rows(rows, tag):
                other = EntityRef(other_label, other_id)
                if query_direction == "outgoing":
                    packet = self.evidence_packet(edge_type, focus, other, annotations)
                else:
                    packet = self.evidence_packet(edge_type, other, focus, annotations)
                if packet.edge_atom in seen:
                    continue
                seen.add(packet.edge_atom)
                packets.append(packet)
                if len(packets) >= limit:
                    truncated = True
                    return NeighborhoodPacket(
                        focus=focus,
                        edge_type=edge_type,
                        packets=packets,
                        limit=limit,
                        truncated=truncated,
                    )

        return NeighborhoodPacket(
            focus=focus,
            edge_type=edge_type,
            packets=packets,
            limit=limit,
            truncated=truncated,
        )
