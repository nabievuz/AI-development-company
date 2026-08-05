import datetime


def test_report_created_at():
    report = build_report()

    assert report.created_at == datetime.datetime.now()


def test_report_title():
    report = build_report()
    assert report.title == "Weekly summary"
