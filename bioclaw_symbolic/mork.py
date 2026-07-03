from __future__ import annotations

import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from .evidence import EntityRef, EvidencePacket, NeighborhoodPacket, edge_atom
from .schema import SchemaRegistry


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

    @staticmethod
    def _parse_annotation_rows(rows: list[str], tag: str) -> list[tuple[str, str]]:
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

    def observed_annotations(self, expression: str, sample_values: int = 3) -> dict[str, dict[str, Any]]:
        tag = "bioclaw_observed_annotation"
        rows = self.export(self._wrap(f"($annotation {expression} $value)"), f"({tag} $annotation $value)")
        observed: dict[str, dict[str, Any]] = {}
        for annotation, value in self._parse_annotation_rows(rows, tag):
            entry = observed.setdefault(annotation, {"count": 0, "sample_values": []})
            entry["count"] += 1
            if len(entry["sample_values"]) < sample_values and value not in entry["sample_values"]:
                entry["sample_values"].append(value)
        return observed

    def observed_neighborhood_annotations(
        self,
        neighborhood: NeighborhoodPacket,
        sample_values: int = 3,
    ) -> dict[str, dict[str, Any]]:
        observed: dict[str, dict[str, Any]] = {}
        for packet in neighborhood.packets:
            for annotation, entry in self.observed_annotations(packet.edge_atom, sample_values).items():
                aggregate = observed.setdefault(annotation, {"edge_count": 0, "value_count": 0, "sample_values": []})
                aggregate["edge_count"] += 1
                aggregate["value_count"] += entry["count"]
                for value in entry["sample_values"]:
                    if len(aggregate["sample_values"]) < sample_values and value not in aggregate["sample_values"]:
                        aggregate["sample_values"].append(value)
        return observed

    def entity_annotation_values(self, entity: EntityRef, annotation: str) -> list[str]:
        return self.annotation_values(entity.atom(), annotation)

    def entity_details(self, entity: EntityRef, schema: SchemaRegistry) -> dict[str, Any]:
        node = schema.node_by_label(entity.label)
        if node is None:
            return {}

        details: dict[str, Any] = {"schema_node": node.name, "properties": {}}
        for prop in node.detail_properties():
            values = self.entity_annotation_values(entity, prop.name)
            if not values:
                continue
            details["properties"][prop.name] = {
                "values": values,
                "role": prop.role,
                "schema_type": prop.schema_type,
                "biolink": prop.biolink,
            }
        if not details["properties"]:
            return {}
        return details

    def enrich_packet_nodes(self, packet: EvidencePacket, schema: SchemaRegistry) -> EvidencePacket:
        return packet.with_node_details(
            source_details=self.entity_details(packet.source, schema),
            target_details=self.entity_details(packet.target, schema),
        )

    def enrich_neighborhood_nodes(self, neighborhood: NeighborhoodPacket, schema: SchemaRegistry) -> NeighborhoodPacket:
        return neighborhood.with_packets([
            self.enrich_packet_nodes(packet, schema)
            for packet in neighborhood.packets
        ])

    def evidence_packet(
        self,
        edge_type: str,
        source: EntityRef,
        target: EntityRef,
        annotations: list[str] | None = None,
        annotation_roles: dict[str, str] | None = None,
    ) -> EvidencePacket:
        expression = edge_atom(edge_type, source.label, source.identifier, target.label, target.identifier)
        exists = self.atom_exists(expression)
        packet_annotations: dict[str, list[str]] = {}
        for annotation in annotations or []:
            values = self.annotation_values(expression, annotation)
            if values:
                packet_annotations[annotation] = values
        return EvidencePacket(
            edge_type=edge_type,
            source=source,
            target=target,
            exists=exists,
            annotations=packet_annotations,
            annotation_roles=annotation_roles or {},
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
        annotation_roles: dict[str, str] | None = None,
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
                    packet = self.evidence_packet(edge_type, focus, other, annotations, annotation_roles)
                else:
                    packet = self.evidence_packet(edge_type, other, focus, annotations, annotation_roles)
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
