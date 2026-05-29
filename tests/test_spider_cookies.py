from unittest.mock import Mock, patch

from backend.spiders.spiders import ToutiaoSpider, WeiboSpider


def test_weibo_cookie_is_optional_env_header(monkeypatch):
    session = Mock()
    session.headers = {}
    session.get.return_value.text = ""
    monkeypatch.delenv("WEIBO_COOKIE", raising=False)

    with patch("backend.spiders.spiders.requests.Session", return_value=session):
        assert WeiboSpider().fetch() == []

    assert "Cookie" not in session.headers

    session = Mock()
    session.headers = {}
    session.get.return_value.text = ""
    monkeypatch.setenv("WEIBO_COOKIE", "SUB=test")

    with patch("backend.spiders.spiders.requests.Session", return_value=session):
        WeiboSpider().fetch()

    assert session.headers["Cookie"] == "SUB=test"


def test_toutiao_cookie_is_optional_env_header(monkeypatch):
    response = Mock()
    response.json.return_value = {"data": []}
    monkeypatch.delenv("TOUTIAO_COOKIE", raising=False)

    with patch("backend.spiders.spiders.requests.get", return_value=response) as get:
        assert ToutiaoSpider().fetch() == []

    assert "Cookie" not in get.call_args.kwargs["headers"]

    monkeypatch.setenv("TOUTIAO_COOKIE", "tt_webid=test")
    with patch("backend.spiders.spiders.requests.get", return_value=response) as get:
        ToutiaoSpider().fetch()

    assert get.call_args.kwargs["headers"]["Cookie"] == "tt_webid=test"
