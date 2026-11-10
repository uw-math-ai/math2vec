import re

def flip_bound(sig: str, type_str: str) -> tuple[str, str] | None:
    """
    Flips the direction of the first inequality in the type.
    ≥ ↔ ≤  and  > ↔ 
    Truth value is always unknown — depends on the specific statement.
    """
    flips = [
        (r'≥', '≤'),
        (r'≤', '≥'),
        (r'>', '<'),
        (r'<', '>'),
    ]
    for pat, replacement in flips:
        m = re.search(pat, type_str)
        if m:
            variant_type = type_str[:m.start()] + replacement + type_str[m.end():]
            return sig, variant_type
    return None

def perturb_bound(sig: str, type_str: str) -> tuple[str, str] | None:
    """
    Finds the first numeric bound in the type and shifts it by ±1.
    Tighter bounds (≥ n → ≥ n+1, ≤ n → ≤ n-1) make the statement stronger.
    Looser bounds (≥ n → ≥ n-1, ≤ n → ≤ n+1) make it weaker.
    Returns the tighter variant by default (more likely to be false, more interesting).
    """
    specs = [
        (r'(≥\s*)(\d+)', +1, "bound_perturbation_tighter"),
        (r'(≤\s*)(\d+)', -1, "bound_perturbation_tighter"),
        (r'(>\s*)(\d+)',  +1, "bound_perturbation_tighter"),
        (r'(<\s*)(\d+)',  -1, "bound_perturbation_tighter"),
    ]
    for pat, delta, _ in specs:
        m = re.search(pat, type_str)
        if m:
            new_val = str(max(0, int(m.group(2)) + delta))
            variant_type = type_str[:m.start(2)] + new_val + type_str[m.end(2):]
            # sig stays the same — bound changes are in the type only
            return sig, variant_type
    return None