from ledger_support import InvalidData


def validate_reading(value):
    if value is not None and type(value) is not int:
        raise InvalidData('Reading must be integer litres or null for missing')
    return value


def litres_for_reading(value):
    return 0 if value is None else value
