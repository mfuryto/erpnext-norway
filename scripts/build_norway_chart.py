"""Convert pinned, licensed account data to the native ERPNext importer CSV.

No import, posting, tax calculation or network access is performed here.
"""
import csv
import hashlib
import io
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
RESOURCE = ROOT / "resources/norway-chart"
HEADERS = ["Account Name", "Parent Account", "Account Number", "Parent Account Number",
           "Is Group", "Account Type", "Root Type", "Account Currency"]
SOURCE_ROOTS = {
    "asset_current": "Asset", "asset_fixed": "Asset", "asset_prepayments": "Asset",
    "asset_receivable": "Asset", "asset_cash": "Asset",
    "equity": "Equity", "equity_unaffected": "Equity",
    "liability_current": "Liability", "liability_payable": "Liability",
    "income": "Income", "expense": "Expense", "expense_depreciation": "Expense",
}
ROOT_NAMES = {"Asset": "Eiendeler", "Liability": "Gjeld", "Equity": "Egenkapital",
              "Income": "Inntekter", "Expense": "Kostnader"}
GROUPS = [
    ("Bankkontoer", "Asset", "Bank"), ("Kontantkontoer", "Asset", "Cash"),
    ("Varelager", "Asset", "Stock"), ("Anleggsmidler", "Asset", ""),
    ("Omløpsmidler", "Asset", ""), ("Salgsinntekter", "Income", ""),
    ("Avgifter til gode", "Asset", "Tax"), ("Merverdiavgift", "Liability", "Tax"),
    ("Finansinntekter", "Income", ""), ("Varekostnader", "Expense", ""),
    ("Lønnskostnader", "Expense", ""), ("Avskrivninger", "Expense", ""),
    ("Andre driftskostnader", "Expense", ""), ("Finanskostnader", "Expense", ""),
    ("Skatt og resultatdisponering", "Expense", ""),
]
NATIVE_TYPES = {
    "1500": "Receivable", "2400": "Payable", "1900": "Cash", "1920": "Bank",
    "3000": "Income Account", "4300": "Cost of Goods Sold", "4390": "Stock Adjustment",
    "7740": "Round Off", "2740": "Tax", "1640": "Tax",
    **{code: "Stock" for code in ("1400", "1405", "1408", "1420", "1440", "1460", "1465", "1499")},
}


def source_accounts(resource=RESOURCE):
    source = json.loads((resource / "source.json").read_text())
    for name, expected in source["upstream_sha256"].items():
        if Path(name).name != name:
            raise ValueError("Upstream manifest must use plain filenames")
        if hashlib.sha256((resource / "upstream" / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Pinned upstream hash mismatch: {name}")
    with (resource / "upstream/account.account-no.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != source["accounts"] or len({row["code"] for row in rows}) != len(rows):
        raise ValueError("Account count or uniqueness does not match the pinned source")
    for row in rows:
        if not re.fullmatch(r"\d{4}", row["code"]) or not row["name@nb_NO"].strip():
            raise ValueError("Expected four-digit account number and Norwegian label")
        if row["account_type"] not in SOURCE_ROOTS:
            raise ValueError(f"Unmapped upstream account type: {row['account_type']}")
    return rows


def account_fields(row):
    code, source_type = row["code"], row["account_type"]
    # Upstream labels/codes are retained; its application-specific types are not copied blindly.
    root = "Income" if code.startswith("80") else SOURCE_ROOTS[source_type]
    account_type = NATIVE_TYPES.get(code, "")
    if source_type == "asset_fixed":
        account_type = "Fixed Asset"
    elif source_type == "expense_depreciation":
        account_type = "Depreciation"
    elif code[:2] in ("16", "27") and code[2] in ("0", "1"):
        account_type = "Tax"

    if account_type == "Tax":
        parent = "Avgifter til gode" if root == "Asset" else "Merverdiavgift"
    elif account_type in ("Bank", "Cash", "Stock"):
        parent = {"Bank": "Bankkontoer", "Cash": "Kontantkontoer", "Stock": "Varelager"}[account_type]
    elif root == "Asset":
        parent = "Anleggsmidler" if source_type == "asset_fixed" else "Omløpsmidler"
    elif root == "Income":
        parent = "Finansinntekter" if code.startswith("80") else "Salgsinntekter"
    elif root == "Expense":
        if source_type == "expense_depreciation":
            parent = "Avskrivninger"
        elif code.startswith("4"):
            parent = "Varekostnader"
        elif code.startswith("5"):
            parent = "Lønnskostnader"
        elif code.startswith("81"):
            parent = "Finanskostnader"
        elif code.startswith("8"):
            parent = "Skatt og resultatdisponering"
        else:
            parent = "Andre driftskostnader"
    else:
        parent = ROOT_NAMES[root]
    return root, account_type, parent


def render(resource=RESOURCE):
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(HEADERS)
    for root, name in ROOT_NAMES.items():
        writer.writerow([name, "", "", "", 1, "", root, "NOK"])
    for name, root, account_type in GROUPS:
        writer.writerow([name, ROOT_NAMES[root], "", "", 1, account_type, root, "NOK"])
    for row in source_accounts(resource):
        root, account_type, parent = account_fields(row)
        writer.writerow([row["name@nb_NO"], parent, row["code"], "", 0, account_type, root, "NOK"])
    return output.getvalue()


if __name__ == "__main__":
    target = RESOURCE / "norway.csv"
    target.write_text(render())
    print("Native ERPNext chart CSV generated from the pinned licensed source. No company changed.")
