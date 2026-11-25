#!/usr/bin/env bash
# install.sh — symlinka engine/* para ~/.claude/commands/ e ~/.claude/agents/
# Idempotente: roda múltiplas vezes sem efeito colateral.
# Uso: install.sh [--force]
#   --force  repõe links que hoje apontam para OUTRO repositório (ex.: um fork interno)

set -euo pipefail

FORCE=0
for arg in "$@"; do
  case "${arg}" in
    --force) FORCE=1 ;;
    *) echo "Uso: $0 [--force]"; exit 64 ;;
  esac
done

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"   # -P: caminho fisico
AI_CLI_COMMANDS="${HOME}/.claude/commands"
AI_CLI_AGENTS="${HOME}/.claude/agents"

mkdir -p "${AI_CLI_COMMANDS}" "${AI_CLI_AGENTS}"

echo "Instalando atende-AI a partir de: ${REPO_DIR}"
echo

target_for() {
  # atende-classifier.md vai para agents/, demais para commands/
  if [[ "$(basename "$1")" == "atende-classifier.md" ]]; then
    echo "${AI_CLI_AGENTS}/$(basename "$1")"
  else
    echo "${AI_CLI_COMMANDS}/$(basename "$1")"
  fi
}

# Mesmo destino fisico? (repo acessado por um caminho com symlink nao e conflito)
same_target() { [[ "$(readlink -f "$1")" == "$(readlink -f "$2")" ]]; }

# 1ª passada: sem --force, qualquer link apontando para outro repo aborta
# ANTES de alterar qualquer coisa (evita instalacao pela metade).
conflicts=0
for f in "${REPO_DIR}"/engine/atende*.md; do
  target="$(target_for "$f")"
  if [[ -L "${target}" ]] && ! same_target "${target}" "$f"; then
    echo "  [CONFLITO] ${target} aponta para $(readlink "${target}")"
    conflicts=$((conflicts + 1))
  fi
done
if [[ ${conflicts} -gt 0 && ${FORCE} -eq 0 ]]; then
  echo
  echo "[ATENCAO] ${conflicts} comando(s) ja instalados a partir de outro repositorio."
  echo "  Nada foi alterado. Para usar este repo: bash $0 --force"
  echo "  (os links antigos sao substituidos; o outro repositorio nao e tocado)"
  exit 2
fi

for f in "${REPO_DIR}"/engine/atende*.md; do
  target="$(target_for "$f")"

  if [[ -L "${target}" ]]; then
    current="$(readlink "${target}")"
    if same_target "${target}" "$f"; then
      echo "  [skip] ${target} (ja aponta para este repo)"
    else
      ln -sfn "$f" "${target}"
      echo "  [relink] ${target} -> $f (antes: ${current})"
    fi
  elif [[ -e "${target}" ]]; then
    backup="${target}.bak"
    [[ -e "${backup}" ]] && backup="${target}.bak.$(date +%Y%m%d%H%M%S)"   # nunca sobrescreve backup anterior
    echo "  [WARN] ${target} ja existe e NAO e symlink. Backup em ${backup}"
    mv "${target}" "${backup}"
    ln -s "$f" "${target}"
    echo "  [link] ${target} -> $f"
  else
    ln -s "$f" "${target}"
    echo "  [link] ${target} -> $f"
  fi
done

echo
echo "[OK] Instalacao concluida."
echo
echo "Verifique com:"
echo "  ls -la ${AI_CLI_COMMANDS}/atende*.md"
echo "  ls -la ${AI_CLI_AGENTS}/atende*.md"
echo
echo "Proximo passo: validar YAMLs"
echo "  bash ${REPO_DIR}/scripts/validate.sh"
