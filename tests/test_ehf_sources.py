"""Verify that the bundled production rules and generator lock retain provenance."""
import hashlib,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'apps/erpnext_norway/erpnext_norway/ehf_data'

class EHFSources(unittest.TestCase):
    def test_official_rules_and_pinned_generator(self):
        source=json.loads((DATA/'source.json').read_text())
        self.assertEqual(source['mandatory_from'],'2026-08-17')
        self.assertEqual(set(source['files']),{'CEN-EN16931-UBL.sch','PEPPOL-EN16931-UBL.sch'})
        for name,meta in source['files'].items():
            content=(DATA/name).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(),meta['sha256'])
            self.assertIn('docs.peppol.eu/poacc/billing/3.0/',meta['url'])
            self.assertIn(b'assert',content)
        lock=(ROOT/'deploy/ehf-requirements.txt').read_text()
        self.assertIn(source['generator']['revision'],lock)
        self.assertIn(source['generator']['archive_sha256'],lock)
        self.assertIn('GNU GENERAL PUBLIC LICENSE',(DATA/'LICENSE.edocument.txt').read_text())
