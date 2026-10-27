class PennywiseError(Exception):
    """An error the CLI reports to the user as ``error: <message>``."""


class NotFound(PennywiseError):
    pass


class InvalidInput(PennywiseError):
    pass
