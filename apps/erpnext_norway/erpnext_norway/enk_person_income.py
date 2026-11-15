"""Person-income bridge reused from ENK Norge, not personal tax calculation.

Copyright (c) 2026 Haakon Fornes, MIT; see saft_data/LICENSE.enk-norge.
Source Medpus/enk_norge@94406e542ed991a8de237b9de44b8d1dd576b566/year_end.py.
Only immutable inputs and arithmetic are retained. No report/status/snapshot or
posting controller. The rate branch is removed: shielding is a documented amount;
capital_return_base is the GROSS base before debt, not the net shielding base.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from erpnext_norway.enk_tax_rules import _decimal_amount

class YearEndError(ValueError):
    pass

def _to_decimal(value, label, *, allow_negative=False):
    try:
        return _decimal_amount(value, label, allow_negative=allow_negative)
    except ValueError as error:
        raise YearEndError(str(error)) from error

def _amount(value, label):
    return _to_decimal(value, label)

def _money(value):
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

@dataclass(frozen=True, slots=True)
class PersonalIncomeInput:
    """Poster i Skatteetatens E-5-4.2; beløp er dokumenterte årsbeløp."""

    capital_return_base: Decimal
    capital_income: Decimal = Decimal("0")
    financial_gains: Decimal = Decimal("0")
    capital_costs: Decimal = Decimal("0")
    financial_losses: Decimal = Decimal("0")
    private_debt_interest: Decimal = Decimal("0")
    qualifying_business_debt: Decimal = Decimal("0")
    qualifying_business_debt_interest: Decimal = Decimal("0")
    special_deductions: Decimal = Decimal("0")
    documented_shielding: Decimal | None = None
    carried_forward_negative: Decimal = Decimal("0")


@dataclass(frozen=True, slots=True)
class PersonalIncomeCalculation:
    business_profit: Decimal
    capital_income_deduction: Decimal
    capital_cost_addback: Decimal
    interest_addback: Decimal
    special_deduction_addback: Decimal
    shielding: Decimal
    person_income_before_carryforward: Decimal
    carried_forward_negative_used: Decimal
    person_income: Decimal
    remaining_negative_carryforward: Decimal


def calculate_personal_income(
    business_profit: Decimal, inputs: PersonalIncomeInput
) -> PersonalIncomeCalculation:
    """Foretaksmodellen etter E-5-4.2, avgrenset til dokumenterte poster."""
    profit = _to_decimal(business_profit, "Skattemessig næringsresultat", allow_negative=True)
    base = _amount(inputs.capital_return_base, "Kapitalavkastningsgrunnlag")
    if inputs.documented_shielding is not None:
        shielding = _amount(inputs.documented_shielding, "Dokumentert skjerming")
    elif base == 0:
        shielding = Decimal("0")
    else:
        raise YearEndError(
            "Dokumentert skjermingsbeløp kreves når grunnlaget ikke er null."
        )
    minus = _amount(inputs.capital_income, "Kapitalinntekt") + _amount(
        inputs.financial_gains, "Finansgevinst"
    )
    plus = (
        _amount(inputs.capital_costs, "Kapitalkostnad")
        + _amount(inputs.financial_losses, "Finanstap")
        + _amount(inputs.private_debt_interest, "Privat gjeldsrente")
        + _amount(inputs.special_deductions, "Særskilt fradrag")
    )
    debt = _amount(inputs.qualifying_business_debt, "Kvalifiserende foretaks­gjeld")
    interest = _amount(inputs.qualifying_business_debt_interest, "Rente på kvalifiserende foretaks­gjeld")
    interest_addback = Decimal("0") if not debt else _money(interest * max(Decimal("0"), debt - base) / debt)
    negative = _amount(inputs.carried_forward_negative, "Fremførbar negativ personinntekt")
    before = profit - minus + plus + interest_addback - shielding
    used = min(max(Decimal("0"), before), negative)
    person_income = before - used
    remaining_negative = negative - used + max(Decimal("0"), -before)
    return PersonalIncomeCalculation(
        *map(
            _money,
            (
                profit,
                minus,
                plus,
                interest_addback,
                _amount(inputs.special_deductions, "Særskilt fradrag"),
                shielding,
                before,
                used,
                person_income,
                remaining_negative,
            ),
        )
    )
