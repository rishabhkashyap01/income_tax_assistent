"""
Tax Computation Engine
======================
Pure Python tax calculation for AY 2025-26 (FY 2024-25).
Both Old and New regimes, surcharge, cess, rebate, regime comparison.
"""

from __future__ import annotations
from src.itr_models import ITRFiling, Deductions


# ---------------------------------------------------------------------------
# Tax Slabs — AY 2025-26
# ---------------------------------------------------------------------------

NEW_REGIME_SLABS = [
    (300000, 0.00),
    (400000, 0.05),  # 3L - 7L
    (300000, 0.10),  # 7L - 10L
    (200000, 0.15),  # 10L - 12L
    (300000, 0.20),  # 12L - 15L
    (float("inf"), 0.30),  # 15L+
]

OLD_REGIME_SLABS = {
    "below_60": [
        (250000, 0.00),
        (250000, 0.05),  # 2.5L - 5L
        (500000, 0.20),  # 5L - 10L
        (float("inf"), 0.30),  # 10L+
    ],
    "senior_60_80": [
        (300000, 0.00),
        (200000, 0.05),  # 3L - 5L
        (500000, 0.20),  # 5L - 10L
        (float("inf"), 0.30),  # 10L+
    ],
    "super_senior_80": [
        (500000, 0.00),
        (500000, 0.20),  # 5L - 10L
        (float("inf"), 0.30),  # 10L+
    ],
}

SURCHARGE_SLABS = [
    (5000000, 0.00),
    (5000000, 0.10),   # 50L - 1Cr
    (10000000, 0.15),  # 1Cr - 2Cr
    (30000000, 0.25),  # 2Cr - 5Cr
    (float("inf"), 0.37),  # 5Cr+ (old regime)
]

# New regime caps surcharge at 25% for income above 5Cr
SURCHARGE_SLABS_NEW = [
    (5000000, 0.00),
    (5000000, 0.10),
    (10000000, 0.15),
    (30000000, 0.25),
    (float("inf"), 0.25),  # Capped at 25%
]

CESS_RATE = 0.04

# Rebate u/s 87A
REBATE_87A_NEW = {"limit": 700000, "max_rebate": 25000}
REBATE_87A_OLD = {"limit": 500000, "max_rebate": 12500}

# Standard deduction
STANDARD_DEDUCTION_NEW = 75000
STANDARD_DEDUCTION_OLD = 50000


# ---------------------------------------------------------------------------
# Core Tax Computation
# ---------------------------------------------------------------------------

def _compute_tax_from_slabs(taxable_income: float, slabs: list[tuple]) -> float:
    """Apply progressive tax slabs to taxable income."""
    tax = 0.0
    remaining = taxable_income
    for slab_amount, rate in slabs:
        if remaining <= 0:
            break
        taxable_in_slab = min(remaining, slab_amount)
        tax += taxable_in_slab * rate
        remaining -= taxable_in_slab
    return tax


def compute_tax_new_regime(taxable_income: float) -> dict:
    """Compute tax under new regime for AY 2025-26."""
    tax = _compute_tax_from_slabs(taxable_income, NEW_REGIME_SLABS)

    # Rebate u/s 87A
    rebate = 0.0
    if taxable_income <= REBATE_87A_NEW["limit"]:
        rebate = min(tax, REBATE_87A_NEW["max_rebate"])

    tax_after_rebate = tax - rebate

    # Surcharge
    surcharge = _compute_surcharge(tax_after_rebate, taxable_income, regime="new")

    # Cess
    cess = (tax_after_rebate + surcharge) * CESS_RATE

    total = tax_after_rebate + surcharge + cess

    return {
        "taxable_income": taxable_income,
        "tax_on_income": round(tax, 2),
        "rebate_87a": round(rebate, 2),
        "tax_after_rebate": round(tax_after_rebate, 2),
        "surcharge": round(surcharge, 2),
        "cess": round(cess, 2),
        "total_tax": round(total, 2),
    }


