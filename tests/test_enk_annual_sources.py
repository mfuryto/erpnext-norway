"""Independent official 2026 catalogue and reused person-income examples."""
import csv,hashlib,importlib.util,json,sys,types,unittest,xml.etree.ElementTree as ET
from pathlib import Path
from decimal import Decimal as D
ROOT=Path(__file__).resolve().parents[1]/'apps/erpnext_norway/erpnext_norway'
# The independent arithmetic module has no Frappe runtime dependency.
package=types.ModuleType('erpnext_norway');package.__path__=[str(ROOT)]
sys.modules.setdefault('erpnext_norway',package)
from erpnext_norway.enk_person_income import PersonalIncomeInput as Input,calculate_personal_income as calc,YearEndError

class AnnualSourceTest(unittest.TestCase):
    def test_all_131_official_enk_posts_labels_signs_and_provenance(self):
        path=ROOT/'enk_data';source=json.loads((path/'source.json').read_text())
        for name,digest in source['files'].items():self.assertEqual(hashlib.sha256((path/name).read_bytes()).hexdigest(),digest)
        ns={'k':'urn:no:skatteetaten:informasjonsforvaltning:kodeliste:v2'}
        official={}
        for sub in ET.parse(path/'resultatregnskap-og-balanse-2026.xml').findall('k:underkodeliste',ns):
            for node in sub.findall('k:kode',ns):
                extra=node.find('k:kodetillegg',ns)
                if extra is None or 'enkeltpersonforetak' not in [v.text for v in extra.findall('k:virksomhetstype',ns)] or 'ingenRegnskapsplikt' not in [v.text for v in extra.findall('k:regnskapspliktstype',ns)]:continue
                label=next(v.findtext('k:tekst',namespaces=ns) for v in node.findall('k:visningsnavn/k:spraakTekst',ns) if v.findtext('k:spraak',namespaces=ns)=='nb_NO')
                official[(sub.findtext('k:tekniskNavn',namespaces=ns),node.findtext('k:tekniskNavn',namespaces=ns))]=(label,extra.findtext('k:kategori',namespaces=ns))
        with (path/'fields-2026.csv').open() as stream:
            actual={(r['category'],r['code']):(r['label'],r['polarity']) for r in csv.DictReader(stream,delimiter=';')}
        self.assertEqual(len(actual),131);self.assertEqual(actual,official)

    def test_gross_debt_limit_is_separate_from_documented_net_shielding(self):
        # 200k gross assets, 300k qualifying debt => one third of 30k interest
        # added back. Actual shielding 4000 is an independent documented fact.
        v=calc(D('100000'),Input(capital_return_base=D('200000'),qualifying_business_debt=D('300000'),
            qualifying_business_debt_interest=D('30000'),capital_income=D('2000'),capital_costs=D('1000'),
            documented_shielding=D('4000'),carried_forward_negative=D('20000')))
        self.assertEqual((v.interest_addback,v.person_income_before_carryforward,v.person_income),(10000,105000,85000))

    def test_unknown_shielding_is_not_zero_and_negative_carry_is_preserved(self):
        with self.assertRaises(YearEndError):calc(D(100),Input(capital_return_base=D(1000)))
        negative=calc(D('-5000'),Input(capital_return_base=D(0),carried_forward_negative=D('2000')))
        self.assertEqual((negative.person_income,negative.remaining_negative_carryforward),(-5000,7000))
        zero=calc(D('2000'),Input(capital_return_base=D(0),carried_forward_negative=D('3000')))
        self.assertEqual((zero.person_income,zero.remaining_negative_carryforward),(0,1000))
