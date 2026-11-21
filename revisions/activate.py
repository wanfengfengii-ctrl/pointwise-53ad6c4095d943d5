from intake.inbox import find_submission, matches_submission, record_submission
from ledger_support import Conflict, IdentityError, StorageError
from revisions.correct import prepare_replacement
from revisions.current import find_current_revision, set_current_revision
from revisions.history import append_revision, find_revision_for_submission


def activate_submission(site, submission):
    if site.station != submission.station:
        raise IdentityError('Submission is for a different station')
    with site.write_transaction() as connection:
        existing = find_submission(connection, site.station, submission.submission_id)
        if existing is not None:
            if not matches_submission(existing, submission):
                raise Conflict(f'Submission ID already has different content: {submission.submission_id}')
            original = find_revision_for_submission(connection, submission.submission_id)
            if original is None:
                raise StorageError('Registered submission is missing its revision')
            return original

        previous = find_current_revision(connection, submission.day)
        record_submission(connection, submission)
        if previous is None:
            revision = append_revision(connection, submission.day, submission.submission_id)
        else:
            revision = prepare_replacement(connection, submission, previous)
        set_current_revision(connection, submission.day, revision.revision)
        return revision
