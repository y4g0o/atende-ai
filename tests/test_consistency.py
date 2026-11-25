"""Invariantes entre engine, schema, docs e areas de exemplo."""
import json
import re
import unittest
from fnmatch import fnmatch

import yaml

from _paths import REPO

ENGINE = (REPO / "engine" / "atende.md").read_text()
CLASSIFIER = (REPO / "engine" / "atende-classifier.md").read_text()


def json_keys(md: str, marker: str) -> set:
    """Chaves de 1o nivel do primeiro bloco ```json apos `marker`."""
    block = md.split(marker, 1)[1].split("```json", 1)[1].split("```", 1)[0]
    return set(re.findall(r'^\s{2}"([a-z_]+)":', block, re.M))


def area_files():
    return [*sorted((REPO / "areas").glob("*.yaml")), REPO / "examples" / "minimal-area.yaml"]


def allowed(tool, whitelist):
    return any(fnmatch(tool, w) for w in whitelist)


class ConsistencyTest(unittest.TestCase):
    def test_contrato_json_classifier_igual_ao_engine(self):
        self.assertEqual(json_keys(CLASSIFIER, "## Output esperado"),
                         json_keys(ENGINE, "Receba JSON"))

    def test_templates_usam_requester_address_e_sem_markdown(self):
        for f in area_files():
            data = yaml.safe_load(f.read_text())
            for t in data["types"]:
                for lang, tpl in t["response_template"].items():
                    where = f"{f.name} tipo {t['id']} {lang}"
                    self.assertNotIn("<users/", tpl, where)
                    self.assertNotIn("**", tpl, where)
                    self.assertIn("{{ requester_address }}", tpl, where)

    def test_whitelist_cobre_canal_e_operacoes(self):
        for f in area_files():
            data = yaml.safe_load(f.read_text())
            wl = data["tools_allowed"]
            for name, tool in data["channel"]["tools"].items():
                self.assertTrue(allowed(tool, wl), f"{f.name}: channel.tools.{name}={tool}")
            for t in data["types"]:
                tool = t["operation"]["tool"]
                if tool.startswith("mcp__"):
                    self.assertTrue(allowed(tool, wl), f"{f.name} tipo {t['id']}: {tool}")

    def test_blocker_sql_diz_o_que_fazer(self):
        # todo blocker com sql deve dizer o que fazer quando bloqueia
        for f in area_files():
            for t in yaml.safe_load(f.read_text())["types"]:
                for b in t.get("blockers", []):
                    if "sql" in b:
                        self.assertTrue(b.get("if_returns_rows") or b.get("else_message"),
                                        f"{f.name} tipo {t['id']} blocker {b['check']}")

    def test_fallbacks_e_globals_sem_markdown(self):
        bloco = ENGINE.split("Templates de fallback", 1)[1].split("## ", 1)[0]
        mensagens = re.findall(r'"([^"]+)"', bloco)  # o texto que vai ao canal fica entre aspas
        self.assertGreaterEqual(len(mensagens), 3)
        for m in mensagens:
            self.assertNotIn("**", m)
        g = yaml.safe_load((REPO / "globals.yaml").read_text())
        for lang, tpl in g["default_response_template"].items():
            self.assertNotIn("**", tpl, lang)
            self.assertIn("{{ requester_address }}", tpl, lang)

    def test_mencao_sem_prefixo_duplicado(self):
        for p in [*(REPO / "engine").glob("*.md"), *(REPO / "docs").glob("*.md"), *area_files()]:
            self.assertNotIn("<users/{{", p.read_text(), p.name)

    def test_sql_parametrizado(self):
        # nenhum {{ }} dentro de SQL (lookups e blockers), com ou sem aspas
        for f in area_files():
            data = yaml.safe_load(f.read_text())
            sqls = [l["sql"] for l in data.get("entity_lookups", [])]
            sqls += [b["sql"] for t in data["types"] for b in t.get("blockers", []) if "sql" in b]
            for q in sqls:
                self.assertNotIn("{{", q, f.name)

    def test_engine_valida_valor_antes_do_sql(self):
        self.assertIn("não aceita parâmetros", ENGINE)
        self.assertIn("Valide o valor contra um formato estrito", ENGINE)

    def test_mencao_rascunho_usa_arroba(self):
        self.assertIn("@{{ requester_name }}", ENGINE)

    def test_classifier_source_id_com_prefixo_spaces(self):
        self.assertIn('source_id: "spaces/<SPACE>/threads/<THREAD_ID>"', CLASSIFIER)

    def test_licoes_nao_afirmam_comportamento_de_desativacao(self):
        self.assertNotIn("desativar uma conta nao exclui dados", (REPO / "docs" / "07-licoes.md").read_text())

    def test_destrutivo_sempre_exige_frase(self):
        self.assertNotIn("entidade grande", ENGINE)
        self.assertIn("**sempre**, qualquer tamanho", ENGINE)

    def test_pausa3_nao_envia_com_sim_ambiguo(self):
        self.assertNotIn('Após `"sim"` → usar `channel.tools.send`', ENGINE)
        self.assertIn("pergunte de novo", ENGINE)

    def test_anti_spoof_compara_pertencimento(self):
        self.assertNotIn("source == channel.source_production", ENGINE)
        self.assertIn("<canal_ativo>/threads/", ENGINE)

    def test_audit_usa_destination_da_area(self):
        self.assertNotIn("Gravar em `REPLACE_AUDIT_PROJECT", ENGINE)
        self.assertIn("bq_table=", ENGINE)

    def test_refinar_roda_lint_antes_do_commit(self):
        ref = (REPO / "engine" / "atende-refinar.md").read_text()
        self.assertLess(ref.index("check-no-pii.sh"), ref.index("git commit"))

    def test_docs_sem_schema_antigo(self):
        antigo = re.compile(r"\bchat\.space_|\bchat_test\b|\bspace_production\b|\bspace_test\b")
        for p in [*REPO.glob("*.md"), *(REPO / "docs").glob("*.md"), *(REPO / "engine").glob("*.md")]:
            self.assertIsNone(antigo.search(p.read_text()), p.name)

    def test_schema_exige_channel(self):
        schema = json.loads((REPO / "schemas" / "atende.v1.json").read_text())
        self.assertIn("channel", schema["required"])
        self.assertNotIn("chat", schema["properties"])

    def test_globals_regras_absolutas(self):
        g = yaml.safe_load((REPO / "globals.yaml").read_text())
        regras = {k for d in g["absolute_rules"] for k in d}
        for r in ["require_approval_pause_2", "require_approval_pause_3", "require_audit_log",
                  "never_invent", "identity_check_before_delivery"]:
            self.assertIn(r, regras)

    def test_engine_tem_checagem_de_audit_antes_de_executar(self):
        self.assertLess(ENGINE.index("check_audit_available"), ENGINE.index("## PASSO 4 — EXECUTAR"))
        self.assertLess(ENGINE.index("CHECAGEM DE IDENTIDADE"), ENGINE.index("PAUSA 3"))


if __name__ == "__main__":
    unittest.main()
