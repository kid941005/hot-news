from unittest.mock import Mock, patch

import requests

from backend.spiders.spiders import BaiduSpider, GitHubSpider


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


def test_github_spider_rejects_http_error_status():
    response = failed_response()

    with patch("backend.spiders.spiders.requests.get", return_value=response):
        assert GitHubSpider().fetch() == []

    response.raise_for_status.assert_called_once()
