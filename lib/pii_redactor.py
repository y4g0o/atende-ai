"""PII Redactor — pipeline obrigatorio antes de qualquer chamada LLM externa.

Quando o engine analisa historico do canal para extrair padroes (/atende-criar Fase 2,
/atende-refinar aprendizado), DEVE passar texto por esta funcao antes de enviar para LLM externo.

Uso:
    from pii_redactor import redact, redact_batch
    result = redact("Oi Joao Silva, o codigo ABC1DEF precisa ser ativado.")
    print(result.redacted_text)   # "Oi [NOME], o codigo [CODE] precisa ser ativado."
    print(result.counts)          # {"[NOME]": 1, "[CODE]": 1}
"""

import re
from dataclasses import dataclass, field


# Ordem importa: identificadores estruturados (users/, spaces/, URLs, UUIDs)
# antes de telefone/CPF -- o regex de telefone come sequencias longas de digitos.
_PATTERNS = [
    # E-mails
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    # URLs do Google Chat (antes de URL generica)
    (re.compile(r"https?://chat\.google\.com/\S+"), "[CHAT_URL]"),
    # URLs do WhatsApp (wa.me e app links)
    (re.compile(r"https?://(?:wa\.me|api\.whatsapp\.com|web\.whatsapp\.com)/\S+"), "[WHATSAPP_URL]"),
    # User IDs do Google Chat (antes de telefone -- 15+ digitos)
    (re.compile(r"users/\d{15,}"), "[USER_ID]"),
    # spaces/ do Google Chat
    (re.compile(r"spaces/[A-Za-z0-9_-]+"), "[SPACE_ID]"),
    # URLs genericas
    (re.compile(r"https?://\S+"), "[URL]"),
    # UUIDs (antes de telefone/CPF)
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE), "[UUID]"),
    (re.compile(r"\b[0-9a-f]{56}\b", re.IGNORECASE), "[UUID]"),
    # Project IDs do GCP (padrao: palavra-digitos, ex: meu-projeto-123456, outro-projeto-654321)
    (re.compile(r"\b[a-z][a-z0-9-]+-\d{6,}\b"), "[GCP_PROJECT]"),
    # Bucket GCS
    (re.compile(r"gs://[A-Za-z0-9._/-]+"), "[GCS_BUCKET]"),
    # CPF formatado
    (re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"), "[CPF]"),
    # Telefones BR
    (re.compile(r"\+55\s*\(?\d{2}\)?\s*\d{4,5}-?\d{4}\b"), "[PHONE]"),
    (re.compile(r"\(?\d{2}\)?\s*9?\d{4}-?\d{4}\b"), "[PHONE]"),
    # CPF ou celular cru (11 digitos isolados)
    (re.compile(r"\b\d{11}\b"), "[CPF_OR_PHONE]"),
    # Numeros de pedido (adapte o padrao ao formato da sua org)
    (re.compile(r"#\d{4,}\b"), "[ORDER_ID]"),
    # Codigos alfanumericos de 7 chars (adapte ao padrao da sua org)
    (re.compile(r"\b[A-Z]{2,4}\d{1,3}[A-Z]{1,3}\b"), "[CODE]"),
    (re.compile(r"\b[A-Z0-9]{7}\b"), "[CODE_OR_ID]"),
    # CEP
    (re.compile(r"\b\d{5}-\d{3}\b"), "[CEP]"),
]


# Nomes proprios: heuristica simples -- 2+ palavras capitalizadas em sequencia,
# excluindo termos institucionais conhecidos.
_INSTITUTIONAL_TERMS = {
    "Google", "Chat", "MCP", "Shopify", "BigQuery", "BQ",
    "PDF", "QR", "Code", "Cloud", "Storage", "Function", "Functions",
    "Brasil", "Mexico", "Internacional",
    "Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo",
    "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
    "URL", "ID", "CPF", "NF", "CEP",
}

_NAME_PATTERN = re.compile(
    r"\b([A-ZÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ][a-záàâãäéèêëíìîïóòôõöúùûüçñ]{2,})"
    r"(?:\s+(?:de|da|do|dos|das|von|van|le|la)\s+|\s+)"
    r"([A-ZÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ][a-záàâãäéèêëíìîïóòôõöúùûüçñ]{2,}(?:\s+[A-ZÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ][a-záàâãäéèêëíìîïóòôõöúùûüçñ]+)*)"
)


@dataclass
class RedactionResult:
    """Resultado da redacao."""
    redacted_text: str
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(self.counts.values())


def redact(text: str) -> RedactionResult:
    """Remove PII de um texto.

    Retorna o texto com placeholders + contagem por categoria. Idempotente:
    aplicar em texto ja redacted nao muda nada.

    Args:
        text: texto bruto (mensagem de chamado, snippet do thread, etc.)

    Returns:
        RedactionResult com `redacted_text` e `counts` por placeholder.
    """
    if not text:
        return RedactionResult(redacted_text=text, counts={})

    counts: dict[str, int] = {}
    result = text

    # Aplicar regex patterns
    for pattern, placeholder in _PATTERNS:
        def _sub(m: re.Match, ph: str = placeholder) -> str:
            counts[ph] = counts.get(ph, 0) + 1
            return ph
        result = pattern.sub(_sub, result)

    # Nomes proprios (ultimo -- depois de tudo)
    def _sub_name(m: re.Match) -> str:
        candidate = m.group(0)
        words = candidate.split()
        if any(w in _INSTITUTIONAL_TERMS for w in words):
            return candidate
        counts["[NOME]"] = counts.get("[NOME]", 0) + 1
        return "[NOME]"

    result = _NAME_PATTERN.sub(_sub_name, result)

    return RedactionResult(redacted_text=result, counts=counts)


def redact_batch(texts: list[str]) -> list[RedactionResult]:
    """Aplica `redact` em lote -- util para historico de chamados."""
    return [redact(t) for t in texts]
