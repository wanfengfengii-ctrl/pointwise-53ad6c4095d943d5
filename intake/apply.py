from intake.submission import parse_submission
from revisions.activate import activate_submission


def apply(site, submission):
    """Register a new site-day or a full replacement, or replay an exact submission."""
    return activate_submission(site, parse_submission(submission))
