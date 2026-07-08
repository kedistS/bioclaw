from __future__ import annotations

import json
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evidence import EvidencePacket
from .reasoning import SymbolicAssessment, packet_assessment


@dataclass(frozen=True)
class OmegaClawSpikeResult:
    payload: dict[str, Any]
    metta_program: str


def _metta_string(value: str) -> str:
    return json.dumps(str(value))


def _safe_claim_id(value: str) -> str:
    chars = [ch if ch.isalnum() else "_" for ch in value]
    collapsed = "".join(chars).strip("_")
    return collapsed or "claim"


def _numeric_stvs(packet: EvidencePacket) -> list[tuple[float, float]]:
    values: list[tuple[float, float]] = []
    raw_values = packet.values_by_role("score", "confidence")
    for raw in raw_values:
        try:
            value = max(0.0, min(1.0, float(raw)))
        except ValueError:
            continue
        values.append((value, value))
    return values


def _atom_lines(packet: EvidencePacket, assessment: SymbolicAssessment, claim_id: str) -> list[str]:
    lines = [
        f"(bioclaw_claim {claim_id} {packet.edge_atom})",
        f"(bioclaw_stv {claim_id} (stv {assessment.stv[0]:.6f} {assessment.stv[1]:.6f}))",
    ]
    for label in assessment.labels:
        lines.append(f"(bioclaw_label {claim_id} {_metta_string(label)})")
    for name, values in sorted(packet.annotations.items()):
        role = packet.annotation_roles.get(name, "unclassified")
        for value in values:
            lines.append(
                f"(bioclaw_annotation {claim_id} {_metta_string(name)} "
                f"{_metta_string(role)} {_metta_string(value)})"
            )
    return lines


def _candidate_pln_queries(packet: EvidencePacket, claim_id: str) -> list[str]:
    stvs = _numeric_stvs(packet)
    if len(stvs) < 2:
        return []
    term = packet.edge_atom
    left = f"({term} (stv {stvs[0][0]:.6f} {stvs[0][1]:.6f}))"
    right = f"({term} (stv {stvs[1][0]:.6f} {stvs[1][1]:.6f}))"
    return [
        f"; PLN revision candidate for {claim_id}: two comparable score/confidence values were observed.",
        f"!(|~pln {left} {right})",
    ]


def metta_program_for_packet(
    packet: EvidencePacket,
    assessment: SymbolicAssessment,
    claim_id: str,
) -> str:
    lines = [
        "; BioClaw Phase 2 symbolic substrate spike payload.",
        "; Load inside an OmegaClaw/Hyperon runtime where lib_pln/lib_nal are available.",
        "!(import! &self (library OmegaClaw-Core lib_pln))",
        "!(import! &self (library OmegaClaw-Core lib_nal))",
        "",
        "; Grounded MORK BioAtomspace evidence packet.",
        *_atom_lines(packet, assessment, claim_id),
        "",
    ]
    queries = _candidate_pln_queries(packet, claim_id)
    if queries:
        lines.extend(queries)
    else:
        lines.extend(
            [
                "; No PLN revision query generated for this packet.",
                "; Reason: fewer than two comparable score/confidence values were present.",
            ]
        )
    return "\n".join(lines) + "\n"


def _engine_status(
    program: str,
    invoke_engine: bool,
    engine_command: str,
    timeout: int,
) -> dict[str, Any]:
    if not invoke_engine:
        return {
            "attempted": False,
            "available": None,
            "status": "not_requested",
            "reason": "Use --invoke-engine to try the local OmegaClaw/MeTTa runtime.",
        }

    parts = shlex.split(engine_command)
    if not parts:
        return {
            "attempted": False,
            "available": False,
            "status": "invalid_engine_command",
            "reason": "The engine command was empty.",
        }
    if shutil.which(parts[0]) is None:
        return {
            "attempted": False,
            "available": False,
            "status": "engine_unavailable",
            "reason": f"Executable {parts[0]!r} was not found on PATH.",
            "engine_command": engine_command,
        }

    with tempfile.NamedTemporaryFile("w", suffix=".metta", delete=False) as handle:
        handle.write(program)
        path = Path(handle.name)
    try:
        completed = subprocess.run(
            [*parts, str(path)],
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "attempted": True,
            "available": True,
            "status": "completed" if completed.returncode == 0 else "failed",
            "engine_command": engine_command,
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "attempted": True,
            "available": True,
            "status": "timeout",
            "engine_command": engine_command,
            "timeout_seconds": timeout,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }
    finally:
        path.unlink(missing_ok=True)


def omega_spike_payload(
    packet: EvidencePacket,
    policy: dict[str, Any],
    *,
    claim_id: str | None = None,
    invoke_engine: bool = False,
    engine_command: str = "metta",
    timeout: int = 30,
) -> OmegaClawSpikeResult:
    assessment = packet_assessment(packet, policy)
    resolved_claim_id = claim_id or f"claim_{_safe_claim_id(packet.edge_type)}_{packet.source.identifier}_{packet.target.identifier}"
    program = metta_program_for_packet(packet, assessment, resolved_claim_id)
    payload = {
        "phase": "phase_2_real_symbolic_substrate_spike",
        "scope": "one bounded MORK evidence packet",
        "packet": packet.to_dict(),
        "packet_local_assessment": assessment.to_dict(),
        "omega_payload": {
            "claim_id": resolved_claim_id,
            "metta_program": program,
            "candidate_pln_queries": _candidate_pln_queries(packet, resolved_claim_id),
            "notes": [
                "This payload is grounded in the extracted MORK packet.",
                "The packet-local assessment remains an interim Python heuristic unless engine.status is completed.",
            ],
        },
        "engine": _engine_status(program, invoke_engine, engine_command, timeout),
    }
    return OmegaClawSpikeResult(payload=payload, metta_program=program)
