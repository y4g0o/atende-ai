import json
import os
import warnings
from unittest import mock
import tempfile
import unittest
from pathlib import Path

from _paths import REPO  # noqa: F401
import audit_logger
from audit_logger import (_hash_payload, check_audit_available, log_execution,
                          tail_local_log)


class AuditLoggerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.log = Path(self.tmp.name) / "sub" / "audit.jsonl"

    def tearDown(self):
        self.tmp.cleanup()

    def _log(self, **kw):
        base = dict(area="demo", type_id=1, operator_email="op@example.com",
                    tool_name="mcp__x__y", payload={"a": 1}, prefer_bq=False,
                    local_log_path=self.log)
        base.update(kw)
        return log_execution(**base)

    def test_hash_deterministico_e_none(self):
        self.assertEqual(_hash_payload({"a": 1, "b": 2}), _hash_payload({"b": 2, "a": 1}))
        self.assertEqual(_hash_payload(None), "")
        self.assertNotEqual(_hash_payload({}), "")

    def test_grava_source_id_e_nao_payload_cru(self):
        self._log(source_id="spaces/S/threads/T", payload={"segredo": "x@y.com"})
        row = json.loads(self.log.read_text().splitlines()[-1])
        self.assertEqual(row["source_id"], "spaces/S/threads/T")
        self.assertNotIn("x@y.com", self.log.read_text())
        self.assertNotIn("thread_url", row)

    def test_thread_url_deprecated_vira_source_id(self):
        self._log(thread_url="https://chat/x")
        row = json.loads(self.log.read_text().splitlines()[-1])
        self.assertEqual(row["source_id"], "https://chat/x")

    def test_thread_url_emite_deprecation(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            self._log(thread_url="x")
        self.assertTrue(any(issubclass(i.category, DeprecationWarning) for i in w))

    def test_tail_normaliza_linha_antiga(self):
        self.log.parent.mkdir(parents=True)
        self.log.write_text(json.dumps({"area": "a", "thread_url": "antigo"}) + "\n")
        row = tail_local_log(1, log_path=self.log)[0]
        self.assertEqual(row["source_id"], "antigo")
        self.assertNotIn("thread_url", row)

    def test_ramo_bigquery(self):
        with mock.patch.object(audit_logger, "_bq_table_exists", return_value=True):
            ok, dest = check_audit_available(bq_table="p.d.t", local_log_path=self.log)
            self.assertEqual((ok, dest), (True, "bigquery:p.d.t"))
            with mock.patch.object(audit_logger, "_bq_insert", return_value=False) as ins, \
                 mock.patch("builtins.print") as pr:
                self._log(prefer_bq=True, bq_table="p.d.t")
            ins.assert_called_once()
            self.assertIn("FALHA ao inserir no BigQuery", pr.call_args[0][0])
        self.assertTrue(self.log.exists(), "o local recebe o evento mesmo com BQ")

    def test_source_id_tem_precedencia(self):
        self._log(source_id="novo", thread_url="velho")
        self.assertEqual(tail_local_log(1, log_path=self.log)[0]["source_id"], "novo")

    def test_tail_filtra_area(self):
        self._log(area="a1")
        self._log(area="a2")
        self.assertEqual([r["area"] for r in tail_local_log(10, area="a2", log_path=self.log)], ["a2"])

    def test_check_disponivel_local(self):
        ok, dest = check_audit_available(prefer_bq=False, local_log_path=self.log)
        self.assertTrue(ok, dest)
        self.assertTrue(dest.startswith("local:"))
        self.assertFalse(self.log.exists(), "a checagem nao deve escrever no log")

    @unittest.skipIf(os.geteuid() == 0, "root ignora permissao de escrita")
    def test_check_falha_sem_permissao(self):
        ro = Path(self.tmp.name) / "ro"
        ro.mkdir()
        ro.chmod(0o500)
        try:
            ok, motivo = check_audit_available(prefer_bq=False, local_log_path=ro / "a.jsonl")
            self.assertFalse(ok)
            self.assertIn("permissao", motivo)
        finally:
            ro.chmod(0o700)

    def test_log_nao_lanca_quando_local_falha(self):
        bloqueio = Path(self.tmp.name) / "arquivo"
        bloqueio.write_text("x")
        ev = self._log(local_log_path=bloqueio / "a.jsonl")  # pai e arquivo → OSError
        self.assertEqual(ev.area, "demo")


if __name__ == "__main__":
    unittest.main()
