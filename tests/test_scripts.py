"""Testes dos scripts shell (validate, check-no-pii, install) em diretorios temporarios."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import REPO

SCRIPTS = REPO / "scripts"


def run(cmd, env=None, cwd=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run(cmd, capture_output=True, text=True, env=e, cwd=cwd)


class ValidateTest(unittest.TestCase):
    def test_areas_e_exemplo_validos(self):
        for f in [*sorted((REPO / "areas").glob("*.yaml")), REPO / "examples" / "minimal-area.yaml"]:
            r = run(["bash", str(SCRIPTS / "validate.sh"), str(f)])
            self.assertEqual(r.returncode, 0, f"{f.name}: {r.stdout}{r.stderr}")

    def test_caminho_com_aspas(self):
        d = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, d)
        f = d / "it's a test.yaml"
        shutil.copy(REPO / "examples" / "minimal-area.yaml", f)
        r = run(["bash", str(SCRIPTS / "validate.sh"), str(f)])
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_yaml_invalido_falha(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as t:
            t.write("schema: atende.v1\narea: {name: X_invalido, owner_team: t}\n")
        try:
            r = run(["bash", str(SCRIPTS / "validate.sh"), t.name])
            self.assertNotEqual(r.returncode, 0)
        finally:
            os.unlink(t.name)


class CheckNoPiiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "doc.md").write_text("contato da ACME-SECRETA aqui\n")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_detecta_padrao_do_arquivo_local(self):
        pf = self.tmp / "pats"
        pf.write_text("# comentario\n\nacme-secreta\n")
        r = run(["bash", str(SCRIPTS / "check-no-pii.sh"), str(self.tmp)], env={"PII_PATTERNS_FILE": str(pf)})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("acme-secreta", r.stdout)

    def test_sem_padroes_avisa_e_strict_falha(self):
        env = {"PII_PATTERNS_FILE": str(self.tmp / "inexistente")}
        r = run(["bash", str(SCRIPTS / "check-no-pii.sh"), str(self.tmp)], env=env)
        self.assertEqual(r.returncode, 0)
        self.assertIn("Nenhum padrao proibido configurado", r.stdout)
        r = run(["bash", str(SCRIPTS / "check-no-pii.sh"), str(self.tmp)], env={**env, "PII_STRICT": "1"})
        self.assertEqual(r.returncode, 1)

    def _pii(self, patterns_text, newline="\n"):
        pf = self.tmp.parent / (self.tmp.name + ".pats")
        pf.write_bytes(patterns_text.replace("\n", newline).encode())
        self.addCleanup(pf.unlink)
        return run(["bash", str(SCRIPTS / "check-no-pii.sh"), str(self.tmp)], env={"PII_PATTERNS_FILE": str(pf)})

    def test_regex_invalida_nao_vira_ok(self):
        r = self._pii("acme(\n")
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertIn("Regex invalida", r.stdout)

    def test_arquivo_de_padroes_com_crlf(self):
        self.assertEqual(self._pii("acme-secreta\n", newline="\r\n").returncode, 1)

    def test_arquivo_sem_extensao_e_varrido(self):
        (self.tmp / "doc.md").unlink()
        (self.tmp / "CODEOWNERS").write_text("* @acme-secreta\n")
        self.assertEqual(self._pii("acme-secreta\n").returncode, 1)

    def test_modo_quiet_nao_imprime_termo(self):
        (self.tmp / "doc.md").write_text("linha um\ncontato acme-secreta aqui\n")
        pf = self.tmp.parent / (self.tmp.name + ".q")
        pf.write_text("acme-secreta\n")
        self.addCleanup(pf.unlink)
        r = run(["bash", str(SCRIPTS / "check-no-pii.sh"), str(self.tmp)],
                env={"PII_PATTERNS_FILE": str(pf), "PII_QUIET": "1"})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertNotIn("acme-secreta", r.stdout.lower())
        self.assertIn("doc.md:2", r.stdout)
        self.assertIn("Padrao #1", r.stdout)

    def test_modo_quiet_historico_nao_imprime_termo(self):
        (self.tmp / "doc.md").write_text("limpo\n")
        git = ["git", "-C", str(self.tmp), "-c", "user.name=t", "-c", "user.email=t@example.com"]
        run(["git", "init", "-q", str(self.tmp)])
        (self.tmp / "velho.md").write_text("acme-secreta\n")
        run([*git, "add", "-A"]); run([*git, "commit", "-qm", "c1"])
        (self.tmp / "velho.md").unlink()
        run([*git, "add", "-A"]); run([*git, "commit", "-qm", "c2"])
        pf = self.tmp.parent / (self.tmp.name + ".q2")
        pf.write_text("acme-secreta\n")
        self.addCleanup(pf.unlink)
        r = run(["bash", str(SCRIPTS / "check-no-pii.sh"), str(self.tmp)],
                env={"PII_PATTERNS_FILE": str(pf), "PII_QUIET": "1"})
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("historico git", r.stdout)
        self.assertNotIn("acme-secreta", r.stdout.lower())

    def test_padrao_com_espacos_nas_pontas(self):
        self.assertEqual(self._pii("   acme-secreta  \n").returncode, 1)

    def test_arquivo_binario_e_varrido(self):
        (self.tmp / "doc.md").unlink()
        (self.tmp / "x.pdf").write_bytes(b"%PDF\x00\x01 acme-secreta \x00")
        self.assertEqual(self._pii("acme-secreta\n").returncode, 1)

    def test_padrao_comecando_com_hifen(self):
        (self.tmp / "doc.md").write_text("valor -x-secreto aqui\n")
        self.assertEqual(self._pii("-x-secreto\n").returncode, 1)

    def test_historico_git_e_varrido(self):
        (self.tmp / "doc.md").write_text("limpo\n")
        git = ["git", "-C", str(self.tmp), "-c", "user.name=t", "-c", "user.email=t@example.com"]
        run(["git", "init", "-q", str(self.tmp)])
        (self.tmp / "velho.md").write_text("acme-secreta\n")
        run([*git, "add", "-A"]); run([*git, "commit", "-qm", "c1"])
        (self.tmp / "velho.md").unlink()
        run([*git, "add", "-A"]); run([*git, "commit", "-qm", "c2"])
        r = self._pii("acme-secreta\n")
        self.assertEqual(r.returncode, 1, r.stdout)
        self.assertIn("historico git", r.stdout)

    def test_arquivo_de_padroes_nao_se_auto_acusa(self):
        pf = self.tmp / ".pii-patterns.local"
        pf.write_text("termo-unico-xyz\n")
        r = run(["bash", str(SCRIPTS / "check-no-pii.sh"), str(self.tmp)], env={"PII_PATTERNS_FILE": str(pf)})
        self.assertEqual(r.returncode, 0, r.stdout)


class InstallTest(unittest.TestCase):
    def setUp(self):
        self.home = Path(tempfile.mkdtemp())
        self.env = {"HOME": str(self.home)}
        self.cmds = self.home / ".claude" / "commands"
        self.agents = self.home / ".claude" / "agents"

    def tearDown(self):
        shutil.rmtree(self.home)

    def install(self, *args):
        return run(["bash", str(SCRIPTS / "install.sh"), *args], env=self.env)

    def test_instala_e_e_idempotente(self):
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(os.readlink(self.agents / "atende-classifier.md"), str(REPO / "engine" / "atende-classifier.md"))
        self.assertTrue((self.cmds / "atende.md").is_symlink())
        r = self.install()
        self.assertEqual(r.returncode, 0)
        self.assertIn("[skip]", r.stdout)

    def test_conflito_aborta_sem_alterar_nada(self):
        self.cmds.mkdir(parents=True)
        outro = self.home / "outro-repo-atende.md"
        outro.write_text("x")
        (self.cmds / "atende.md").symlink_to(outro)
        r = self.install()
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertEqual(os.readlink(self.cmds / "atende.md"), str(outro))
        self.assertFalse((self.cmds / "atende-criar.md").exists(), "nao pode instalar pela metade")

    def test_force_reaponta(self):
        self.cmds.mkdir(parents=True)
        outro = self.home / "outro.md"
        outro.write_text("x")
        (self.cmds / "atende.md").symlink_to(outro)
        r = self.install("--force")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(os.readlink(self.cmds / "atende.md"), str(REPO / "engine" / "atende.md"))
        self.assertTrue(outro.exists(), "o arquivo do outro repo nao pode ser tocado")

    def test_argumento_desconhecido_falha(self):
        self.assertEqual(self.install("-f").returncode, 64)
        self.assertEqual(self.install("--force", "--bogus").returncode, 64)
        self.assertEqual(self.install("", "bogus").returncode, 64)

    def test_backup_existente_nao_e_sobrescrito(self):
        self.cmds.mkdir(parents=True)
        (self.cmds / "atende.md.bak").write_text("v1")
        (self.cmds / "atende.md").write_text("v2")
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual((self.cmds / "atende.md.bak").read_text(), "v1")
        self.assertEqual([b.read_text() for b in self.cmds.glob("atende.md.bak.*")], ["v2"])

    def test_repo_por_caminho_com_symlink_nao_e_conflito(self):
        alias = self.home / "alias-repo"
        alias.symlink_to(REPO)
        self.assertEqual(self.install().returncode, 0)
        r = run(["bash", str(alias / "scripts" / "install.sh")], env=self.env)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_arquivo_regular_vira_backup(self):
        self.cmds.mkdir(parents=True)
        (self.cmds / "atende.md").write_text("meu")
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual((self.cmds / "atende.md.bak").read_text(), "meu")


if __name__ == "__main__":
    unittest.main()
