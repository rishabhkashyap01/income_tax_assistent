"""
Filing Engine
=============
LLM-driven conversational ITR filing flow.
Manages the state machine, sends step-specific prompts to Groq,
parses extracted data from LLM responses, and advances the flow.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dotenv import load_dotenv

from src.itr_models import (
    ITRFiling, PersonalInfo, SalaryIncome, HousePropertyIncome,
    OtherIncome, CapitalGains, BusinessIncome, Deductions,
    TaxPayments, BankAccount,
)
from src.itr_prompts import (
    FILING_STEPS, STEP_LABELS, DATA_START, DATA_END, get_step_prompt,
)
from src.tax_engine import (
    compare_regimes, compute_net_tax_payable, format_currency,
    STANDARD_DEDUCTION_NEW, STANDARD_DEDUCTION_OLD,
)

load_dotenv()

GROQ_MODEL = "llama-3.3-70b-versatile"


def _get_llm():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found. Check your .env file!")
    return ChatGroq(
        model=GROQ_MODEL,
        temperature=0.1,
        groq_api_key=api_key,
        max_tokens=1024,
    )


def _parse_extracted_data(response_text: str) -> dict | None:
    """Extract JSON data between <<<EXTRACTED_DATA>>> and <<<END_DATA>>> markers."""
    pattern = re.compile(
        re.escape(DATA_START) + r"\s*(.*?)\s*" + re.escape(DATA_END),
        re.DOTALL,
    )
    match = pattern.search(response_text)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _clean_response(response_text: str) -> str:
    """Remove the data extraction block and truncate any repetition loops."""
    # Remove extraction markers
    pattern = re.compile(
        re.escape(DATA_START) + r".*?" + re.escape(DATA_END),
        re.DOTALL,
    )
    cleaned = pattern.sub("", response_text).strip()

    # Detect and truncate repetition loops
    # Split into paragraphs and find the first repeated block
    paragraphs = cleaned.split("\n\n")
    if len(paragraphs) > 4:
        seen = set()
        cut_index = len(paragraphs)
        for i, para in enumerate(paragraphs):
            # Normalize whitespace for comparison
            key = " ".join(para.split()).strip()
            if len(key) < 20:
                continue  # Skip short lines (headers, etc.)
            if key in seen:
                cut_index = i
                break
            seen.add(key)
        if cut_index < len(paragraphs):
            cleaned = "\n\n".join(paragraphs[:cut_index]).strip()

    return cleaned


def _build_filing_summary(filing: ITRFiling) -> str:
    """Build a text summary of the current filing state for the LLM."""
    lines = []
    lines.append(f"**Form:** {filing.form_type} | **AY:** {filing.assessment_year} | **Regime:** {filing.regime.upper()}")

    if filing.personal.pan:
        p = filing.personal
        lines.append(f"\n**Personal:** {p.name} | PAN: {p.pan} | DOB: {p.dob}")

    if filing.salary.gross_salary > 0:
        s = filing.salary
        lines.append(f"\n**Salary:** Gross Rs. {format_currency(s.gross_salary)} | Net Rs. {format_currency(s.net_salary)}")

    if filing.house_property:
        for hp in filing.house_property:
            lines.append(f"\n**House Property ({hp.property_type}):** Net Rs. {format_currency(hp.net_income)}")

    if filing.other_income.total > 0:
        lines.append(f"\n**Other Income:** Rs. {format_currency(filing.other_income.total)}")

    if filing.capital_gains:
        cg = filing.capital_gains
        total_cg = cg.stcg_15 + cg.stcg_slab + cg.ltcg_10 + cg.ltcg_20
        if total_cg > 0:
            lines.append(f"\n**Capital Gains:** Total Rs. {format_currency(total_cg)}")

    if filing.business_income:
        bi = filing.business_income
        if filing.form_type == "ITR-4":
            lines.append(f"\n**Business ({bi.presumptive_scheme}):** Turnover Rs. {format_currency(bi.gross_turnover)} | Income Rs. {format_currency(bi.presumptive_income)}")
        elif bi.net_profit > 0:
            lines.append(f"\n**Business:** Net Profit Rs. {format_currency(bi.net_profit)}")

    return "\n".join(lines)


def _build_tax_computation_text(filing: ITRFiling) -> str:
    """Build tax computation result text for the tax_computation step."""
    comparison = compare_regimes(filing, age=_estimate_age(filing.personal.dob))
    net = compute_net_tax_payable(filing, age=_estimate_age(filing.personal.dob))

    lines = []
    lines.append("## Tax Computation Results\n")
    lines.append(f"**Gross Total Income:** Rs. {format_currency(net['gross_total_income'])}")
    lines.append(f"**Deductions ({filing.regime.upper()} regime):** Rs. {format_currency(net['deductions'])}")
    lines.append(f"**Taxable Income:** Rs. {format_currency(net['taxable_income'])}")
    lines.append(f"**Tax on Income:** Rs. {format_currency(net['tax_breakdown']['tax_on_income'])}")
    lines.append(f"**Rebate u/s 87A:** Rs. {format_currency(net['tax_breakdown']['rebate_87a'])}")
    lines.append(f"**Surcharge:** Rs. {format_currency(net['tax_breakdown']['surcharge'])}")
    lines.append(f"**Cess (4%):** Rs. {format_currency(net['tax_breakdown']['cess'])}")
    lines.append(f"**Total Tax Liability:** Rs. {format_currency(net['total_tax_liability'])}")

    lines.append("\n## Regime Comparison\n")
    lines.append(f"| | New Regime | Old Regime |")
    lines.append(f"|---|---|---|")
    lines.append(f"| Deductions | Rs. {format_currency(comparison['new_deductions'])} | Rs. {format_currency(comparison['old_deductions'])} |")
    lines.append(f"| Taxable Income | Rs. {format_currency(comparison['new_regime']['taxable_income'])} | Rs. {format_currency(comparison['old_regime']['taxable_income'])} |")
    lines.append(f"| Total Tax | Rs. {format_currency(comparison['new_regime']['total_tax'])} | Rs. {format_currency(comparison['old_regime']['total_tax'])} |")
    lines.append(f"\n**Recommendation:** {comparison['recommendation']}")

    return "\n".join(lines)


def _estimate_age(dob: str) -> int:
    """Estimate age from DOB string (DD/MM/YYYY)."""
    if not dob:
        return 30
    try:
        parts = dob.split("/")
        birth_year = int(parts[2])
        # AY 2025-26 = FY 2024-25, age as of 31 March 2025
        return 2025 - birth_year
    except (IndexError, ValueError):
        return 30


# ---------------------------------------------------------------------------
# Core: Process a filing message
# ---------------------------------------------------------------------------

def get_next_step(filing: ITRFiling) -> str | None:
    """Get the next step in the filing flow."""
    steps = FILING_STEPS.get(filing.form_type, FILING_STEPS["ITR-1"])
    current_idx = -1
    if filing.current_step in steps:
        current_idx = steps.index(filing.current_step)
    next_idx = current_idx + 1
    if next_idx < len(steps):
        return steps[next_idx]
    return None


def advance_step(filing: ITRFiling) -> str | None:
    """Mark current step as completed and move to the next one."""
    if filing.current_step not in filing.completed_steps:
        filing.completed_steps.append(filing.current_step)
    next_step = get_next_step(filing)
    if next_step:
        filing.current_step = next_step
    filing.updated_at = datetime.now().isoformat()
    return next_step


def _apply_extracted_data(filing: ITRFiling, step: str, data: dict):
    """Apply extracted data from a step to the filing model."""
    if step == "welcome":
        pass  # Nothing to store

    elif step == "form_selection":
        filing.form_type = data.get("form_type", "ITR-1")
        # Initialize form-specific fields
        if filing.form_type in ("ITR-2", "ITR-3"):
            filing.capital_gains = CapitalGains()
        if filing.form_type in ("ITR-3", "ITR-4"):
            filing.business_income = BusinessIncome()

    elif step == "personal_info":
        filing.personal = PersonalInfo(
            pan=data.get("pan", ""),
            name=data.get("name", ""),
            dob=data.get("dob", ""),
            aadhaar=data.get("aadhaar", ""),
            email=data.get("email", ""),
            mobile=data.get("mobile", ""),
            address=data.get("address", ""),
            pincode=data.get("pincode", ""),
            residential_status=data.get("residential_status", "resident"),
            filing_status=data.get("filing_status", "original"),
        )

    elif step == "regime_selection":
        filing.regime = data.get("regime", "new")
        # Set standard deduction based on regime
        if filing.regime == "new":
            filing.salary.standard_deduction = STANDARD_DEDUCTION_NEW
        else:
            filing.salary.standard_deduction = STANDARD_DEDUCTION_OLD

    elif step == "salary_income":
        ea = data.get("exempt_allowances", {})
        filing.salary = SalaryIncome(
            gross_salary=float(data.get("gross_salary", 0)),
            exempt_allowances={
                "hra": float(ea.get("hra", 0)),
                "lta": float(ea.get("lta", 0)),
                "other": float(ea.get("other", 0)),
            },
            standard_deduction=filing.salary.standard_deduction,
            professional_tax=float(data.get("professional_tax", 0)),
            employer_name=data.get("employer_name", ""),
            employer_tan=data.get("employer_tan", ""),
        )

    elif step == "house_property":
        filing.house_property = []
        for prop in data.get("properties", []):
            filing.house_property.append(HousePropertyIncome(
                property_type=prop.get("property_type", "self_occupied"),
                rental_income=float(prop.get("rental_income", 0)),
                municipal_tax=float(prop.get("municipal_tax", 0)),
                home_loan_interest=float(prop.get("home_loan_interest", 0)),
            ))

    elif step == "other_income":
        filing.other_income = OtherIncome(
            savings_interest=float(data.get("savings_interest", 0)),
            fd_interest=float(data.get("fd_interest", 0)),
            dividend_income=float(data.get("dividend_income", 0)),
            family_pension=float(data.get("family_pension", 0)),
            agricultural_income=float(data.get("agricultural_income", 0)),
            other=float(data.get("other", 0)),
        )

    elif step == "capital_gains":
        filing.capital_gains = CapitalGains(
            stcg_15=float(data.get("stcg_15", 0)),
            stcg_slab=float(data.get("stcg_slab", 0)),
            ltcg_10=float(data.get("ltcg_10", 0)),
            ltcg_20=float(data.get("ltcg_20", 0)),
        )

    elif step in ("business_income", "presumptive_income"):
        filing.business_income = BusinessIncome(
            business_type=data.get("business_type", ""),
            gross_turnover=float(data.get("gross_turnover", 0)),
            presumptive_income=float(data.get("presumptive_income", 0)),
            net_profit=float(data.get("net_profit", 0)),
            presumptive_scheme=data.get("presumptive_scheme", ""),
        )

    elif step == "deductions":
        filing.deductions = Deductions(
            sec_80c=float(data.get("sec_80c", 0)),
            sec_80ccc=float(data.get("sec_80ccc", 0)),
            sec_80ccd_1=float(data.get("sec_80ccd_1", 0)),
            sec_80ccd_1b=float(data.get("sec_80ccd_1b", 0)),
            sec_80ccd_2=float(data.get("sec_80ccd_2", 0)),
            sec_80d_self=float(data.get("sec_80d_self", 0)),
            sec_80d_parents=float(data.get("sec_80d_parents", 0)),
            sec_80dd=float(data.get("sec_80dd", 0)),
            sec_80ddb=float(data.get("sec_80ddb", 0)),
            sec_80e=float(data.get("sec_80e", 0)),
            sec_80ee=float(data.get("sec_80ee", 0)),
            sec_80eea=float(data.get("sec_80eea", 0)),
            sec_80eeb=float(data.get("sec_80eeb", 0)),
            sec_80g=float(data.get("sec_80g", 0)),
            sec_80gg=float(data.get("sec_80gg", 0)),
            sec_80tta=float(data.get("sec_80tta", 0)),
            sec_80ttb=float(data.get("sec_80ttb", 0)),
            sec_80u=float(data.get("sec_80u", 0)),
        )

    elif step == "tax_computation":
        # User may have switched regimes
        if "regime" in data:
            filing.regime = data["regime"]

    elif step == "tax_payments":
        filing.tax_payments = TaxPayments(
            tds_salary=float(data.get("tds_salary", 0)),
            tds_other=float(data.get("tds_other", 0)),
            tcs=float(data.get("tcs", 0)),
            advance_tax=float(data.get("advance_tax", 0)),
            self_assessment_tax=float(data.get("self_assessment_tax", 0)),
        )

    elif step == "bank_details":
        filing.bank_accounts = []
        for acc in data.get("accounts", []):
            filing.bank_accounts.append(BankAccount(
                bank_name=acc.get("bank_name", ""),
                ifsc=acc.get("ifsc", ""),
                account_number=acc.get("account_number", ""),
                is_refund_account=acc.get("is_refund_account", False),
            ))

    elif step == "summary":
        pass  # Just confirmation


def process_filing_message(
    user_message: str,
    filing: ITRFiling,
    chat_history: list[dict],
    rag_context: str = "",
) -> tuple[str, ITRFiling, bool]:
    """Process a user message in the filing flow.

    Args:
        user_message: The user's chat message.
        filing: Current ITR filing state.
        chat_history: List of {"role": ..., "content": ...} dicts.
        rag_context: Optional retrieved context from RAG for answering tax questions.

    Returns:
        (assistant_response, updated_filing, step_advanced)
    """
    llm = _get_llm()
    step = filing.current_step

    # Build step-specific system prompt
    prompt_kwargs = {
        "form_type": filing.form_type or "ITR-1",
        "regime": filing.regime,
    }

    # Inject computed data for special steps
    if step == "tax_computation":
        prompt_kwargs["tax_computation_result"] = _build_tax_computation_text(filing)
    elif step == "summary":
        prompt_kwargs["filing_summary"] = _build_full_summary(filing)

    system_prompt = get_step_prompt(step, **prompt_kwargs)

    # Add filing context to system prompt
    if filing.personal.pan:
        system_prompt += f"\n\nCurrent filing state:\n{_build_filing_summary(filing)}"

    # Global instructions appended to every step prompt
    system_prompt += (
        "\n\nIMPORTANT RULES:"
        "\n1. If the user asks a question about tax concepts, rules, sections, "
        "or anything related to income tax — answer it clearly using your knowledge "
        "and any reference context provided below. Then gently guide them back to the "
        "current filing step. Do NOT say you don't have the information."
        "\n2. When you have collected all data for this step and are ready to output the "
        "extraction block — you MUST first show the user a clear, readable summary of "
        "what you collected. Use bullet points or a table. For example:"
        "\n   'Here's what I've recorded:"
        "\n   - Gross Salary: Rs. 12,00,000"
        "\n   - HRA Exemption: Rs. 1,20,000"
        "\n   - Professional Tax: Rs. 2,400'"
        "\n   Then ask 'Does this look correct?' and include the extraction block AFTER "
        "the readable summary. The extraction block will be hidden from the user, but "
        "your readable summary above it will be visible."
        "\n3. You are an expert Indian tax assistant with deep knowledge of the Income Tax "
        "Act 1961 and Income Tax Rules 1962."
    )

    # Inject RAG context if available
    if rag_context:
        system_prompt += (
            f"\n\nReference context from the Income Tax Act & Rules "
            f"(use this to answer the user's question):\n\n{rag_context}"
        )

    # Build LangChain messages — limit history to avoid token overflow & repetition
    messages = [SystemMessage(content=system_prompt)]
    for msg in chat_history[-10:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            # Truncate long assistant messages in history to save tokens
            content = msg["content"]
            if len(content) > 500:
                content = content[:500] + "..."
            messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_message))

    # Call LLM
    response = llm.invoke(messages)
    response_text = response.content

    # Parse extracted data
    extracted = _parse_extracted_data(response_text)
    step_advanced = False

    if extracted:
        _apply_extracted_data(filing, step, extracted)
        next_step = advance_step(filing)
        step_advanced = True

        # If we just advanced to tax_computation or summary, auto-generate intro
        if next_step in ("tax_computation", "summary"):
            # The next call will pick up the computed data
            pass

    # Clean response (remove data blocks from visible text)
    visible_response = _clean_response(response_text)

    return visible_response, filing, step_advanced


def _build_full_summary(filing: ITRFiling) -> str:
    """Build complete filing summary for the summary step."""
    net = compute_net_tax_payable(filing, age=_estimate_age(filing.personal.dob))
    comparison = compare_regimes(filing, age=_estimate_age(filing.personal.dob))

    lines = []
    lines.append(f"## ITR Filing Summary — {filing.form_type} (AY {filing.assessment_year})\n")

    # Personal
    p = filing.personal
    lines.append(f"**Name:** {p.name}")
    lines.append(f"**PAN:** {p.pan} | **Aadhaar:** {p.aadhaar}")
    lines.append(f"**DOB:** {p.dob} | **Regime:** {filing.regime.upper()}")

    # Income
    lines.append(f"\n### Income Summary")
    if filing.salary.gross_salary > 0:
        lines.append(f"- Salary (Gross): Rs. {format_currency(filing.salary.gross_salary)}")
        lines.append(f"- Salary (Net after deductions): Rs. {format_currency(filing.salary.net_salary)}")
    if filing.house_property:
        for hp in filing.house_property:
            lines.append(f"- House Property ({hp.property_type}): Rs. {format_currency(hp.net_income)}")
    if filing.other_income.total > 0:
        lines.append(f"- Other Income: Rs. {format_currency(filing.other_income.total)}")
    if filing.capital_gains:
        cg = filing.capital_gains
        total_cg = cg.stcg_15 + cg.stcg_slab + cg.ltcg_10 + cg.ltcg_20
        if total_cg > 0:
            lines.append(f"- Capital Gains: Rs. {format_currency(total_cg)}")
    if filing.business_income:
        bi = filing.business_income
        if filing.form_type == "ITR-4":
            lines.append(f"- Business Income ({bi.presumptive_scheme}): Rs. {format_currency(bi.presumptive_income)}")
        elif bi.net_profit > 0:
            lines.append(f"- Business Net Profit: Rs. {format_currency(bi.net_profit)}")

    lines.append(f"\n**Gross Total Income:** Rs. {format_currency(net['gross_total_income'])}")

    # Deductions
    lines.append(f"\n### Deductions")
    lines.append(f"- Total Deductions: Rs. {format_currency(net['deductions'])}")

    # Tax
    lines.append(f"\n### Tax Computation")
    lines.append(f"- Taxable Income: Rs. {format_currency(net['taxable_income'])}")
    lines.append(f"- Tax Liability: Rs. {format_currency(net['total_tax_liability'])}")
    lines.append(f"- Taxes Already Paid: Rs. {format_currency(net['total_tax_paid'])}")

    if net["status"] == "refund":
        lines.append(f"\n### **Refund Due: Rs. {format_currency(net['amount'])}**")
    else:
        lines.append(f"\n### **Tax Payable: Rs. {format_currency(net['amount'])}**")

    # Bank
    if filing.bank_accounts:
        refund_acc = next((a for a in filing.bank_accounts if a.is_refund_account), filing.bank_accounts[0])
        lines.append(f"\n**Refund to:** {refund_acc.bank_name} ({refund_acc.account_number})")

    # Regime comparison
    lines.append(f"\n### Regime Comparison")
    lines.append(f"- New Regime Tax: Rs. {format_currency(comparison['new_regime']['total_tax'])}")
    lines.append(f"- Old Regime Tax: Rs. {format_currency(comparison['old_regime']['total_tax'])}")
    lines.append(f"- **{comparison['recommendation']}**")

    return "\n".join(lines)


def is_tax_question(message: str) -> bool:
    """Detect if user is asking a tax knowledge question vs providing filing data."""
    msg = message.lower().strip()

    question_indicators = [
        "what is", "what are", "how to", "how do", "how does",
        "explain", "tell me about", "meaning of", "define",
        "which section", "which rule", "can i claim", "am i eligible",
        "difference between", "what counts",
    ]

    filing_indicators = [
        "my salary", "i earn", "my income", "i paid", "i have",
        "my pan", "my name", "my address", "yes", "no", "skip",
        "next", "continue", "go ahead", "proceed", "done",
        "correct", "that's right", "confirm",
    ]

    is_question = any(q in msg for q in question_indicators)
    is_filing = any(f in msg for f in filing_indicators)

    # If it looks like both, prefer filing context
    if is_filing:
        return False
    return is_question
