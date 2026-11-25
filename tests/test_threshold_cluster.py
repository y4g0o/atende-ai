import unittest

from _paths import REPO  # noqa: F401
from threshold_cluster import cluster_threads, sample_representatives


class ClusterTest(unittest.TestCase):
    def test_vazio(self):
        self.assertEqual(cluster_threads([]), [])

    def test_agrupa_similares(self):
        texts = ["senha errada login bloqueado", "login bloqueado senha errada hoje",
                 "fatura cobrada duas vezes", "cobrada duas vezes fatura mensal"]
        clusters = cluster_threads(texts, threshold=0.4)
        self.assertEqual(len(clusters), 2)
        self.assertEqual(sorted(c.size for c in clusters), [2, 2])

    def test_cobre_todos_os_indices_uma_vez(self):
        texts = [f"assunto {i} texto distinto palavra{i}" for i in range(20)]
        clusters = cluster_threads(texts, threshold=0.9)
        idx = sorted(i for c in clusters for i in c.member_indices)
        self.assertEqual(idx, list(range(20)))

    def test_limite_de_representantes(self):
        texts = [f"tema comum chamado variante{i}" for i in range(30)]
        reps, counts = sample_representatives(texts, threshold=0.95, max_samples=5)
        self.assertEqual(sum(counts), 30)
        self.assertEqual(len(reps), len(counts))


if __name__ == "__main__":
    unittest.main()
