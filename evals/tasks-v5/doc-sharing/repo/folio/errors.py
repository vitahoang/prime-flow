"""Exceptions raised by folio."""


class FolioError(Exception):
    """Base class for everything folio raises on purpose."""


class NotFound(FolioError, KeyError):
    def __init__(self, kind: str, ident: str):
        super().__init__(f"no {kind} {ident!r}")
        self.kind = kind
        self.ident = ident

    def __str__(self) -> str:  # KeyError would quote the whole message
        return self.args[0]


class Invalid(FolioError, ValueError):
    """Bad input: an empty name, a folder loop, a wrong-workspace move..."""


class AccessDenied(FolioError, PermissionError):
    def __init__(self, user_id: str, action: str, resource_id: str):
        super().__init__(f"{user_id} may not {action} {resource_id}")
        self.user_id = user_id
        self.action = action
        self.resource_id = resource_id
