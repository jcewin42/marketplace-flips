"""Time-based polling schedule, Eastern-time aware.

Each day-type schedule is a list of (start_time, end_time, interval_minutes)
windows built by create_schedule(). No calls happen from midnight-6am any
day. The monitor never waits longer than the interval for the current
window, and runs immediately if the next scheduled check has already
passed (seconds_until_next_check returns 0 in that case).
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def create_schedule(*periods):
    """periods: tuples of ("HH:MM", "HH:MM", interval_minutes).
    An end time of "00:00" means "through end of day"."""
    schedule = []
    for start_str, end_str, interval_minutes in periods:
        start = datetime.strptime(start_str, "%H:%M").time()
        end = time(23, 59, 59) if end_str == "00:00" else datetime.strptime(end_str, "%H:%M").time()
        schedule.append((start, end, interval_minutes))
    return schedule


WEEKDAY_SCHEDULE = create_schedule(
    ("06:00", "08:00", 45),
    ("08:00", "11:00", 30),
    ("11:00", "13:30", 20),
    ("13:30", "16:00", 30),
    ("16:00", "17:00", 20),
    ("17:00", "21:00", 10),
    ("21:00", "00:00", 20),
)

FRIDAY_SCHEDULE = create_schedule(
    ("06:00", "08:00", 45),
    ("08:00", "11:00", 30),
    ("11:00", "13:30", 20),
    ("13:30", "16:00", 30),
    ("16:00", "17:00", 15),
    ("17:00", "22:30", 10),
    ("22:30", "00:00", 20),
)

SATURDAY_SCHEDULE = create_schedule(
    ("06:00", "08:00", 30),
    ("08:00", "13:00", 10),
    ("13:00", "15:00", 20),
    ("15:00", "17:00", 30),
    ("17:00", "21:00", 10),
    ("21:00", "00:00", 20),
)

SUNDAY_SCHEDULE = create_schedule(
    ("06:00", "09:00", 45),
    ("09:00", "14:00", 10),
    ("14:00", "18:00", 15),
    ("18:00", "22:00", 10),
    ("22:00", "00:00", 30),
)


def _schedule_for_day(weekday: int):
    # datetime.weekday(): Monday=0 ... Sunday=6
    if weekday == 4:
        return FRIDAY_SCHEDULE
    if weekday == 5:
        return SATURDAY_SCHEDULE
    if weekday == 6:
        return SUNDAY_SCHEDULE
    return WEEKDAY_SCHEDULE


def get_current_interval_minutes(now: datetime | None = None):
    """Interval in minutes for right now, or None if in the midnight-6am
    blackout window."""
    now = now or datetime.now(EASTERN)
    current_time = now.time()
    if time(0, 0) <= current_time < time(6, 0):
        return None
    for start, end, interval in _schedule_for_day(now.weekday()):
        if start <= current_time < end:
            return interval
    return None


def seconds_until_next_check(last_check: datetime, now: datetime | None = None) -> float:
    """Seconds to sleep before the next check. Returns 0 if the scheduled
    time has already passed (run immediately)."""
    now = now or datetime.now(EASTERN)
    interval_minutes = get_current_interval_minutes(now)

    if interval_minutes is None:
        # In the blackout window - sleep until 6am (today if we're
        # before 6am, otherwise tomorrow).
        next_run = datetime.combine(now.date(), time(6, 0), tzinfo=EASTERN)
        if now.time() >= time(6, 0):
            next_run += timedelta(days=1)
        return max((next_run - now).total_seconds(), 0)

    next_run = last_check + timedelta(minutes=interval_minutes)
    return max((next_run - now).total_seconds(), 0)
