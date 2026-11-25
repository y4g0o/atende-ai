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
  # "meu-projeto-dados-000001"
  # "meu-projeto-ops-000002"
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

# Padroes REAIS ficam fora do git: um por linha em .pii-patterns.local
# (ou no arquivo apontado por PII_PATTERNS_FILE). Linhas vazias e "#" sao ignoradas.
# O arquivo e gitignored — assim o proprio lint nao publica o que deveria esconder.
PATTERNS_FILE="${PII_PATTERNS_FILE:-${REPO_DIR}/.pii-patterns.local}"
if [[ -f "${PATTERNS_FILE}" ]]; then
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"                       # tolera arquivo salvo com CRLF
    line="${line#"${line%%[![:space:]]*}"}"     # remove espacos no inicio
    line="${line%"${line##*[![:space:]]}"}"     # e no fim
    [[ -z "${line}" || "${line}" =~ ^[[:space:]]*# ]] && continue
    FORBIDDEN_PATTERNS+=("${line}")
  done < "${PATTERNS_FILE}"
fi

# Regex invalida nao pode virar "OK" silencioso
active=0
for pattern in "${FORBIDDEN_PATTERNS[@]+"${FORBIDDEN_PATTERNS[@]}"}"; do
  [[ -z "${pattern}" || "${pattern}" =~ ^# ]] && continue
  rc=0; grep -qiE -e "${pattern}" /dev/null 2>/dev/null || rc=$?
  if [[ ${rc} -ge 2 ]]; then
    echo "[ERRO] Regex invalida em ${PATTERNS_FILE}: ${pattern}"
    exit 2
  fi
  active=$((active + 1))
done
if [[ ${active} -eq 0 ]]; then
  echo "[AVISO] Nenhum padrao proibido configurado — este lint NAO verificou PII da sua org."
  echo "        Crie ${PATTERNS_FILE} (um regex por linha) antes de publicar."
  [[ "${PII_STRICT:-0}" == "1" ]] && exit 1
fi

# O que varrer: em repo git, tudo que pode ir para o push (rastreado + novo nao
# ignorado, de QUALQUER extensao) e tambem o historico e as mensagens de commit.
# Fora de git: todos os arquivos do diretorio.
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
FILES="${WORK}/files"
HISTORY=""
TARGET_ABS="$(cd "${TARGET}" && pwd -P)"
if git -C "${TARGET_ABS}" rev-parse --show-toplevel >/dev/null 2>&1 \
   && [[ "$(cd "$(git -C "${TARGET_ABS}" rev-parse --show-toplevel)" && pwd -P)" == "${TARGET_ABS}" ]]; then
  (cd "${TARGET_ABS}" && git ls-files -z -co --exclude-standard) > "${FILES}"
  HISTORY="${WORK}/history"
  git -C "${TARGET_ABS}" log --all -p --format='commit %H%n%an <%ae>%n%B' > "${HISTORY}" 2>/dev/null || true
else
  (cd "${TARGET_ABS}" && find . -type f -not -path './.git/*' -print0) > "${FILES}"
fi

found=0
for pattern in "${FORBIDDEN_PATTERNS[@]+"${FORBIDDEN_PATTERNS[@]}"}"; do
  [[ -z "${pattern}" || "${pattern}" =~ ^# ]] && continue

  matches=$(cd "${TARGET_ABS}" && xargs -0 -r grep -naiE -e "${pattern}" -- < "${FILES}" 2>/dev/null \
    | grep -av '^\(\./\)\?\.pii-patterns\.local:' || true)
  if [[ -n "${HISTORY}" ]]; then
    hist=$(grep -niE -e "${pattern}" -- "${HISTORY}" 2>/dev/null || true)
    [[ -n "${hist}" ]] && matches="${matches}${matches:+$'\n'}[historico git] $(echo "${hist}" | head -3)"
  fi

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
  echo "[OK] Nenhum token proibido encontrado (${active} padrao(es) verificados)."
else
  echo "[ERRO] ${found} padrao(es) proibido(s) encontrado(s). Corrija antes de compartilhar."
  exit 1
fi
