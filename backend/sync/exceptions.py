from rest_framework import status

class SyncAlreadyRunningException(Exception):
    """Raised when a sync is triggered while one is already pending/running for that connection."""
    status_code = status.HTTP_409_CONFLICT

class SyncRunNotFoundException(Exception):
    status_code = status.HTTP_404_NOT_FOUND
