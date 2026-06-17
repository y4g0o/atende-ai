#!/usr/bin/env bash
# install.sh — symlinka engine/* para ~/.claude/commands/ e ~/.claude/agents/
# Idempotente: roda múltiplas vezes sem efeito colateral.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AI_CLI_COMMANDS="${HOME}/.claude/commands"
AI_CLI_AGENTS="${HOME}/.claude/agents"

mkdir -p "${AI_CLI_COMMANDS}" "${AI_CLI_AGENTS}"

echo "Instalando atende-AI a partir de: ${REPO_DIR}"
echo

# Skills (slash commands)
for f in "${REPO_DIR}"/engine/atende*.md; do
  basename_file="$(basename "$f")"
  # atende-classifier.md vai para agents/, demais para commands/
  if [[ "${basename_file}" == "atende-classifier.md" ]]; then
    target="${AI_CLI_AGENTS}/${basename_file}"
  else
    target="${AI_CLI_COMMANDS}/${basename_file}"
  fi

  if [[ -L "${target}" ]]; then
    echo "  [skip] ${target} (ja e symlink)"
  elif [[ -e "${target}" ]]; then
    echo "  [WARN] ${target} ja existe e NAO e symlink. Backup em ${target}.bak"
    mv "${target}" "${target}.bak"
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
