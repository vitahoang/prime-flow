# alertd

Routes alerts from our systems (databases, cron jobs, the API) to whoever is on
call, over email, SMS or Slack.

```python
from alertd import Alert, Router, UserSettings, WARNING, SMS
from alertd.notifiers import build_notifiers

settings = UserSettings(user_id="dana", timezone="Europe/Berlin", phone="+49...")
router = Router(build_notifiers(settings))
router.route(Alert(WARNING, "db-primary", "replication lag 40s", SMS))
```

## Layout

- `alertd/models.py` — `Alert`, severities (`info`, `warning`, `critical`) and channels
- `alertd/settings.py` — per-user `UserSettings` (contact details, timezone)
- `alertd/formatting.py` — channel-specific text; timestamps are shown in the user's timezone
- `alertd/notifiers.py` — one notifier per channel (transports are stubs that record sends)
- `alertd/router.py` — `Router` picks the notifier for each alert
- `alertd/clock.py` — `SystemClock` and `FakeClock`; pass a clock anywhere time matters

## Tests

    python -m pytest
