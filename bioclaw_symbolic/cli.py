from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from .evidence import EntityRef
from .mork import MorkClient
from .reasoning import load_policy, packet_assessment
from .schema import SchemaRegistry


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=True))


def cmd_schema(args: argparse.Namespace) -> int:
    registry = SchemaRegistry.from_file(args.schema)
    if args.summary:
        _print_json(registry.summary())
    elif args.label:
        _print_json([edge.to_dict() for edge in registry.by_label(args.label)])
    else:
        _print_json({"summary": registry.summary(), "edges": [edge.to_dict() for edge in registry.edges]})
    return 0


def cmd_edge(args: argparse.Namespace) -> int:
    client = MorkClient(base_url=args.mork, namespace=args.namespace, timeout=args.timeout)
    packet = client.evidence_packet(
        edge_type=args.edge,
        source=EntityRef.parse(args.source),
        target=EntityRef.parse(args.target),
    )
    data: dict[str, Any] = {"packet": packet.to_dict(), "summary": packet.short_summary()}
    if args.reason:
        policy = load_policy(args.reasoning)
        data["assessment"] = packet_assessment(packet, policy).to_dict()
    _print_json(data)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bioclaw-symbolic")
    sub = parser.add_subparsers(dest="command", required=True)

    schema = sub.add_parser("schema", help="inspect BioCypher schema capabilities")
    schema.add_argument("--schema", required=True, help="BioCypher schema YAML")
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
    edge.add_argument("--reason", action="store_true", help="add bounded symbolic assessment")
    edge.add_argument("--reasoning", default="config/reasoning.yaml", help="reasoning policy YAML")
    edge.set_defaults(func=cmd_edge)

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
