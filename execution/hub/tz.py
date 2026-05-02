"""Pacific time helpers. The whole app should think in America/Los_Angeles
("PDT" in summer / "PST" in winter), not UTC — reps log activity by their
local day, and a UTC `today()` rolls over at 5pm Pacific."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")


def local_now() -> datetime:
    return datetime.now(PACIFIC)


def local_today() -> date:
    return local_now().date()
