from helpdesk import jobs


def test_run_all_reports_counts(store, clock, mailer):
    assert jobs.run_all(store, mailer, clock) == {"sla_warnings": 0}
