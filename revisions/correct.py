from ledger_support import StorageError
from revisions.history import append_revision, find_revision


def prepare_replacement(connection, submission, current_revision):
    """Append a complete replacement linked to the current revision of the same day."""
    predecessor = find_revision(connection, submission.day, current_revision)
    if predecessor is None:
        raise StorageError('Replacement has no current predecessor for this station day')
    return append_revision(connection, submission.day, submission.submission_id, predecessor.revision)
