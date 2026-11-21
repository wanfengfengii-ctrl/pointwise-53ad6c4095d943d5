from dataclasses import dataclass

from ledger_support import require_fields, require_positive_int, require_text


@dataclass(frozen=True, slots=True)
class SourceOrigin:
    register: str
    line: int

    def as_dict(self):
        return {'register': self.register, 'line': self.line}


def parse_origin(value):
    fields = require_fields(value, ('register', 'line'), 'source origin')
    register = require_text(fields['register'], 'register')
    line = require_positive_int(fields['line'], 'register line')
    return SourceOrigin(register, line)
