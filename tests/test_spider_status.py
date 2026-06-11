from unittest.mock import Mock, patch

import pytest
import requests
from bs4 import FeatureNotFound

from backend.spiders.spiders import (
    AihotSpider,
    BaiduSpider,
    CankaoXiaoxiSpider,
    ChongbuluoSpider,
    FastbullSpider,
    GitHubSpider,
    IfengSpider,
    Jin10Spider,
    KuaishouSpider,
    Kr36RenqiSpider,
    PcbetaSpider,
    ProductHuntSpider,
    SolidotSpider,
    XueqiuHotstockSpider,
    ZaobaoSpider,
    fetch_get,
    fetch_post,
    _parse_rss_text,
)


class BaiduSuccessResponse:
    text = '<!--s-data:{"data":{"cards":[{"content":[{"word":"A&B #测试","isTop":false}]}]}}-->'


def test_baidu_spider_rejects_http_error_status():
    with patch("backend.spiders.spiders.fetch_get", side_effect=requests.HTTPError("bad status")):
        assert BaiduSpider().fetch() == []


def test_fetch_get_uses_chrome_user_agent_by_default():
    with patch("backend.spiders.spiders.requests.Session") as session_cls:
        session = session_cls.return_value
        response = Mock()
        response.raise_for_status = Mock()
        session.get.return_value = response

        fetch_get("https://example.com")

    assert "Chrome" in session.headers.update.call_args_list[0].args[0]["User-Agent"]
    response.raise_for_status.assert_called_once()


def test_fetch_post_uses_chrome_user_agent_by_default():
    with patch("backend.spiders.spiders.requests.Session") as session_cls:
        session = session_cls.return_value
        response = Mock()
        response.raise_for_status = Mock()
        session.post.return_value = response

        fetch_post("https://example.com", json={})

    assert "Chrome" in session.headers.update.call_args_list[0].args[0]["User-Agent"]
    response.raise_for_status.assert_called_once()


def test_rss_parser_falls_back_without_xml_builder():
    xml = '''
    <rss><channel>
      <item><title>标题</title><link>https://example.com/1</link><pubDate>Wed, 10 Jun 2026 09:30:00 GMT</pubDate></item>
    </channel></rss>
    '''

    with patch("backend.spiders.spiders.BeautifulSoup", side_effect=FeatureNotFound("xml")):
        items = _parse_rss_text(xml, "测试")

    assert items[0]["platform"] == "测试"
    assert items[0]["title"] == "标题"
    assert items[0]["time"] == "17:30"


def test_cankaoxiaoxi_spider_sorts_by_publish_time():
    def response(title, publish_time):
        mock = Mock()
        mock.json.return_value = {
            "list": [{"data": {"title": title, "url": f"https://example.com/{title}", "publishTime": publish_time}}]
        }
        return mock

    responses = [
        response("旧", "2026-06-11 09:00:00"),
        response("中", "2026-06-11 10:00:00"),
        response("新", "2026-06-11 11:00:00"),
    ]

    with patch("backend.spiders.spiders.fetch_get", side_effect=responses):
        items = CankaoXiaoxiSpider().fetch()

    assert [item["title"] for item in items] == ["新", "中", "旧"]
    assert items[0]["time"] == "11:00"


def test_baidu_spider_encodes_search_keyword_url():
    response = BaiduSuccessResponse()

    with patch("backend.spiders.spiders.fetch_get", return_value=response):
        items = BaiduSpider().fetch()

    assert items[0]["url"] == "https://www.baidu.com/s?wd=A%26B+%23%E6%B5%8B%E8%AF%95"


def test_github_spider_rejects_http_error_status():
    with patch("backend.spiders.spiders.fetch_get", side_effect=requests.HTTPError("bad status")):
        assert GitHubSpider().fetch() == []


def test_ifeng_spider_reads_newsnow_hotnews_data():
    response = Mock()
    response.text = 'var allData = {"hotNews1":[{"title":"凤凰标题一","url":"https://news.ifeng.com/a","newsTime":"2026-06-10"},{"title":"凤凰标题二","url":"https://news.ifeng.com/b","newsTime":""}]};'

    with patch("backend.spiders.spiders.fetch_get", return_value=response):
        items = IfengSpider().fetch()

    assert [item["title"] for item in items] == ["凤凰标题一", "凤凰标题二"]
    assert items[0]["platform"] == "凤凰"
    assert items[0]["url"] == "https://news.ifeng.com/a"
    assert items[0]["time"] == "2026-06-10"


def test_ifeng_spider_falls_back_when_hotnews_empty():
    response = Mock()
    response.status_code = 200
    response.text = '''
    <html><body>
      <script>var allData = {"hotNews1": []};</script>
      <a href="https://news.ifeng.com/c/1" title="凤凰兜底一"></a>
      <a href="https://news.ifeng.com/c/2">凤凰兜底二</a>
    </body></html>
    '''

    with patch("backend.spiders.spiders.fetch_get", return_value=response):
        items = IfengSpider().fetch()

    assert [item["title"] for item in items] == ["凤凰兜底一", "凤凰兜底二"]
    assert items[0]["platform"] == "凤凰"
    assert items[0]["url"] == "https://news.ifeng.com/c/1"


