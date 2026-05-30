from unittest.mock import Mock, patch

import requests

from backend.spiders.spiders import BaiduSpider, GitHubSpider


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
