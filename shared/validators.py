"""
validators.py — 财务数据完整性校验
BS balance assertion, unit-scale sanity checks, cross-statement validation.
"""
import warnings
from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════
# BS subtotal key groups (re-exported from source_reader for convenience)
# ═══════════════════════════════════════════════════════════════════

CA_KEYS = [
    'Cash', 'Trading_Fin_Assets', 'Notes_Receivable',
    'Accounts_Receivable', 'Prepayments', 'Other_Receivables',
    'Inventory', 'Contract_Assets', 'Other_Current_Assets',
]
NCA_KEYS = [
    'LT_Equity_Investments', 'Other_Equity_Investments',
    'Fixed_Assets', 'Intangible_Assets', 'LT_Prepaid',
    'ROU_Assets', 'Deferred_Tax_Assets',
]
CL_KEYS = [
    'ST_Borrowings', 'Accounts_Payable', 'Advance_Receipts',
    'Contract_Liabilities', 'Employee_Comp_Payable',
    'Taxes_Payable', 'Other_Payable',
]
NCL_KEYS = [
    'LT_Borrowings', 'Lease_Liabilities',
    'Deferred_Income', 'Deferred_Tax_Liabilities',
]
EQ_KEYS = [
    'Paid_in_Capital', 'Capital_Reserve',
    'Surplus_Reserve', 'Retained_Earnings',
]


class DataValidationError(Exception):
    """Raised when data validation fails critically."""
    pass


class DataValidationWarning(UserWarning):
    """Issued for suspicious but non-critical data patterns."""
    pass


# ═══════════════════════════════════════════════════════════════════
# Improvement #2: BS balance assertion
# ═══════════════════════════════════════════════════════════════════

def assert_bs_balance(bs_data: Dict[str, List[int]],
                      year_labels: Optional[List[str]] = None,
                      tolerance: int = 0) -> None:
    """
    Assert that Total Assets == Total Liabilities + Equity for all years.

    Args:
        bs_data: Dict of key → [values_per_year]
        year_labels: Optional list of year labels for error messages.
        tolerance: Allowable imbalance in 万元 (default 0 = exact balance).

    Raises:
        DataValidationError if any year is out of balance.
    """
    n_years = len(next(iter(bs_data.values())))
    errors = []

    for i in range(n_years):
        ta = sum(bs_data.get(k, [0]*n_years)[i] for k in CA_KEYS + NCA_KEYS)
        tle = sum(bs_data.get(k, [0]*n_years)[i]
                  for k in CL_KEYS + NCL_KEYS + EQ_KEYS)
        gap = ta - tle
        if abs(gap) > tolerance:
            yr = year_labels[i] if year_labels else f"Year{i}"
            errors.append(
                f"  {yr}: TA={ta:,} != TLE={tle:,} (gap={gap:+,})"
            )

    if errors:
        msg = "BS BALANCE CHECK FAILED:\n" + "\n".join(errors)
        raise DataValidationError(msg)


# ═══════════════════════════════════════════════════════════════════
# Improvement #3: Unit-scale validation
# ═══════════════════════════════════════════════════════════════════

def check_unit_scale(is_data: Dict[str, List[int]],
                     bs_data: Dict[str, List[int]],
                     cf_data: Dict[str, List[int]],
                     year_labels: Optional[List[str]] = None) -> List[str]:
    """
    Detect potential 10x / 100x unit-scale errors by checking ratios.

    Returns a list of warning messages. Empty list = all OK.
    """
    warns = []
    n = len(next(iter(is_data.values())))

    for i in range(n):
        yr = year_labels[i] if year_labels else f"Year{i}"
        rev = is_data.get('Revenue_Total', [0]*n)[i]
        ta = sum(bs_data.get(k, [0]*n)[i] for k in CA_KEYS + NCA_KEYS)

        if rev <= 0:
            continue  # pre-revenue company, skip ratio checks

        # 1. Paid_in_Capital should be small relative to Revenue for mature co
        pic = bs_data.get('Paid_in_Capital', [0]*n)[i]
        if pic > 0 and pic > rev * 10:
            warns.append(
                f"[!] {yr}: Paid_in_Capital ({pic:,}) > 10x Revenue ({rev:,}) - "
                f"possible 10x error"
            )

        # 2. No single BS line item should exceed Total Assets
        for k in CA_KEYS + NCA_KEYS:
            v = bs_data.get(k, [0]*n)[i]
            if v > ta and ta > 0:
                warns.append(
                    f"[!] {yr}: BS.{k} ({v:,}) > Total Assets ({ta:,})"
                )

        # 3. CF Capex should be negative and not exceed Total Assets
        capex = cf_data.get('Capex', [0]*n)[i]
        if capex > 0:
            warns.append(
                f"[!] {yr}: CF.Capex is positive ({capex:,}) - "
                f"should be negative (outflow)"
            )
        elif abs(capex) > ta and ta > 0:
            warns.append(
                f"[!] {yr}: |CF.Capex| ({abs(capex):,}) > Total Assets ({ta:,}) "
                f"- possible 10x error"
            )

        # 4. Operating_CF magnitude check vs Revenue
        opcf = abs(cf_data.get('Operating_CF', [0]*n)[i])
        if opcf > rev * 3 and rev > 0:
            warns.append(
                f"[!] {yr}: |Operating_CF| ({opcf:,}) > 3x Revenue ({rev:,}) "
                f"- suspicious"
            )

        # 5. COGS should not exceed Revenue
        cogs = is_data.get('COGS_Total', [0]*n)[i]
        if cogs > rev * 1.5 and rev > 0:
            warns.append(
                f"[!] {yr}: COGS ({cogs:,}) > 1.5x Revenue ({rev:,}) - "
                f"possible error"
            )

    return warns


