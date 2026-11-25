"""Audit logger — registra cada execucao do engine.

Estrategia hibrida:
  1. Se tabela BQ `REPLACE_AUDIT_PROJECT.atende_audit.executions` existir → grava la via
     `bq insert` (gcloud bq CLI). Mais robusto.
  2. Fallback: append em `~/atende-ai/audit-local.jsonl` (linha por execucao).
     Periodicamente faca upload em batch via `bq load`.

Sem dependencias externas — pure Python + subprocess.
"""

from __future__ import annotations
import hashlib
import json
import os
import shutil
import subprocess
import uuid
import warnings
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Caminho do log local (fallback)
DEFAULT_LOCAL_LOG = Path.home() / "atende-ai" / "audit-local.jsonl"

# Tabela BQ alvo -- substitua pelo seu projeto de auditoria
DEFAULT_BQ_TABLE = "REPLACE_AUDIT_PROJECT.atende_audit.executions"


@dataclass
class AuditEvent:
    """Uma execucao do engine."""
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    area: str = ""
    type_id: int | None = None
    operator_email: str = ""
    requester_id: str = ""
    tool_name: str = ""
    payload_hash: str = ""
    approved_at: str | None = None
    sent_at: str | None = None
    result_status: str = "pending"   # pending | success | partial | failed
    result_message: str = ""
    source_id: str = ""              # identificador do thread no canal (Chat, Gmail, WhatsApp)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, default=str)


def _hash_payload(payload: Any) -> str:
    """SHA256 do payload (ja com PII redacted).

    None → "" (sem payload registravel).
    {} ou "" → hash do JSON correspondente (distingue de None).
    """
    if payload is None:
        return ""
    if isinstance(payload, str):
        data = payload.encode("utf-8")
    else:
        data = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _bq_table_exists(table: str = DEFAULT_BQ_TABLE) -> bool:
    """Verifica se a tabela BQ existe via `bq show`. Retorna False se bq nao disponivel."""
    if not shutil.which("bq"):
        return False
    try:
        result = subprocess.run(
            ["bq", "show", "--format=none", table],
            capture_output=True, timeout=5,
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _bq_insert(event: AuditEvent, table: str = DEFAULT_BQ_TABLE) -> bool:
    """Insere via `bq insert`. Retorna True se sucesso."""
    if not shutil.which("bq"):
        return False
    try:
        proc = subprocess.run(
            ["bq", "insert", table],
            input=event.to_json(),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def _local_append(event: AuditEvent, log_path: Path = DEFAULT_LOCAL_LOG) -> bool:
    """Append em audit-local.jsonl."""
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")
        return True
    except OSError as e:
        print(f"[audit_logger] FALHA no log local: {e}")
        return False


def log_execution(
    *,
    area: str,
    type_id: int,
    operator_email: str,
    tool_name: str,
    payload: Any = None,
    requester_id: str = "",
    source_id: str = "",
    thread_url: str = "",            # DEPRECATED: use source_id (mantido por compatibilidade)
    approved_at: str | None = None,
    sent_at: str | None = None,
    result_status: str = "success",
    result_message: str = "",
    prefer_bq: bool = True,
    bq_table: str = DEFAULT_BQ_TABLE,
    local_log_path: Path = DEFAULT_LOCAL_LOG,
) -> AuditEvent:
    """Registra uma execucao. Sempre retorna o evento criado.

    Comportamento:
      - Se prefer_bq=True e tabela BQ existe → tenta inserir la. Se falhar, cai pro local.
      - Sempre escreve em local-jsonl (mesmo apos sucesso BQ, para redundancia).
      - NAO lanca excecao: quando esta funcao roda a operacao ja foi executada, e
        uma excecao aqui so esconderia o resultado do operador. A garantia de
        "falhar cedo sem auditoria" e de `check_audit_available()`, que o engine
        chama no Passo 0, ANTES de qualquer execucao.

    Args:
        area: nome da area (ex: 'helpdesk-saas')
        type_id: ID do tipo no YAML
        operator_email: e-mail do operador (runtime)
        tool_name: MCP/tool chamada
        payload: payload da operacao — sera hashed (NAO armazenado em claro)
        requester_id: User ID do solicitante (ex: 'users/...')
        source_id: identificador do thread no canal (spaces/.../threads/..., thread_id do Gmail, msg_id)
        thread_url: DEPRECATED — alias de source_id
        approved_at: timestamp ISO da Pausa 2
        sent_at: timestamp ISO da Pausa 3
        result_status: success | partial | failed | pending
        result_message: mensagem curta (sem PII)
        prefer_bq: se False, so grava local

    Returns:
        AuditEvent registrado.
    """
    if thread_url:
        warnings.warn("log_execution(thread_url=...) esta obsoleto; use source_id=",
                      DeprecationWarning, stacklevel=2)
    event = AuditEvent(
        area=area,
        type_id=type_id,
        operator_email=operator_email,
        requester_id=requester_id,
        tool_name=tool_name,
        payload_hash=_hash_payload(payload),
        approved_at=approved_at,
        sent_at=sent_at,
        result_status=result_status,
        result_message=result_message,
        source_id=source_id or thread_url,
    )

    # Sempre tenta local primeiro (rapido, sem rede)
    _local_append(event, local_log_path)

    # Best-effort BQ
    if prefer_bq and _bq_table_exists(bq_table):
        if not _bq_insert(event, bq_table):
            # nao lanca (a operacao ja rodou), mas a falha precisa ficar visivel
            print(f"[audit_logger] FALHA ao inserir no BigQuery ({bq_table}); "
                  f"evento {event.execution_id} ficou so no log local")

    return event


def check_audit_available(
    prefer_bq: bool = True,
    bq_table: str = DEFAULT_BQ_TABLE,
    local_log_path: Path = DEFAULT_LOCAL_LOG,
) -> tuple[bool, str]:
    """Confere, ANTES de executar qualquer operacao, se ha onde gravar a auditoria.

    Retorna (ok, destino_ou_motivo). O engine para no Passo 0 se ok=False —
    invariante "sem audit, falha cedo". Nao escreve no log (pode criar o diretorio pai).
    """
    if prefer_bq and _bq_table_exists(bq_table):
        return True, f"bigquery:{bq_table}"
    try:
        local_log_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return False, f"nao foi possivel criar {local_log_path.parent}: {e}"
    target = local_log_path if local_log_path.exists() else local_log_path.parent
    if os.access(target, os.W_OK):
        return True, f"local:{local_log_path}"
    return False, f"sem permissao de escrita em {target}"


def tail_local_log(n: int = 50, area: str | None = None, log_path: Path = DEFAULT_LOCAL_LOG) -> list[dict]:
    """Retorna as ultimas N execucoes do log local. Util para `/atende-refinar`."""
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    if area:
        lines = [ln for ln in lines if f'"area": "{area}"' in ln or f'"area":"{area}"' in ln]
    out = []
    for ln in lines[-n:]:
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if "thread_url" in row:  # linha gravada antes da troca para source_id
            row.setdefault("source_id", row.pop("thread_url"))
        out.append(row)
    return out