def compute_tax_old_regime(taxable_income: float, age: int = 30) -> dict:
    """Compute tax under old regime for AY 2025-26."""
    if age >= 80:
        slabs = OLD_REGIME_SLABS["super_senior_80"]
    elif age >= 60:
        slabs = OLD_REGIME_SLABS["senior_60_80"]
    else:
        slabs = OLD_REGIME_SLABS["below_60"]

    tax = _compute_tax_from_slabs(taxable_income, slabs)

    # Rebate u/s 87A
    rebate = 0.0
    if taxable_income <= REBATE_87A_OLD["limit"]:
        rebate = min(tax, REBATE_87A_OLD["max_rebate"])

    tax_after_rebate = tax - rebate

    # Surcharge
    surcharge = _compute_surcharge(tax_after_rebate, taxable_income, regime="old")

    # Cess
    cess = (tax_after_rebate + surcharge) * CESS_RATE

    total = tax_after_rebate + surcharge + cess

    return {
        "taxable_income": taxable_income,
        "tax_on_income": round(tax, 2),
        "rebate_87a": round(rebate, 2),
        "tax_after_rebate": round(tax_after_rebate, 2),
        "surcharge": round(surcharge, 2),
        "cess": round(cess, 2),
        "total_tax": round(total, 2),
    }


def _compute_surcharge(tax: float, total_income: float, regime: str = "new") -> float:
    """Compute surcharge based on total income."""
    slabs = SURCHARGE_SLABS_NEW if regime == "new" else SURCHARGE_SLABS
    remaining = total_income
    for slab_limit, rate in slabs:
        if remaining <= slab_limit:
            return tax * rate
        remaining -= slab_limit
    # Shouldn't reach here, but fallback
    return tax * slabs[-1][1]


# ---------------------------------------------------------------------------
# Gross Total Income
# ---------------------------------------------------------------------------

def compute_gross_total_income(filing: ITRFiling) -> float:
    """Compute GTI from all income heads."""
    # 1. Salary income (net of exempt allowances, std deduction, prof tax)
    salary_net = filing.salary.net_salary

    # 2. House property income
    hp_income = sum(hp.net_income for hp in filing.house_property)

    # 3. Other income
    other = filing.other_income.total

    # 4. Capital gains (ITR-2, ITR-3)
    cg_slab = 0.0
    if filing.capital_gains:
        cg_slab = filing.capital_gains.stcg_slab

    # 5. Business income (ITR-3, ITR-4)
    biz = 0.0
    if filing.business_income:
        if filing.form_type == "ITR-4":
            biz = filing.business_income.presumptive_income
        else:
            biz = filing.business_income.net_profit

    gti = salary_net + hp_income + other + cg_slab + biz
    return max(gti, 0.0)


def compute_special_rate_tax(filing: ITRFiling) -> float:
    """Tax on capital gains at special rates (not slab-based)."""
    if not filing.capital_gains:
        return 0.0
    cg = filing.capital_gains
    tax = 0.0
    tax += cg.stcg_15 * 0.15  # Sec 111A
    # LTCG u/s 112A: exempt up to 1.25L, then 10%
    ltcg_112a_taxable = max(cg.ltcg_10 - 125000, 0.0)
    tax += ltcg_112a_taxable * 0.10
    tax += cg.ltcg_20 * 0.20  # Sec 112
    return tax


# ---------------------------------------------------------------------------
# Regime Comparison
# ---------------------------------------------------------------------------

