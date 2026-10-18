MAX_ATTEMPTS = 6

class PermanentError(Exception):
    """Raise this when retrying cannot help."""


def backoff_delay(attempts: int) -> float:
    if attempts < 1:
        raise ValueError(f"attempts must be >=1 , got {attempts}")
    
    return min(2 ** attempts,60.0)