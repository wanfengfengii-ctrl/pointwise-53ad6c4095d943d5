from accounting.measures import litres_for_reading


def calculate_site_total(rows):
    """Sum the contributions of the frozen observations, including an empty day."""
    return sum(litres_for_reading(row.litres) for row in rows)