def test_ifeng_spider_falls_back_without_alldata():
    response = Mock()
    response.status_code = 200
    response.text = '<a href="https://news.ifeng.com/c/1" title="凤凰兜底一"></a>'

    with patch("backend.spiders.spiders.fetch_get", return_value=response):
        items = IfengSpider().fetch()

    assert len(items) == 1
    assert items[0]["title"] == "凤凰兜底一"


def test_jin10_spider_reads_newest_js():
    response = Mock()
    response.text = 'var newest = [{"id":"1","time":"2026-06-10 09:43:22","type":0,"important":1,"channel":[1],"data":{"content":"【金十标题】详情"}},{"id":"2","time":"2026-06-10 09:40:00","type":0,"important":0,"channel":[5],"data":{"content":"过滤"}}];'

    with patch("backend.spiders.spiders.fetch_get", return_value=response):
        items = Jin10Spider().fetch()

    assert len(items) == 1
    assert items[0]["platform"] == "金十数据"
    assert items[0]["title"] == "金十标题"
    assert items[0]["url"] == "https://flash.jin10.com/detail/1"
    assert items[0]["time"] == "09:43"


def test_zaobao_spider_reads_gb2312_realtime_page():
    response = Mock()
    html = '<div class="list-block"><a class="item" href="/realtime/1.html"><span class="eps">早报标题</span><span class="pdt10">2026-06-10 09:30</span></a></div>'
    response.content = html.encode("gb2312")

    with patch("backend.spiders.spiders.fetch_get", return_value=response):
        items = ZaobaoSpider().fetch()

    assert items[0]["platform"] == "联合早报"
    assert items[0]["title"] == "早报标题"
    assert items[0]["url"] == "https://www.zaochenbao.com/realtime/1.html"
    assert items[0]["time"] == "09:30"


def test_fastbull_spider_reads_api_body_message():
    response = Mock()
    response.json.return_value = {
        "bodyMessage": '{"pageDatas":[{"newsId":"1","path":"fastbull-title-1","title":"法布标题","point":12,"pubTime":1781048143634}]}'
    }

    with patch("backend.spiders.spiders.fetch_post", return_value=response):
        items = FastbullSpider().fetch()

    assert items[0]["platform"] == "法布财经"
    assert items[0]["title"] == "法布标题"
    assert items[0]["url"] == "https://www.fastbull.com/cn/news-detail/fastbull-title-1"
    assert items[0]["hot"] == "12"


def test_36kr_renqi_spider_reads_newsnow_gateway_api():
    response = Mock()
    response.json.return_value = {
        "data": {
            "hotRankList": [
                {
                    "itemId": 123,
                    "templateMaterial": {
                        "widgetTitle": "36氪标题",
                        "authorName": "作者",
                        "statFormat": "热度 99",
                    },
                }
            ]
        }
    }

    with patch("backend.spiders.spiders.fetch_post", return_value=response):
        items = Kr36RenqiSpider().fetch()

    assert items[0]["platform"] == "36Kr热榜"
    assert items[0]["title"] == "36氪标题"
    assert items[0]["url"] == "https://36kr.com/p/123"
    assert items[0]["hot"] == "作者  |  热度 99"


def test_xueqiu_hotstock_spider_reads_cookie_api():
    first = Mock()
    first.raise_for_status = Mock()
    second = Mock()
    second.raise_for_status = Mock()
    second.json.return_value = {
        "data": {
            "items": [
                {"code": "SH600000", "name": "浦发银行", "percent": 1.2, "exchange": "SH", "ad": 0},
                {"code": "AD", "name": "广告", "percent": 0, "exchange": "SH", "ad": 1},
            ]
        }
    }
    session = Mock()
    session.headers.update = Mock()
    session.get.side_effect = [first, second]

    with patch("backend.spiders.spiders.requests.Session", return_value=session):
        items = XueqiuHotstockSpider().fetch()

    assert len(items) == 1
    assert items[0]["platform"] == "雪球热门股票"
    assert items[0]["title"] == "浦发银行"
    assert items[0]["url"] == "https://xueqiu.com/s/SH600000"
    assert items[0]["hot"] == "1.2% SH"


