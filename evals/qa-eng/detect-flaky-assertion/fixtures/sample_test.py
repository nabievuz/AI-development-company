import datetime


def test_report_created_at():
    report = build_report()
    # BUG: compares against a fresh wall-clock read → non-deterministic.
    assert report.created_at == datetime.datetime.now()


def test_report_title():
    report = build_report()
    assert report.title == "Weekly summary"
