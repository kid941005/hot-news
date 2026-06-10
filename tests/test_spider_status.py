from unittest.mock import Mock, patch

import requests

from backend.spiders.spiders import BaiduSpider, FastbullSpider, GitHubSpider, IfengSpider, Jin10Spider, ZaobaoSpider


class BaiduSuccessResponse:
    text = '<!--s-data:{"data":{"cards":[{"content":[{"word":"A&B #测试","isTop":false}]}]}}-->'

    def __init__(self):
        self.raise_for_status = Mock()


def failed_response():
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError("bad status")
    response.text = "<!--s-data:{}-->"
    response.json.return_value = {"items": [{"name": "repo"}]}
    return response


def test_baidu_spider_rejects_http_error_status():
    response = failed_response()

    with patch("backend.spiders.spiders.requests.get", return_value=response):
        assert BaiduSpider().fetch() == []

    response.raise_for_status.assert_called_once()


def test_baidu_spider_encodes_search_keyword_url():
    response = BaiduSuccessResponse()

    with patch("backend.spiders.spiders.requests.get", return_value=response):
        items = BaiduSpider().fetch()

    assert items[0]["url"] == "https://www.baidu.com/s?wd=A%26B+%23%E6%B5%8B%E8%AF%95"
    response.raise_for_status.assert_called_once()


def test_github_spider_rejects_http_error_status():
    response = failed_response()

    with patch("backend.spiders.spiders.requests.get", return_value=response):
        assert GitHubSpider().fetch() == []

    response.raise_for_status.assert_called_once()


def test_ifeng_spider_reads_newsnow_hotnews_data():
    response = Mock()
    response.raise_for_status = Mock()
    response.text = 'var allData = {"hotNews1":[{"title":"凤凰标题一","url":"https://news.ifeng.com/a","newsTime":"2026-06-10"},{"title":"凤凰标题二","url":"https://news.ifeng.com/b","newsTime":""}]};'

    with patch("backend.spiders.spiders.requests.get", return_value=response):
        items = IfengSpider().fetch()

    assert [item["title"] for item in items] == ["凤凰标题一", "凤凰标题二"]
    assert items[0]["platform"] == "凤凰"
    assert items[0]["url"] == "https://news.ifeng.com/a"
    assert items[0]["time"] == "2026-06-10"


def test_ifeng_spider_falls_back_when_hotnews_empty():
    response = Mock()
    response.raise_for_status = Mock()
    response.status_code = 200
    response.text = '''
    <html><body>
      <script>var allData = {"hotNews1": []};</script>
      <a href="https://news.ifeng.com/c/1" title="凤凰兜底一"></a>
      <a href="https://news.ifeng.com/c/2">凤凰兜底二</a>
    </body></html>
    '''

    with patch("backend.spiders.spiders.requests.get", return_value=response):
        items = IfengSpider().fetch()

    assert [item["title"] for item in items] == ["凤凰兜底一", "凤凰兜底二"]
    assert items[0]["platform"] == "凤凰"
    assert items[0]["url"] == "https://news.ifeng.com/c/1"


def test_ifeng_spider_falls_back_without_alldata():
    response = Mock()
    response.raise_for_status = Mock()
    response.status_code = 200
    response.text = '<a href="https://news.ifeng.com/c/1" title="凤凰兜底一"></a>'

    with patch("backend.spiders.spiders.requests.get", return_value=response):
        items = IfengSpider().fetch()

    assert len(items) == 1
    assert items[0]["title"] == "凤凰兜底一"


def test_jin10_spider_reads_newest_js():
    response = Mock()
    response.raise_for_status = Mock()
    response.text = 'var newest = [{"id":"1","time":"2026-06-10 09:43:22","type":0,"important":1,"channel":[1],"data":{"content":"【金十标题】详情"}},{"id":"2","time":"2026-06-10 09:40:00","type":0,"important":0,"channel":[5],"data":{"content":"过滤"}}];'

    with patch("backend.spiders.spiders.requests.get", return_value=response):
        items = Jin10Spider().fetch()

    assert len(items) == 1
    assert items[0]["platform"] == "金十数据"
    assert items[0]["title"] == "金十标题"
    assert items[0]["url"] == "https://flash.jin10.com/detail/1"
    assert items[0]["time"] == "09:43"


def test_zaobao_spider_reads_gb2312_realtime_page():
    response = Mock()
    response.raise_for_status = Mock()
    html = '<div class="list-block"><a class="item" href="/realtime/1.html"><span class="eps">早报标题</span><span class="pdt10">2026-06-10 09:30</span></a></div>'
    response.content = html.encode("gb2312")

    with patch("backend.spiders.spiders.requests.get", return_value=response):
        items = ZaobaoSpider().fetch()

    assert items[0]["platform"] == "联合早报"
    assert items[0]["title"] == "早报标题"
    assert items[0]["url"] == "https://www.zaochenbao.com/realtime/1.html"
    assert items[0]["time"] == "09:30"


def test_fastbull_spider_reads_api_body_message():
    response = Mock()
    response.raise_for_status = Mock()
    response.json.return_value = {
        "bodyMessage": '{"pageDatas":[{"newsId":"1","path":"fastbull-title-1","title":"法布标题","point":12,"pubTime":1781048143634}]}'
    }

    with patch("backend.spiders.spiders.requests.post", return_value=response):
        items = FastbullSpider().fetch()

    assert items[0]["platform"] == "法布财经"
    assert items[0]["title"] == "法布标题"
    assert items[0]["url"] == "https://www.fastbull.com/cn/news-detail/fastbull-title-1"
    assert items[0]["hot"] == "12"