def test_kuaishou_spider_reads_apollo_state():
    response = Mock()
    response.text = '''
    <script>window.__APOLLO_STATE__ = {"defaultClient":{"ROOT_QUERY":{"visionHotRank({\\"page\\":\\"home\\"})":{"id":"HotRank:1"}},"HotRank:1":{"items":[{"id":"VisionHotRankItem:a"},{"id":"VisionHotRankItem:b"}]},"VisionHotRankItem:a":{"name":"置顶标题","tagType":"置顶"},"VisionHotRankItem:b":{"name":"快手标题"}}};</script>
    '''

    with patch("backend.spiders.spiders.fetch_get", return_value=response):
        items = KuaishouSpider().fetch()

    assert len(items) == 1
    assert items[0]["platform"] == "快手"
    assert items[0]["title"] == "快手标题"
    assert items[0]["url"] == "https://www.kuaishou.com/search/video?searchKey=%E5%BF%AB%E6%89%8B%E6%A0%87%E9%A2%98"


def test_pcbeta_spider_uses_rss_helper():
    response = Mock()
    response.text = '''
    <rss><channel>
      <item><title>远景标题</title><link>https://bbs.pcbeta.com/thread-1-1-1.html</link><pubDate>Wed, 10 Jun 2026 09:30:00 GMT</pubDate></item>
    </channel></rss>
    '''

    with patch("backend.spiders.spiders.fetch_get", return_value=response):
        items = PcbetaSpider().fetch()

    assert items[0]["platform"] == "远景论坛"
    assert items[0]["title"] == "远景标题"
    assert items[0]["url"] == "https://bbs.pcbeta.com/thread-1-1-1.html"
    assert items[0]["time"] == "17:30"


def test_solidot_spider_uses_rss_helper():
    response = Mock()
    response.text = '''
    <rss><channel>
      <item><title>Solidot 标题</title><link>https://www.solidot.org/story?sid=1</link><pubDate>Wed, 10 Jun 2026 09:30:00 GMT</pubDate></item>
    </channel></rss>
    '''

    with patch("backend.spiders.spiders.fetch_get", return_value=response):
        items = SolidotSpider().fetch()

    assert items[0]["platform"] == "Solidot"
    assert items[0]["title"] == "Solidot 标题"
    assert items[0]["url"] == "https://www.solidot.org/story?sid=1"
    assert items[0]["time"] == "17:30"


@pytest.mark.parametrize(
    "spider_cls, platform, title, url",
    [
        (AihotSpider, "AIHOT", "AIHOT 标题", "https://aihot.virxact.com/item/1"),
        (ProductHuntSpider, "Product Hunt", "Product Hunt 标题", "https://www.producthunt.com/posts/item-1"),
        (ChongbuluoSpider, "虫部落", "虫部落标题", "https://www.chongbuluo.com/thread-1-1-1.html"),
    ],
)
def test_newsnow_rss_spiders_use_rss_helper(spider_cls, platform, title, url):
    response = Mock()
    response.text = f'''
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>{title}</title><link href="{url}"/><published>2026-06-10T09:30:00Z</published></entry>
    </feed>
    ''' if spider_cls is ProductHuntSpider else f'''
    <rss><channel>
      <item><title>{title}</title><link>{url}</link><pubDate>Wed, 10 Jun 2026 09:30:00 GMT</pubDate></item>
    </channel></rss>
    '''

    with patch("backend.spiders.spiders.fetch_get", return_value=response):
        items = spider_cls().fetch()

    assert items[0]["platform"] == platform
    assert items[0]["title"] == title
    assert items[0]["url"] == url
    assert items[0]["time"] == "17:30"


def test_aihot_spider_falls_back_to_rss_when_api_fails():
    api_error = requests.HTTPError("api down")
    rss_response = Mock()
    rss_response.text = '''
    <rss><channel>
      <item><title>AIHOT RSS 标题</title><link>https://aihot.virxact.com/rss/1</link><pubDate>Wed, 10 Jun 2026 09:30:00 GMT</pubDate></item>
    </channel></rss>
    '''

    with patch("backend.spiders.spiders.fetch_get", side_effect=[api_error, rss_response]):
        items = AihotSpider().fetch()

    assert items[0]["platform"] == "AIHOT"
    assert items[0]["title"] == "AIHOT RSS 标题"
    assert items[0]["url"] == "https://aihot.virxact.com/rss/1"


def test_producthunt_spider_falls_back_to_rss_when_api_fails():
    api_error = requests.HTTPError("api down")
    rss_response = Mock()
    rss_response.text = '''
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry><title>Product Hunt RSS 标题</title><link href="https://www.producthunt.com/posts/rss-1"/><published>2026-06-10T09:30:00Z</published></entry>
    </feed>
    '''

    with patch.dict("backend.spiders.spiders.os.environ", {"PRODUCTHUNT_API_TOKEN": "test-token"}), \
         patch("backend.spiders.spiders.fetch_post", side_effect=api_error), \
         patch("backend.spiders.spiders.fetch_get", return_value=rss_response):
        items = ProductHuntSpider().fetch()

    assert items[0]["platform"] == "Product Hunt"
    assert items[0]["title"] == "Product Hunt RSS 标题"
    assert items[0]["url"] == "https://www.producthunt.com/posts/rss-1"
