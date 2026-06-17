---
description: Sincroniza ~/atende-ai/ com o repositório git remoto
allowed-tools:
  - Bash
---

# `/atende-sync` — Sincronizar com repositório

Atualiza `~/atende-ai/` puxando mudanças do repositório remoto configurado.

> **Configurar remote:** antes do primeiro sync, configure o repositório:
> ```bash
> cd ~/atende-ai
> git init
> git remote add origin <URL_DO_SEU_REPOSITORIO>
> git push -u origin main
> ```

**O que faz:**
1. `git fetch` para ver se há atualizações
2. Se sim, mostra os commits que vão entrar
3. Pede confirmação se houver mudanças em arquivos críticos (`engine/`, `schemas/`, `globals.yaml`, `lib/`)
4. `git pull --ff-only` (rejeita merges complicados)
5. Mostra resumo do que mudou

---

## Execução

**1.** Verifique se há mudanças:
```bash
cd ~/atende-ai && git fetch --quiet
LOCAL=$(git rev-parse @)
REMOTE=$(git rev-parse @{u} 2>/dev/null || echo "no-upstream")
```

**2.** Se `REMOTE == "no-upstream"`:
> "⚠️ Branch sem upstream. Configure com: `git push -u origin main` antes do primeiro sync."

Parar.

**3.** Se `LOCAL == REMOTE`:
> "✅ Já atualizado."

Parar.

**4.** Senão, mostrar commits que vão entrar:
```bash
git log --oneline ${LOCAL}..${REMOTE}
git diff --stat ${LOCAL}..${REMOTE}
```

**5.** Se houver mudanças em **arquivos críticos** (`engine/`, `schemas/`, `globals.yaml`, `lib/pii_redactor.py`), avisar:
> "⚠️ Mudanças críticas detectadas em: {lista}. Confirma o pull? [s/n]"

Se outros arquivos (apenas `areas/`, `docs/`), seguir direto.

**6.** Executar pull:
```bash
cd ~/atende-ai && git pull --ff-only
```

**7.** Se mudou alguma área (`areas/*.yaml`), revalidar:
```bash
bash ~/atende-ai/scripts/validate.sh
```

Se falhar, **revertir** o pull (`git reset --hard ${LOCAL}`) e avisar — não deixar `~/atende-ai/` em estado inválido.

**8.** Se mudou `engine/*.md`, reinstalar symlinks:
```bash
bash ~/atende-ai/scripts/install.sh
```

---

## Regras

1. **Nunca fazer `git pull` com merge** — só fast-forward
2. **Nunca deixar `~/atende-ai/` em estado inválido** após sync
3. **Nunca silenciar mudanças em `engine/`** — sempre informar
