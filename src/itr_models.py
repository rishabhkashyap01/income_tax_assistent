"""
ITR Data Models
===============
Dataclasses for all ITR form data. Shared across forms with form-specific extensions.
Supports serialization to/from dict for JSON persistence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime


@dataclass
class PersonalInfo:
    pan: str = ""
    name: str = ""
    dob: str = ""  # DD/MM/YYYY
    aadhaar: str = ""
    address: str = ""
    pincode: str = ""
    email: str = ""
    mobile: str = ""
    residential_status: str = "resident"  # resident / non_resident / rnor
    filing_status: str = "original"  # original / revised / belated


@dataclass
class SalaryIncome:
    gross_salary: float = 0.0
    exempt_allowances: dict = field(default_factory=lambda: {
        "hra": 0.0, "lta": 0.0, "other": 0.0
    })
    standard_deduction: float = 0.0  # Computed based on regime
    professional_tax: float = 0.0
    employer_name: str = ""
    employer_tan: str = ""

    @property
    def net_salary(self) -> float:
        total_exempt = sum(self.exempt_allowances.values())
        return self.gross_salary - total_exempt - self.standard_deduction - self.professional_tax


@dataclass
class HousePropertyIncome:
    property_type: str = "self_occupied"  # self_occupied / let_out / deemed_let_out
    rental_income: float = 0.0
    municipal_tax: float = 0.0
    home_loan_interest: float = 0.0  # Sec 24(b)

    @property
    def net_income(self) -> float:
        if self.property_type == "self_occupied":
            # Only home loan interest deduction, capped at 2L for self-occupied
            return -min(self.home_loan_interest, 200000.0)
        # Let out: GAV - municipal tax - 30% standard deduction - interest
        nav = self.rental_income - self.municipal_tax
        standard_deduction = nav * 0.30
        return nav - standard_deduction - self.home_loan_interest


@dataclass
class OtherIncome:
    savings_interest: float = 0.0
    fd_interest: float = 0.0
    dividend_income: float = 0.0
    family_pension: float = 0.0
    agricultural_income: float = 0.0  # Up to 5000 for ITR-1
    other: float = 0.0

    @property
    def total(self) -> float:
        # Family pension gets 1/3 or 15000 deduction (Sec 57)
        fp_deduction = min(self.family_pension / 3, 15000.0) if self.family_pension > 0 else 0.0
        return (
            self.savings_interest + self.fd_interest + self.dividend_income
            + (self.family_pension - fp_deduction) + self.other
        )


@dataclass
class CapitalGains:
    """For ITR-2 and ITR-3."""
    stcg_15: float = 0.0  # Short-term at 15% (Sec 111A)
    stcg_slab: float = 0.0  # Short-term at slab rate
    ltcg_10: float = 0.0  # Long-term at 10% — listed equity (Sec 112A)
    ltcg_20: float = 0.0  # Long-term at 20% with indexation (Sec 112)


@dataclass
class BusinessIncome:
    """For ITR-3 and ITR-4."""
    business_type: str = ""  # business / profession
    gross_turnover: float = 0.0
    presumptive_income: float = 0.0  # For ITR-4 (Sec 44AD/44ADA)
    net_profit: float = 0.0  # For ITR-3 (from P&L)
    presumptive_scheme: str = ""  # 44AD / 44ADA / 44AE


@dataclass
class Deductions:
    sec_80c: float = 0.0  # Max 1.5L (EPF, PPF, ELSS, LIC, etc.)
    sec_80ccc: float = 0.0  # Pension fund (combined with 80C limit)
    sec_80ccd_1: float = 0.0  # Employee NPS (combined with 80C limit)
    sec_80ccd_1b: float = 0.0  # Additional NPS, max 50K
    sec_80ccd_2: float = 0.0  # Employer NPS (no cap, available in both regimes)
    sec_80d_self: float = 0.0  # Health insurance self+family
    sec_80d_parents: float = 0.0  # Health insurance parents
    sec_80dd: float = 0.0  # Disabled dependent
    sec_80ddb: float = 0.0  # Specified diseases
    sec_80e: float = 0.0  # Education loan interest (no cap)
    sec_80ee: float = 0.0  # Additional home loan interest (first-time, max 50K)
    sec_80eea: float = 0.0  # Affordable housing interest (max 1.5L)
    sec_80eeb: float = 0.0  # EV loan interest (max 1.5L)
    sec_80g: float = 0.0  # Donations
    sec_80gg: float = 0.0  # Rent paid (no HRA)
    sec_80tta: float = 0.0  # Savings interest, max 10K
    sec_80ttb: float = 0.0  # Senior citizen deposit interest, max 50K
    sec_80u: float = 0.0  # Disabled individual

    @property
    def total_80c_group(self) -> float:
        """80C + 80CCC + 80CCD(1) combined limit of 1.5L."""
        return min(self.sec_80c + self.sec_80ccc + self.sec_80ccd_1, 150000.0)

    @property
    def total_old_regime(self) -> float:
        """Total deductions available under old regime."""
        return (
            self.total_80c_group
            + self.sec_80ccd_1b
            + self.sec_80ccd_2
            + self.sec_80d_self + self.sec_80d_parents
            + self.sec_80dd + self.sec_80ddb
            + self.sec_80e + self.sec_80ee + self.sec_80eea + self.sec_80eeb
            + self.sec_80g + self.sec_80gg
            + self.sec_80tta + self.sec_80ttb + self.sec_80u
        )

    @property
    def total_new_regime(self) -> float:
        """Only employer NPS (80CCD(2)) is available in new regime."""
        return self.sec_80ccd_2


@dataclass
class TaxPayments:
    tds_salary: float = 0.0
    tds_other: float = 0.0
    tcs: float = 0.0
    advance_tax: float = 0.0
    self_assessment_tax: float = 0.0

    @property
    def total_paid(self) -> float:
        return (
            self.tds_salary + self.tds_other + self.tcs
            + self.advance_tax + self.self_assessment_tax
        )


@dataclass
class BankAccount:
    bank_name: str = ""
    ifsc: str = ""
    account_number: str = ""
    is_refund_account: bool = False


@dataclass
class ITRFiling:
    form_type: str = ""  # ITR-1, ITR-2, ITR-3, ITR-4
    assessment_year: str = "2025-26"
    regime: str = "new"  # old / new
    personal: PersonalInfo = field(default_factory=PersonalInfo)
    salary: SalaryIncome = field(default_factory=SalaryIncome)
    house_property: list = field(default_factory=list)  # list of HousePropertyIncome
    other_income: OtherIncome = field(default_factory=OtherIncome)
    capital_gains: CapitalGains | None = None
    business_income: BusinessIncome | None = None
    deductions: Deductions = field(default_factory=Deductions)
    tax_payments: TaxPayments = field(default_factory=TaxPayments)
    bank_accounts: list = field(default_factory=list)  # list of BankAccount
    current_step: str = "welcome"
    completed_steps: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ITRFiling:
        filing = cls()
        filing.form_type = data.get("form_type", "")
        filing.assessment_year = data.get("assessment_year", "2025-26")
        filing.regime = data.get("regime", "new")
        filing.current_step = data.get("current_step", "welcome")
        filing.completed_steps = data.get("completed_steps", [])
        filing.created_at = data.get("created_at", datetime.now().isoformat())
        filing.updated_at = data.get("updated_at", datetime.now().isoformat())

        if "personal" in data:
            filing.personal = PersonalInfo(**data["personal"])
        if "salary" in data:
            filing.salary = SalaryIncome(**data["salary"])
        if "house_property" in data:
            filing.house_property = [HousePropertyIncome(**hp) for hp in data["house_property"]]
        if "other_income" in data:
            filing.other_income = OtherIncome(**data["other_income"])
        if data.get("capital_gains"):
            filing.capital_gains = CapitalGains(**data["capital_gains"])
        if data.get("business_income"):
            filing.business_income = BusinessIncome(**data["business_income"])
        if "deductions" in data:
            filing.deductions = Deductions(**data["deductions"])
        if "tax_payments" in data:
            filing.tax_payments = TaxPayments(**data["tax_payments"])
        if "bank_accounts" in data:
            filing.bank_accounts = [BankAccount(**ba) for ba in data["bank_accounts"]]

        return filing
