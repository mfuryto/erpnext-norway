from frappe.model.document import Document
from erpnext_norway.enk_tax import validate


class NorwegianTaxFacts(Document):
    def validate(self):
        validate(self)
