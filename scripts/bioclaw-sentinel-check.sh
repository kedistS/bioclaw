#!/usr/bin/env bash
set -euo pipefail

containers=(
  bioclaw-conductor
  bioclaw-assistant-oc
  bioclaw-reasoner-oc
)

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

run_check() {
  local container="$1"
  docker exec -i "$container" python3 - <<'PY'
import sys

sys.path.insert(0, "/PeTTa/repos/OmegaClaw-Core/src")
import biokg

checks = [
    ("IMPACT|enhancer", biokg.pln_schema_neighbor_aggregate_pipe("IMPACT|enhancer")),
    ("TP53|disease", biokg.pln_schema_neighbor_aggregate_pipe("TP53|disease")),
    ("BRCA1|enables|zinc ion binding", biokg.provenance("BRCA1|enables|zinc ion binding")),
]

for label, result in checks:
    print(f"{label} => {result}")
PY
}

echo "BioClaw sentinel check: comparing conductor, AssistantOC, and ReasonerOC"

for container in "${containers[@]}"; do
  echo
  echo "== $container =="
  run_check "$container" | tee "$tmpdir/$container.out"
done

require_contains() {
  local file="$1"
  local needle="$2"
  if ! grep -Fq "$needle" "$file"; then
    echo "FAIL: expected '$needle' in $(basename "$file")" >&2
    exit 1
  fi
}

for container in "${containers[@]}"; do
  file="$tmpdir/$container.out"
  require_contains "$file" "IMPACT|enhancer =>"
  require_contains "$file" "Enhancer Atlas"
  require_contains "$file" "PEREGRINE"
  require_contains "$file" "TP53|disease =>"
  require_contains "$file" "Human Phenotype Ontology"
  require_contains "$file" "is_implicated_in"
  require_contains "$file" "BRCA1|enables|zinc ion binding =>"
  require_contains "$file" "GOA"
  require_contains "$file" "IEA"
done

reference="${containers[0]}"
for container in "${containers[@]:1}"; do
  if ! diff -u "$tmpdir/$reference.out" "$tmpdir/$container.out"; then
    echo "FAIL: sentinel outputs differ between $reference and $container" >&2
    exit 1
  fi
done

echo
echo "PASS: all BioClaw sentinel outputs match across containers."
