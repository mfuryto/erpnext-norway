"""Norwegian tax balance arithmetic; a/d foundation reused from ENK Norge.

Copyright (c) 2026 Haakon Fornes. MIT; see saft_data/LICENSE.enk-norge.
Source: Medpus/enk_norge@94406e542ed991a8de237b9de44b8d1dd576b566,
enk_norge/norway_rules.py. The independent saldo subset is retained. Extensions implement documented
b/c/e-j and gain/loss-account rules; no posting or ledger is added.
"""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum

SMALL_SALDO_THRESHOLD = Decimal('30000')

class RuleValidationError(ValueError):
    pass

class SaldoGroup(StrEnum):
    A = "a"
    B = "b"
    C = "c"
    D = "d"
    E = "e"
    F = "f"
    G = "g"
    H = "h"
    I = "i"
    J = "j"

@dataclass(frozen=True, slots=True)
class SaldoPoolResult:
    group: SaldoGroup
    year_end: date
    depreciation_rate: Decimal
    opening_balance: Decimal
    acquisitions: Decimal
    disposal_proceeds: Decimal
    disposal_proceeds_taken_to_income: Decimal
    balance_before_year_end_adjustments: Decimal
    depreciation_deduction: Decimal
    negative_balance_income: Decimal
    closing_balance: Decimal
    gain_loss_transfer: Decimal = Decimal("0")
    unit: str = ""

def calculate_saldo_pool(
    *,
    group: SaldoGroup,
    year_end: date,
    opening_balance: Decimal,
    acquisitions: Decimal = Decimal("0"),
    disposal_proceeds: Decimal = Decimal("0"),
    disposal_proceeds_taken_to_income: Decimal = Decimal("0"),
    requested_depreciation: Decimal | None = None,
    write_off_small_positive_balance: bool = False,
    additional_negative_balance_income: Decimal = Decimal("0"),
    disposed: bool = False,
    rate: Decimal | None = None,
    unit: str = "",
) -> SaldoPoolResult:
    """Beregner en dokumentert saldoskatteposisjon for ett fullt 2026-inntektsår.

    Realisasjonsvederlag som ikke er valgt tatt direkte til inntekt nedskrives på
    saldoen. Positiv restsaldo under 30 000 kroner kan velges fullt fradragsført.
    Negativ restsaldo under 30 000 kroner skal inntektsføres fullt; ved 30 000
    kroner eller mer er minst gruppens sats pliktig inntektsføring.
    """

    _require_year_end(year_end)
    if not isinstance(group, SaldoGroup):
        raise RuleValidationError("Velg en gyldig saldogruppe a–j.")
    if not isinstance(write_off_small_positive_balance, bool):
        raise RuleValidationError("write_off_small_positive_balance må være bool.")
    rates = dict(zip(SaldoGroup, map(Decimal, ('0.30','0.20','0.24','0.20','0.14','0.12','0.05','0.04','0.02','0.10'))))
    standard_rate = rates[group]
    rate = standard_rate if rate is None else _decimal_amount(rate, 'Avskrivningssats')
    allowed = {Decimal('0.04'), Decimal('0.06'), Decimal('0.10'), Decimal('0.20')} if group == SaldoGroup.H else {standard_rate}
    if rate not in allowed:
        raise RuleValidationError('Satsen er ikke kvalifisert for denne saldogruppen.')
    opening = _decimal_amount(opening_balance, "Inngående saldo", allow_negative=True)
    adds = _decimal_amount(acquisitions, "Netto tilgang og dokumenterte kostkorreksjoner", allow_negative=True)
    proceeds = _decimal_amount(disposal_proceeds, "Realisasjonsvederlag")
    direct_income = _decimal_amount(
        disposal_proceeds_taken_to_income, "Direkte inntektsført realisasjonsvederlag"
    )
    if direct_income > proceeds:
        raise RuleValidationError("Direkte inntektsført vederlag kan ikke overstige samlet vederlag.")
    additional_income = _decimal_amount(
        additional_negative_balance_income, "Ekstra inntektsføring av negativ saldo"
    )
    if requested_depreciation is not None:
        requested = _decimal_amount(requested_depreciation, "Ønsket avskrivning")
    else:
        requested = None

    balance = opening + adds - (proceeds - direct_income)
    depreciation = Decimal("0")
    negative_income = Decimal("0")
    transfer = Decimal('0')
    individual = group in {SaldoGroup.E, SaldoGroup.F, SaldoGroup.G, SaldoGroup.H, SaldoGroup.I}
    if (individual and disposed) or (group == SaldoGroup.B and balance < 0):
        if requested is not None or write_off_small_positive_balance or additional_income:
            raise RuleValidationError('Realisert individuell saldo eller negativ b-saldo overføres til gevinst- og tapskonto uten saldoavskrivning.')
        transfer = -balance
        closing = Decimal('0')
    elif balance < 0 and individual:
        if requested is not None or write_off_small_positive_balance or additional_income:
            raise RuleValidationError('Negativ inngangsverdi uten realisasjon gir ikke årets avskrivning eller inntektsføring.')
        closing = balance
    elif balance > 0:
        if additional_income:
            raise RuleValidationError("Ekstra negativ-saldo-inntekt krever negativ saldo.")
        if write_off_small_positive_balance:
            if balance >= SMALL_SALDO_THRESHOLD:
                raise RuleValidationError("Full fradragsføring av restsaldo krever saldo under 30 000 kroner.")
            maximum_deduction = balance
        else:
            maximum_deduction = balance * rate
        depreciation = maximum_deduction if requested is None else requested
        if depreciation > maximum_deduction:
            raise RuleValidationError("Ønsket avskrivning overstiger tillatt fradrag.")
        closing = balance - depreciation
    elif balance < 0:
        if requested is not None or write_off_small_positive_balance:
            raise RuleValidationError("Avskrivning og positiv-restsaldo-valg krever positiv saldo.")
        negative_amount = -balance
        mandatory_income = negative_amount if negative_amount < SMALL_SALDO_THRESHOLD else negative_amount * rate
        negative_income = mandatory_income + additional_income
        if negative_income > negative_amount:
            raise RuleValidationError("Inntektsføring kan ikke overstige negativ saldo.")
        closing = balance + negative_income
    else:
        if requested not in (None, Decimal("0")) or additional_income or write_off_small_positive_balance:
            raise RuleValidationError("Ingen årsjustering kan velges når saldoen er null.")
        closing = Decimal("0")

    return SaldoPoolResult(
        group=group,
        year_end=year_end,
        depreciation_rate=rate,
        opening_balance=opening,
        acquisitions=adds,
        disposal_proceeds=proceeds,
        disposal_proceeds_taken_to_income=direct_income,
        balance_before_year_end_adjustments=balance,
        depreciation_deduction=depreciation,
        negative_balance_income=negative_income,
        closing_balance=closing,
        gain_loss_transfer=transfer,
        unit=unit,
    )

