#!/usr/bin/env bash
# check-no-pii.sh — lint anti-vazamento de dados sensiveis
# Verifica se o kit contem tokens proibidos antes de compartilhar.
# Uso: bash scripts/check-no-pii.sh [diretorio]  (default: raiz do repo)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET="${1:-${REPO_DIR}}"

# === ADICIONE AQUI OS TOKENS PROIBIDOS DA SUA ORGANIZACAO ===
# Exemplos abaixo sao placeholders — substitua pelos valores reais
# que NAO devem aparecer no kit compartilhado.
#
# Formato: "padrao_regex"
#
FORBIDDEN_PATTERNS=(
  # === Exemplos de padroes para adicionar (substitua pelos valores REAIS da sua org) ===
  #
  # E-mails pessoais
  # "nome\.sobrenome@suaorg\.com"
  #
  # User IDs reais do Google Chat (formato: users/ seguido de 15-21 digitos)
  # Adicione os IDs reais dos operadores, ex:
  # "users/100000000000000000001"   <- substitua pelo ID real
  #
  # Space IDs reais do Google Chat (obtenha da URL do canal)
  # "spaces/ID_DO_CANAL_PRODUCAO"
  # "spaces/ID_DO_CANAL_TESTE"
  #
  # Project IDs do GCP (formato: nome-digitos, ex: meu-projeto-123456)
  # "meu-lakehouse-000001"
  # "meu-services-000002"
  #
  # Bucket GCS (nome do bucket sem gs://)
  # "nome-do-seu-bucket"
  #
  # URLs internas (sem https://)
  # "admin\.suaorg\.com"
  #
  # Nomes proprios sensiveis (cuidado com falso-positivo)
  # "Nome Sobrenome Real"
)

found=0

for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
  # Pular comentarios (linhas que comecam com #)
  [[ "${pattern}" =~ ^# ]] && continue
  [[ -z "${pattern}" ]] && continue

  matches=$(grep -rniE "${pattern}" "${TARGET}" \
    --include="*.yaml" --include="*.md" --include="*.json" --include="*.py" --include="*.sh" \
    2>/dev/null || true)

  if [[ -n "${matches}" ]]; then
    echo "[FALHOU] Padrao encontrado: ${pattern}"
    echo "${matches}" | head -5
    echo
    found=$((found + 1))
  fi
done

# Sempre verificar: placeholders nao preenchidos
unfilled=$(grep -rniE "REPLACE_|YOUR_ORG_MCP|YOUR_HELPDESK_MCP|SEU-DOMINIO|REPLACE_PROJECT|REPLACE_SPACE" "${TARGET}" \
  --include="*.yaml" \
  2>/dev/null | grep -v "^Binary" || true)

if [[ -n "${unfilled}" ]]; then
  echo "[AVISO] Placeholders ainda nao preenchidos em YAMLs:"
  echo "${unfilled}" | head -20
  echo
  echo "  -> Preencha antes de usar em producao (nao e um erro de PII, e um lembrete)."
fi

echo
if [[ ${found} -eq 0 ]]; then
  echo "[OK] Nenhum token proibido encontrado."
  echo "     (Lembre de adicionar seus tokens reais na secao FORBIDDEN_PATTERNS deste script)"
else
  echo "[ERRO] ${found} padrao(es) proibido(s) encontrado(s). Corrija antes de compartilhar."
  exit 1
fi
