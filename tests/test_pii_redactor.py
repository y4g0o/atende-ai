import unittest

from _paths import REPO  # noqa: F401  (ajusta sys.path)
from pii_redactor import redact, redact_batch


class RedactTest(unittest.TestCase):
    def assertRedacted(self, text, must_contain, must_not_contain):
        out = redact(text).redacted_text
        for m in must_contain:
            self.assertIn(m, out, out)
        for m in must_not_contain:
            self.assertNotIn(m, out, out)

    def test_email(self):
        self.assertRedacted("Contato: maria@example.com", ["[EMAIL]"], ["maria@example.com"])

    def test_uuid_com_hifen(self):
        u = "12345678-aaaa-bbbb-cccc-1234567890ab"
        self.assertRedacted(f"id {u}", ["[UUID]"], [u])

    def test_chat_user_id(self):
        self.assertRedacted("marquei users/123456789012345678901", ["[USER_ID]"], ["123456789012345678901"])

    def test_pedido(self):
        self.assertRedacted("pedido #12345 chegou", ["[ORDER_ID]"], ["#12345"])

    def test_codigo_7(self):
        self.assertRedacted("codigo ABC1DEF", ["[CODE"], ["ABC1DEF"])

    def test_nome_proprio(self):
        self.assertRedacted("Cliente João Silva precisa", ["[NOME]"], ["João Silva"])
        self.assertRedacted("fala com Maria de Souza", ["[NOME]"], ["Maria de Souza"])

    def test_bucket_e_projeto(self):
        self.assertRedacted("gs://meu-bucket/x.pdf", ["[GCS_BUCKET]"], ["meu-bucket"])
        self.assertRedacted("projeto meu-projeto-123456", ["[GCP_PROJECT]"], ["123456"])

    def test_idempotente(self):
        r1 = redact("João Silva, codigo ABC1DEF, x@y.com").redacted_text
        self.assertEqual(r1, redact(r1).redacted_text)

    def test_vazio_e_contagem(self):
        self.assertEqual(redact("").redacted_text, "")
        r = redact("a@b.com e c@d.com")
        self.assertEqual(r.counts.get("[EMAIL]"), 2)
        self.assertEqual(r.total, 2)

    def test_batch(self):
        self.assertEqual(len(redact_batch(["a", "b@c.com"])), 2)


if __name__ == "__main__":
    unittest.main()