# ═══════════════════════════════════════════════════════════════════
# Improvement #5: Cross-validation rules
# ═══════════════════════════════════════════════════════════════════

def cross_validate(is_data: Dict[str, List[int]],
                   bs_data: Dict[str, List[int]],
                   cf_data: Dict[str, List[int]],
                   year_labels: Optional[List[str]] = None,
                   tolerance: int = 2) -> List[str]:
    """
    Cross-validate consistency between IS, BS, and CF statements.

    Checks:
      1. CF.Cash_End == BS.Cash (should be identical)
      2. Product revenue sums ≈ Revenue_Total (if details present)
      3. IS balance: Revenue - COGS - Expenses ≈ Operating_Profit

    Args:
        tolerance: Allowed difference in 万元 due to rounding.

    Returns a list of error messages. Empty = all OK.
    """
    errors = []
    n = len(next(iter(is_data.values())))

    for i in range(n):
        yr = year_labels[i] if year_labels else f"Year{i}"

        # 1. CF Cash_End == BS Cash
        cf_cash = cf_data.get('Cash_End', [0]*n)[i]
        bs_cash = bs_data.get('Cash', [0]*n)[i]
        if abs(cf_cash - bs_cash) > tolerance:
            errors.append(
                f"[X] {yr}: CF.Cash_End ({cf_cash:,}) != BS.Cash ({bs_cash:,}) "
                f"[diff={cf_cash - bs_cash:+,}]"
            )

        # 2. Revenue product detail sum ≈ Revenue_Total
        rev_detail_keys = ['Revenue_Servo', 'Revenue_Dexterous', 'Revenue_Other']
        if all(k in is_data for k in rev_detail_keys):
            rev_sum = sum(is_data[k][i] for k in rev_detail_keys)
            rev_total = is_data.get('Revenue_Total', [0]*n)[i]
            if abs(rev_sum - rev_total) > tolerance:
                errors.append(
                    f"[!] {yr}: Revenue detail sum ({rev_sum:,}) != "
                    f"Revenue_Total ({rev_total:,}) [diff={rev_sum - rev_total:+,}]"
                )

        # 3. IS internal consistency:
        #    Operating_Profit ≈ Revenue - COGS - Tax_Surcharge - Selling -
        #    Admin - RD - Finance_Cost + Other_Income + Investment_Income +
        #    Credit_Impairment + Asset_Impairment
        rev = is_data.get('Revenue_Total', [0]*n)[i]
        cogs = is_data.get('COGS_Total', [0]*n)[i]
        tax_s = is_data.get('Tax_Surcharge', [0]*n)[i]
        sell = is_data.get('Selling_Exp', [0]*n)[i]
        admin = is_data.get('Admin_Exp', [0]*n)[i]
        rd = is_data.get('RD_Exp', [0]*n)[i]
        fin = is_data.get('Finance_Cost', [0]*n)[i]
        oth_inc = is_data.get('Other_Income', [0]*n)[i]
        inv_inc = is_data.get('Investment_Income', [0]*n)[i]
        cred_imp = is_data.get('Credit_Impairment', [0]*n)[i]
        asset_imp = is_data.get('Asset_Impairment', [0]*n)[i]
        op_profit = is_data.get('Operating_Profit', [0]*n)[i]

        computed_op = (rev - cogs - tax_s - sell - admin - rd - fin
                       + oth_inc + inv_inc + cred_imp + asset_imp)
        if abs(computed_op - op_profit) > tolerance:
            errors.append(
                f"[!] {yr}: IS computed Operating_Profit ({computed_op:,}) != "
                f"reported ({op_profit:,}) [diff={computed_op - op_profit:+,}]"
            )

    return errors


def run_all_validations(
    is_data: Dict[str, List[int]],
    bs_data: Dict[str, List[int]],
    cf_data: Dict[str, List[int]],
    year_labels: Optional[List[str]] = None,
    strict: bool = True,
) -> None:
    """
    Run all validation checks. Print results and optionally raise on critical errors.

    Args:
        strict: If True, raise on BS imbalance. If False, just warn.
    """
    print("=" * 60)
    print("DATA VALIDATION REPORT")
    print("=" * 60)

    # 1. BS Balance
    print("\n── BS Balance Check ──")
    try:
        assert_bs_balance(bs_data, year_labels)
        print("  [OK] BS balanced for all years")
    except DataValidationError as e:
        print(f"  {e}")
        if strict:
            raise

    # 2. Unit Scale
    print("\n── Unit Scale Check ──")
    scale_warns = check_unit_scale(is_data, bs_data, cf_data, year_labels)
    if scale_warns:
        for w in scale_warns:
            print(f"  {w}")
    else:
        print("  [OK] No unit-scale anomalies detected")

    # 3. Cross-Validation
    print("\n── Cross-Statement Validation ──")
    xval_errors = cross_validate(is_data, bs_data, cf_data, year_labels)
    if xval_errors:
        for e in xval_errors:
            print(f"  {e}")
    else:
        print("  [OK] All cross-checks passed")

    total_issues = len(scale_warns) + len(xval_errors)
    print(f"\n{'=' * 60}")
    print(f"  Total warnings: {len(scale_warns)}")
    print(f"  Total cross-validation issues: {len(xval_errors)}")
    print(f"  Result: {'[OK] ALL PASS' if total_issues == 0 else '[!] REVIEW NEEDED'}")
    print(f"{'=' * 60}\n")
