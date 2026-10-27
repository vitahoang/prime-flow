"""tickoff: an offline-first todo library.

Each device keeps its own replica (a JSON file) with its tasks and a log of
every change made on that device. See README.md.
"""

from .models import Task, ValidationError
from .replica import Replica

__all__ = ["Task", "ValidationError", "Replica"]
__version__ = "0.6.0"