def _require_year_end(value):
    if type(value) is not date or value != date(2026, 12, 31):
        raise RuleValidationError('Saldoberegningen er kvalifisert for 2026-12-31.')

def _decimal_amount(value: Decimal, field_name: str, *, allow_negative: bool = False) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, Decimal):
        raise RuleValidationError(f"{field_name} må oppgis som Decimal, ikke float eller int.")
    if not value.is_finite():
        raise RuleValidationError(f"{field_name} må være et endelig tall.")
    if not allow_negative and value < 0:
        raise RuleValidationError(f"{field_name} kan ikke være negativt.")
    return value


@dataclass(frozen=True, slots=True)
class GainLossResult:
    opening: Decimal
    transfers: Decimal
    basis: Decimal
    income: Decimal
    deduction: Decimal
    closing: Decimal


def calculate_gain_loss(opening, transfers, *, extra_income=Decimal('0'), requested_deduction=None, write_off_small=False):
    """Sktl. §§14-45,14-47: positive gains min20%; losses max20%, small-balance option."""
    opening = _decimal_amount(opening, 'Inngående gevinst-/tapskonto', allow_negative=True)
    transfers = _decimal_amount(transfers, 'Årets overføringer', allow_negative=True)
    extra = _decimal_amount(extra_income, 'Ekstra inntektsføring fra gevinst-/tapskonto')
    basis = opening + transfers
    income = deduction = Decimal('0')
    if basis > 0:
        if requested_deduction is not None or write_off_small:
            raise RuleValidationError('Gevinstsaldo gir inntektsføring, ikke tapsfradrag.')
        income = (basis if basis < SMALL_SALDO_THRESHOLD else basis * Decimal('0.20')) + extra
        if income > basis:
            raise RuleValidationError('Inntektsføringen overstiger gevinstsaldoen.')
    elif basis < 0:
        if extra:
            raise RuleValidationError('Ekstra inntektsføring krever gevinstsaldo.')
        loss = -basis
        if write_off_small and loss >= SMALL_SALDO_THRESHOLD:
            raise RuleValidationError('Fullt tapsfradrag krever saldo under 30 000 kroner.')
        maximum = loss if write_off_small else loss * Decimal('0.20')
        deduction = maximum if requested_deduction is None else _decimal_amount(requested_deduction, 'Valgt tapsfradrag')
        if deduction > maximum:
            raise RuleValidationError('Tapsfradraget overstiger årets maksimum.')
    elif extra or write_off_small or requested_deduction not in (None, Decimal('0')):
        raise RuleValidationError('Null saldo gir ingen årsjustering.')
    return GainLossResult(opening, transfers, basis, income, deduction, basis - income + deduction)
