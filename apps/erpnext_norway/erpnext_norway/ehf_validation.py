"""Fail-closed use of existing UBL XSD and official CEN/Peppol Schematron tools."""
from pathlib import Path
import hashlib
import json

DATA = Path(__file__).with_name('ehf_data')
RULES = ('CEN-EN16931-UBL', 'PEPPOL-EN16931-UBL')


def compile_rules():
    import edocument
    from saxonche import PySaxonProcessor
    sdk = Path(edocument.__file__).parent / 'edocument/profiles/peppol'
    compiler = sdk / 'peppol-bis-invoice-3/rules/tools/schxslt-1.10.1/2.0/pipeline-for-svrl.xsl'
    source = json.loads((DATA / 'source.json').read_text())
    (DATA / 'compiled').mkdir(exist_ok=True)
    with PySaxonProcessor(license=False) as processor:
        xslt = processor.new_xslt30_processor().compile_stylesheet(stylesheet_file=str(compiler))
        xslt.set_parameter("schxslt.compile.metadata", processor.make_boolean_value(False))
        for name in RULES:
            path = DATA / (name + '.sch')
            assert hashlib.sha256(path.read_bytes()).hexdigest() == source['files'][path.name]['sha256']
            xslt.transform_to_file(source_file=str(path), output_file=str(DATA / 'compiled' / (name + '.xsl')))


def validate(content):
    from edocument.edocument.validator import reject_doctype, validate_xml_against_xsd_file, validate_xml_against_schematron_file
    from edocument.edocument.profiles.peppol.validator import _get_peppol_xsd_path
    reject_doctype(content)
    validate_xml_against_xsd_file(content, _get_peppol_xsd_path(content))
    errors, warnings = [], []
    for name in RULES:
        failed, warned = validate_xml_against_schematron_file(content, DATA / 'compiled' / (name + '.xsl'))
        errors.extend(failed); warnings.extend(warned)
    if errors:
        import frappe
        frappe.throw('EHF-valideringen avviste dokumentet:\n' + '\n'.join(errors))
    return warnings


if __name__ == '__main__':
    compile_rules()
