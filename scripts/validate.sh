#!/usr/bin/env bash
# validate.sh -- valida YAMLs em areas/ contra schemas/atende.v1.json
# Uso: validate.sh [arquivo.yaml]  (sem argumento valida todos)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCHEMA="${REPO_DIR}/schemas/atende.v1.json"

if [[ ! -f "${SCHEMA}" ]]; then
  echo "ERRO: Schema nao encontrado: ${SCHEMA}"
  exit 1
fi

if command -v ajv >/dev/null 2>&1; then
  VALIDATOR="ajv"
elif command -v python3 >/dev/null 2>&1; then
  if python3 -c "import jsonschema, yaml" 2>/dev/null; then
    VALIDATOR="python"
  else
    echo "AVISO: pip install jsonschema pyyaml   (ou npm install -g ajv-cli)"
    exit 1
  fi
else
  echo "ERRO: Instale ajv (npm) ou python3+jsonschema+pyyaml"
  exit 1
fi

validate_file() {
  local yaml_file="$1"
  local name
  name="$(basename "${yaml_file}")"

  if [[ "${VALIDATOR}" == "ajv" ]]; then
    if ajv validate --spec=draft2020 -s "${SCHEMA}" -d "${yaml_file}" --strict=false 2>&1; then
      echo "  [OK] ${name}"; return 0
    else
      echo "  [FAIL] ${name}"; return 1
    fi
  else
    # caminhos vao por argv (heredoc com aspas): aspas/espacos no nome nao quebram o Python
    if python3 - "${SCHEMA}" "${yaml_file}" "${name}" <<'PYEOF'
import sys, json, yaml
from jsonschema import Draft202012Validator
schema_path, yaml_path, name = sys.argv[1:4]
with open(schema_path) as s: schema = json.load(s)
with open(yaml_path) as y: data = yaml.safe_load(y)
errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.absolute_path))
if not errors:
    print('  [OK] ' + name)
    sys.exit(0)
print('  [FAIL] ' + name)
for e in errors[:5]:
    print('    Path: ' + '.'.join(str(p) for p in e.absolute_path))
    print('    Erro: ' + e.message)
sys.exit(1)
PYEOF
    then
      return 0
    else
      return 1
    fi
  fi
}

failed=0
total=0

if [[ $# -gt 0 ]]; then
  for f in "$@"; do
    total=$((total + 1))
    validate_file "${f}" || failed=$((failed + 1))
  done
else
  for f in "${REPO_DIR}"/areas/*.yaml; do
    total=$((total + 1))
    validate_file "${f}" || failed=$((failed + 1))
  done
fi

echo
if [[ ${failed} -eq 0 ]]; then
  echo "[OK] ${total}/${total} YAMLs validados."
else
  echo "[ERRO] ${failed}/${total} YAMLs com erro."
  exit 1
fi
