from unittest.mock import Mock, patch

from backend.spiders.spiders import ToutiaoSpider, WeiboSpider


def test_weibo_uses_fallback_cookie_or_env_header(monkeypatch):
    session = Mock()
    session.headers = {}
    session.get.return_value.text = ""
    monkeypatch.delenv("WEIBO_COOKIE", raising=False)

    with patch("backend.spiders.spiders.requests.Session", return_value=session):
        assert WeiboSpider().fetch() == []

    assert session.headers["Cookie"].startswith("SUB=")

    session = Mock()
    session.headers = {}
    session.get.return_value.text = ""
    monkeypatch.setenv("WEIBO_COOKIE", "SUB=test")

    with patch("backend.spiders.spiders.requests.Session", return_value=session):
        WeiboSpider().fetch()

    assert session.headers["Cookie"] == "SUB=test"


def test_weibo_fetch_parses_s_weibo_hot_list():
    html = """
    <div id="pl_top_realtimehot"><table><tbody>
      <tr><td></td></tr>
      <tr><td class="td-02"><a href="/weibo?q=one">话题一</a></td></tr>
      <tr><td class="td-02"><a href="javascript:void(0);">无效</a><a href="/weibo?q=two">话题二</a></td></tr>
    </tbody></table></div>
    """
    response = Mock()
    response.text = html
    session = Mock()
    session.headers = {}
    session.get.return_value = response

    with patch("backend.spiders.spiders.requests.Session", return_value=session):
        items = WeiboSpider().fetch()

    assert [item["title"] for item in items] == ["话题一", "话题二"]
    assert items[0]["url"] == "https://s.weibo.com/weibo?q=one"


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
