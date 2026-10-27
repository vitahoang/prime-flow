"""The current time, overridable for tests and demos.

Set JOTTER_NOW=YYYY-MM-DDTHH:MM:SS to run as if it were another moment.
"""

import os
from datetime import datetime


def now():
    value = os.environ.get("JOTTER_NOW")
    if value:
        return datetime.fromisoformat(value).replace(microsecond=0)
    return datetime.now().replace(microsecond=0)
