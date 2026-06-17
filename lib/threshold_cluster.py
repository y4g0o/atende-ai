"""Threshold cluster — amostragem inteligente por similaridade Jaccard.

Usado por `/atende-criar` Fase 2 (análise de histórico) para reduzir N threads
similares a um representante por cluster. Evita pagar tokens por análise de
threads quase idênticos (ex: 50 chamados de "reset de senha" viram ~3 grupos).

Sem dependências externas — pure Python. Para 100-500 threads é suficiente.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from collections import defaultdict


_TOKEN_PATTERN = re.compile(r"\b[a-záàâãäéèêëíìîïóòôõöúùûüçñ]{3,}\b", re.IGNORECASE)


def _tokenize(text: str) -> set[str]:
    """Tokenização simples: palavras com 3+ caracteres, lowercase, sem acentos preservados."""
    if not text:
        return set()
    return {t.lower() for t in _TOKEN_PATTERN.findall(text)}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Coeficiente de Jaccard entre dois conjuntos."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


@dataclass
class Cluster:
    """Grupo de threads similares."""
    representative_idx: int      # índice da thread escolhida como representante
    member_indices: list[int]    # todos os índices que caíram neste cluster
    tokens: set[str] = field(default_factory=set)

    @property
    def size(self) -> int:
        return len(self.member_indices)


def cluster_threads(
    texts: list[str],
    threshold: float = 0.4,
    max_representatives: int = 50,
) -> list[Cluster]:
    """Agrupa textos similares e retorna representantes.

    Algoritmo: agglomerative greedy single-pass. Cada texto novo é comparado
    com o representante de cada cluster existente. Se similaridade >= threshold
    com algum, adiciona ao cluster. Senão, cria novo cluster.

    Args:
        texts: lista de textos (já PII-redacted recomendado)
        threshold: similaridade Jaccard mínima para agrupar (0.0–1.0)
        max_representatives: limite de clusters. Se ultrapassar, aumenta
            threshold automaticamente (cluster mais agressivo).

    Returns:
        Lista de Cluster ordenada por size (maiores primeiro).
    """
    if not texts:
        return []

    # Adaptive threshold se necessário
    current_threshold = threshold
    for attempt in range(5):  # até 5 tentativas
        clusters: list[Cluster] = []
        for idx, text in enumerate(texts):
            tokens = _tokenize(text)
            placed = False
            for c in clusters:
                if _jaccard(tokens, c.tokens) >= current_threshold:
                    c.member_indices.append(idx)
                    # representante continua sendo o primeiro (idx menor)
                    placed = True
                    break
            if not placed:
                clusters.append(Cluster(
                    representative_idx=idx,
                    member_indices=[idx],
                    tokens=tokens,
                ))

        if len(clusters) <= max_representatives:
            break
        # Muitos clusters — aumentar threshold para agrupar mais
        current_threshold = min(0.95, current_threshold + 0.1)

    # Ordenar por tamanho desc (representantes mais frequentes primeiro)
    clusters.sort(key=lambda c: c.size, reverse=True)
    return clusters


def sample_representatives(
    texts: list[str],
    threshold: float = 0.4,
    max_samples: int = 50,
) -> tuple[list[int], list[int]]:
    """Helper: retorna (índices_dos_representantes, contagens_por_representante).

    Para uso direto do `/atende-criar` Fase 2.
    """
    clusters = cluster_threads(texts, threshold=threshold, max_representatives=max_samples)
    rep_indices = [c.representative_idx for c in clusters]
    counts = [c.size for c in clusters]
    return rep_indices, counts


if __name__ == "__main__":
    # Demo — tickets de helpdesk SaaS fictícios
    samples = [
        "Nao consigo fazer login, senha errada [EMAIL]",
        "Esqueci minha senha, como resetar?",
        "Login bloqueado apos varias tentativas",
        "Conta suspensa, nao acessa o sistema",
        "Conta bloqueada por inatividade",
        "Quota de storage excedida no workspace [UUID]",
        "Preciso aumentar o limite do plano",
        "Billing duplicado no mes de [DATA]",
        "Cobrado duas vezes na fatura",
        "Nao estou conseguindo exportar os dados",
        "Como faço download do relatorio?",
        "Exportar CSV do workspace nao funciona",
    ]
    clusters = cluster_threads(samples, threshold=0.35)
    print(f"De {len(samples)} amostras → {len(clusters)} clusters:\n")
    for i, c in enumerate(clusters, 1):
        rep = samples[c.representative_idx]
        members = [samples[idx] for idx in c.member_indices]
        print(f"Cluster {i} (representante, {c.size} membros):")
        print(f"  → {rep}")
        if c.size > 1:
            for m in members[1:]:
                print(f"     · {m}")
        print()
