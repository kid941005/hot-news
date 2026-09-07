"""数据源修复回归测试：weibo 内置 Cookie 兜底、kaopu 改抓 HTML、pcbeta 双 RSS 容错。"""
from unittest.mock import Mock, patch

from backend.spiders.spiders import KaopuSpider, PcbetaSpider, WeiboSpider

WEIBO_HTML = """
<div id="pl_top_realtimehot"><table><tbody>
  <tr><td class="td-01"></td><td class="td-02"><a href="//s.weibo.com/weibo?q=%E6%B5%8B%E8%AF%95">置顶</a></td></tr>
  <tr><td class="td-01"></td><td class="td-02"><a href="//s.weibo.com/weibo?q=%E6%B5%8B%E8%AF%95">测试热搜</a></td><td class="td-03">热</td></tr>
  <tr><td class="td-01"></td><td class="td-02"><a href="javascript:void(0);">占位</a></td></tr>
  <tr><td class="td-01"></td><td class="td-02"><a href="//s.weibo.com/weibo?q=second">第二条</a></td><td class="td-03">新</td></tr>
</tbody></table></div>
"""

KAOPU_HTML = """
<html><body>
  <article>
    <a href="/story/abc"><h2>靠谱新闻标题一</h2></a>
    <p>简介一</p>
    <div class="story-meta"><span>1 小时前</span></div>
    <div class="story-provenance">路透</div>
  </article>
  <article>
    <a href="/story/def"><h2>靠谱新闻标题二</h2></a>
    <p>简介二</p>
    <div class="story-meta"><span>2 小时前</span></div>
    <div class="story-provenance">法新社</div>
  </article>
</body></html>
"""

RSS_XML = """
<rss><channel>
  <item><title>远景标题</title><link>https://bbs.pcbeta.com/viewthread-1-1.html</link></item>
</channel></rss>
"""


def test_weibo_spider_uses_fallback_cookie_when_env_missing():
    resp = Mock()
    resp.text = WEIBO_HTML

    with patch("backend.spiders.spiders.os.getenv", return_value=None), \
         patch("backend.spiders.spiders.fetch_get", return_value=resp) as fetch:
        items = WeiboSpider().fetch()

    headers = fetch.call_args.kwargs["headers"]
    assert "Cookie" in headers and headers["Cookie"].startswith("SUB=")
    titles = [item["title"] for item in items]
    assert "测试热搜" in titles
    assert "第二条" in titles
    assert len(items) == 2


def test_weibo_spider_uses_env_cookie_when_set():
    resp = Mock()
    resp.text = WEIBO_HTML

    with patch("backend.spiders.spiders.os.getenv", return_value="MY_COOKIE"), \
         patch("backend.spiders.spiders.fetch_get", return_value=resp) as fetch:
        WeiboSpider().fetch()

    headers = fetch.call_args.kwargs["headers"]
    assert headers["Cookie"] == "MY_COOKIE"


def test_kaopu_spider_fetches_html_page_instead_of_blob():
    resp = Mock()
    resp.text = KAOPU_HTML

    with patch("backend.spiders.spiders.fetch_get", return_value=resp) as fetch:
        items = KaopuSpider().fetch()

    url = fetch.call_args.args[0] if fetch.call_args.args else fetch.call_args.kwargs.get("url")
    assert url == "https://kaopu.news"
    titles = [item["title"] for item in items]
    assert "靠谱新闻标题一" in titles
    assert "靠谱新闻标题二" in titles
    assert items[0]["hot"] == "路透"
    assert items[0]["url"] == "https://kaopu.news/story/abc"


def test_pcbeta_spider_falls_back_to_second_rss_feed():
    def fake_fetch_get(url, **_kwargs):
        if "fid=563" in url:
            raise OSError("primary feed failed")
        resp = Mock()
        resp.text = RSS_XML
        return resp

    with patch("backend.spiders.spiders.fetch_get", side_effect=fake_fetch_get):
        items = PcbetaSpider().fetch()

    assert len(items) == 1
    assert items[0]["platform"] == "远景论坛"
    assert items[0]["title"] == "远景标题"