def compare_regimes(filing: ITRFiling, age: int = 30) -> dict:
    """Compare old vs new regime and recommend the better one."""
    gti = compute_gross_total_income(filing)
    special_tax = compute_special_rate_tax(filing)

    # New regime
    new_std_ded = STANDARD_DEDUCTION_NEW
    new_deductions = filing.deductions.total_new_regime
    new_taxable = max(gti - new_deductions, 0.0)
    # Adjust salary standard deduction for new regime
    filing.salary.standard_deduction = new_std_ded
    new_gti = compute_gross_total_income(filing)
    new_taxable = max(new_gti - new_deductions, 0.0)
    new_result = compute_tax_new_regime(new_taxable)
    new_result["total_tax"] = round(new_result["total_tax"] + special_tax, 2)

    # Old regime
    old_std_ded = STANDARD_DEDUCTION_OLD
    filing.salary.standard_deduction = old_std_ded
    old_gti = compute_gross_total_income(filing)
    old_deductions = filing.deductions.total_old_regime
    old_taxable = max(old_gti - old_deductions, 0.0)
    old_result = compute_tax_old_regime(old_taxable, age)
    old_result["total_tax"] = round(old_result["total_tax"] + special_tax, 2)

    # Restore standard deduction based on current regime
    if filing.regime == "new":
        filing.salary.standard_deduction = new_std_ded
    else:
        filing.salary.standard_deduction = old_std_ded

    # Recommendation
    saving = old_result["total_tax"] - new_result["total_tax"]
    if saving > 0:
        recommendation = f"New Regime saves you Rs. {saving:,.0f}"
        recommended = "new"
    elif saving < 0:
        recommendation = f"Old Regime saves you Rs. {-saving:,.0f}"
        recommended = "old"
    else:
        recommendation = "Both regimes result in the same tax"
        recommended = "new"

    return {
        "new_regime": new_result,
        "old_regime": old_result,
        "new_deductions": round(new_deductions, 2),
        "old_deductions": round(old_deductions, 2),
        "saving": round(abs(saving), 2),
        "recommendation": recommendation,
        "recommended_regime": recommended,
    }


# ---------------------------------------------------------------------------
# Net Tax Payable / Refund
# ---------------------------------------------------------------------------

def compute_net_tax_payable(filing: ITRFiling, age: int = 30) -> dict:
    """Final tax computation: tax liability minus taxes already paid."""
    gti = compute_gross_total_income(filing)
    special_tax = compute_special_rate_tax(filing)

    if filing.regime == "new":
        deductions = filing.deductions.total_new_regime
        taxable = max(gti - deductions, 0.0)
        result = compute_tax_new_regime(taxable)
    else:
        deductions = filing.deductions.total_old_regime
        taxable = max(gti - deductions, 0.0)
        result = compute_tax_old_regime(taxable, age)

    total_tax = result["total_tax"] + special_tax
    total_paid = filing.tax_payments.total_paid
    net_payable = total_tax - total_paid

    return {
        "gross_total_income": round(gti, 2),
        "deductions": round(deductions, 2),
        "taxable_income": round(taxable, 2),
        "tax_breakdown": result,
        "special_rate_tax": round(special_tax, 2),
        "total_tax_liability": round(total_tax, 2),
        "total_tax_paid": round(total_paid, 2),
        "net_payable": round(net_payable, 2),
        "status": "refund" if net_payable < 0 else "payable",
        "amount": round(abs(net_payable), 2),
    }


def format_currency(amount: float) -> str:
    """Format amount in Indian currency style (e.g., 12,50,000)."""
    if amount < 0:
        return f"-{format_currency(-amount)}"
    s = f"{amount:,.0f}"
    # Convert international format to Indian format
    parts = s.split(",")
    if len(parts) <= 2:
        return s
    # Indian: last 3 digits, then groups of 2
    last_three = parts[-1]
    rest = ",".join(parts[:-1])
    # Re-join with Indian grouping
    rest_digits = rest.replace(",", "")
    indian_groups = []
    while len(rest_digits) > 2:
        indian_groups.insert(0, rest_digits[-2:])
        rest_digits = rest_digits[:-2]
    if rest_digits:
        indian_groups.insert(0, rest_digits)
    return ",".join(indian_groups) + "," + last_three
