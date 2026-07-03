from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

from .evidence import EntityRef
from .mork import MorkClient
from .reasoning import load_policy, neighborhood_assessment, packet_assessment
from .schema import SchemaRegistry

DEFAULT_SCHEMA_POLICY = "config/schema_roles.yaml"


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def _packet_assessments_by_edge(neighborhood, policy: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if policy is None:
        return {}
    return {
        packet.edge_atom: packet_assessment(packet, policy).to_dict()
        for packet in neighborhood.packets
    }


def _write_neighborhood_export(
    path: str,
    export_format: str,
    neighborhood,
    assessment_by_edge: dict[str, dict[str, Any]],
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    if export_format == "json":
        target.write_text(
            json.dumps(
                {
                    "neighborhood": neighborhood.to_dict(),
                    "packet_assessments": assessment_by_edge,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        return

    if export_format == "jsonl":
        with target.open("w") as handle:
            for packet in neighborhood.packets:
                row = packet.to_dict()
                if packet.edge_atom in assessment_by_edge:
                    row["assessment"] = assessment_by_edge[packet.edge_atom]
                handle.write(json.dumps(row, sort_keys=True) + "\n")
        return

    if export_format == "csv":
        with target.open("w", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "edge",
                    "edge_type",
                    "source_label",
                    "source_id",
                    "source_name",
                    "target_label",
                    "target_id",
                    "target_name",
                    "sources",
                    "scores",
                    "evidence",
                    "references",
                    "context",
                    "labels",
                    "strength",
                    "confidence",
                ],
            )
            writer.writeheader()
            for packet in neighborhood.packets:
                packet_dict = packet.to_dict()
                assessment = assessment_by_edge.get(packet.edge_atom, {})
                stv = assessment.get("stv", {})
                writer.writerow(
                    {
                        "edge": packet.edge_atom,
                        "edge_type": packet.edge_type,
                        "source_label": packet.source.label,
                        "source_id": packet.source.identifier,
                        "source_name": packet_dict["source"].get("name", ""),
                        "target_label": packet.target.label,
                        "target_id": packet.target.identifier,
                        "target_name": packet_dict["target"].get("name", ""),
                        "sources": "|".join(packet.values("source", "data_source", "knowledge_source")),
                        "scores": "|".join(packet.values("score", "edge_score", "confidence", "edge_confidence")),
                        "evidence": "|".join(packet.values("evidence", "evidence_code", "evidence_code_name")),
                        "references": "|".join(packet.values("reference", "references", "db_reference", "pubmed_references", "source_url")),
                        "context": "|".join(packet.values("biological_context", "interaction_context", "interaction_type", "reactome_pathway")),
                        "labels": "|".join(assessment.get("labels", [])),
                        "strength": stv.get("strength", ""),
                        "confidence": stv.get("confidence", ""),
                    }
                )
        return

    raise ValueError(f"unknown export format {export_format!r}")


def cmd_schema(args: argparse.Namespace) -> int:
    registry = SchemaRegistry.from_file(args.schema, args.schema_policy)
    if args.summary:
        _print_json(registry.summary())
    elif args.label:
        _print_json([edge.to_dict() for edge in registry.by_label(args.label)])
    else:
        _print_json({"summary": registry.summary(), "edges": [edge.to_dict() for edge in registry.edges]})
    return 0


def cmd_edge(args: argparse.Namespace) -> int:
    client = MorkClient(base_url=args.mork, namespace=args.namespace, timeout=args.timeout)
    registry = SchemaRegistry.from_file(args.schema, args.schema_policy) if args.schema else None
    annotations = registry.edge_annotation_names(args.edge) if registry else []
    packet = client.evidence_packet(
        edge_type=args.edge,
        source=EntityRef.parse(args.source),
        target=EntityRef.parse(args.target),
        annotations=annotations,
    )
    if args.include_node_details:
        if registry is None:
            raise ValueError("--schema is required with --include-node-details")
        packet = client.enrich_packet_nodes(packet, registry)
    data: dict[str, Any] = {"packet": packet.to_dict(), "summary": packet.short_summary()}
    if args.reason:
        policy = load_policy(args.reasoning)
        data["assessment"] = packet_assessment(packet, policy).to_dict()
    _print_json(data)
    return 0


def cmd_neighborhood(args: argparse.Namespace) -> int:
    client = MorkClient(base_url=args.mork, namespace=args.namespace, timeout=args.timeout)
    registry = SchemaRegistry.from_file(args.schema, args.schema_policy) if args.schema else None
    if args.include_node_details and registry is None:
        raise ValueError("--schema is required with --include-node-details")
    annotations = registry.edge_annotation_names(args.edge) if registry else []
    retrieval_limit = args.max_total if args.max_total is not None else args.limit
    raw_neighborhood = client.neighborhood(
        edge_type=args.edge,
        focus=EntityRef.parse(args.entity),
        direction=args.direction,
        limit=retrieval_limit,
        annotations=annotations,
    )
    if registry is not None:
        raw_neighborhood = client.enrich_neighborhood_nodes(raw_neighborhood, registry)
    neighborhood = raw_neighborhood
    if args.only_multisource:
        neighborhood = raw_neighborhood.with_packets(raw_neighborhood.multi_source_packets())

    policy = load_policy(args.reasoning) if args.reason else None
    assessment_by_edge = _packet_assessments_by_edge(neighborhood, policy)
    data: dict[str, Any] = {
        "neighborhood": neighborhood.to_dict() if args.include_packets else {
            key: value
            for key, value in neighborhood.to_dict().items()
            if key != "packets"
        },
        "retrieval": {
            "candidate_edges": len(raw_neighborhood.packets),
            "returned_edges": len(neighborhood.packets),
            "limit": retrieval_limit,
            "truncated": raw_neighborhood.truncated,
            "only_multisource": args.only_multisource,
            "filter_scope": "within bounded retrieval result",
            "pagination": "bounded_export; native MORK cursor pagination is not used yet",
        },
        "summary": neighborhood.short_summary(),
    }
    if args.reason:
        data["assessment"] = neighborhood_assessment(neighborhood, policy)
    if args.export:
        _write_neighborhood_export(args.export, args.format, neighborhood, assessment_by_edge)
        data["export"] = {
            "path": args.export,
            "format": args.format,
            "edges": len(neighborhood.packets),
        }
    _print_json(data)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bioclaw-symbolic")
    sub = parser.add_subparsers(dest="command", required=True)

    schema = sub.add_parser("schema", help="inspect BioCypher schema capabilities")
    schema.add_argument("--schema", required=True, help="BioCypher schema YAML")
    schema.add_argument("--schema-policy", default=DEFAULT_SCHEMA_POLICY, help="schema role policy YAML")
    schema.add_argument("--label", help="optional edge label/name filter")
    schema.add_argument("--summary", action="store_true", help="print only schema capability counts")
    schema.set_defaults(func=cmd_schema)

    edge = sub.add_parser("edge", help="extract one exact-edge evidence packet from MORK")
    edge.add_argument("--mork", required=True, help="MORK base URL, e.g. http://localhost:8037")
    edge.add_argument("--namespace", default="annotation", help="MORK namespace wrapper, use '-' for none")
    edge.add_argument("--source", required=True, help="source entity as label:id")
    edge.add_argument("--edge", required=True, help="edge predicate, e.g. interacts_with")
    edge.add_argument("--target", required=True, help="target entity as label:id")
    edge.add_argument("--timeout", type=int, default=30)
    edge.add_argument("--schema", help="BioCypher schema YAML, required for --include-node-details")
    edge.add_argument("--schema-policy", default=DEFAULT_SCHEMA_POLICY, help="schema role policy YAML")
    edge.add_argument("--include-node-details", action="store_true", help="enrich source/target nodes using schema-selected node properties")
    edge.add_argument("--reason", action="store_true", help="add bounded symbolic assessment")
    edge.add_argument("--reasoning", default="config/reasoning.yaml", help="reasoning policy YAML")
    edge.set_defaults(func=cmd_edge)

    neighborhood = sub.add_parser("neighborhood", help="extract incident edge evidence packets from MORK")
    neighborhood.add_argument("--mork", required=True, help="MORK base URL, e.g. http://localhost:8037")
    neighborhood.add_argument("--namespace", default="annotation", help="MORK namespace wrapper, use '-' for none")
    neighborhood.add_argument("--entity", required=True, help="focus entity as label:id")
    neighborhood.add_argument("--edge", required=True, help="edge predicate, e.g. interacts_with")
    neighborhood.add_argument("--direction", choices=["incoming", "outgoing", "both"], default="both")
    neighborhood.add_argument("--limit", type=int, default=100, help="backward-compatible retrieval cap")
    neighborhood.add_argument("--max-total", type=int, help="maximum candidate edges to retrieve/process; overrides --limit")
    neighborhood.add_argument("--timeout", type=int, default=30)
    neighborhood.add_argument("--schema", help="BioCypher schema YAML, required for --include-node-details")
    neighborhood.add_argument("--schema-policy", default=DEFAULT_SCHEMA_POLICY, help="schema role policy YAML")
    neighborhood.add_argument("--include-node-details", action="store_true", help="enrich source/target nodes using schema-selected node properties")
    neighborhood.add_argument("--include-packets", action="store_true", help="include every edge packet in JSON output")
    neighborhood.add_argument("--only-multisource", action="store_true", help="return/export only edges with more than one source annotation")
    neighborhood.add_argument("--export", help="write returned neighborhood packets to a file")
    neighborhood.add_argument("--format", choices=["json", "jsonl", "csv"], default="json", help="export format")
    neighborhood.add_argument("--reason", action="store_true", help="add bounded symbolic neighborhood assessment")
    neighborhood.add_argument("--reasoning", default="config/reasoning.yaml", help="reasoning policy YAML")
    neighborhood.set_defaults(func=cmd_neighborhood)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
