from accounting.combine import combine_totals
from accounting.site_totals import calculate_site_total
from ledger_support import InvalidData


def reconcile_site(rows, declared):
    actual = calculate_site_total(rows)
    if type(declared) is not int or actual != declared:
        raise InvalidData('Site subtotal disagrees with its observation rows')
    return actual


def reconcile_handoff(east_litres, west_litres, declared):
    """Check the combined declaration against the already reconciled station subtotals."""
    actual = combine_totals(east_litres, west_litres)
    if actual != declared:
        raise InvalidData('Combined totals disagree with the two site subtotals')
    return actual
