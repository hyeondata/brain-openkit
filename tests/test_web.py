import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from urllib.parse import quote

from brain_openkit.web import make_server


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.note = self.vault / "한글.md"
        self.note.write_bytes('# 한국어\r\n\r\n검색 <script>alert("source")</script>\r\n'.encode())
        self.before = hashlib.sha256(self.note.read_bytes()).hexdigest()
        self.server = make_server(self.vault, self.root / "cache", port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def request(self, path, method="GET", headers=None):
        connection = HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, path, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_search_returns_exact_sources_without_writing_them(self):
        status, headers, data = self.request('/api/search?q=' + quote('검색'))
        self.assertEqual(status, 200)
        self.assertIn('application/json', headers['Content-Type'])
        result = json.loads(data)
        self.assertEqual(result['provider'], 'none')
        self.assertEqual(result['results'][0]['path'], '한글.md')
        self.assertIn('<script>', result['results'][0]['text'])
        self.assertEqual(hashlib.sha256(self.note.read_bytes()).hexdigest(), self.before)

    def test_page_has_safe_text_renderer_and_no_external_assets(self):
        status, headers, data = self.request('/')
        self.assertEqual(status, 200)
        self.assertIn(b'textContent', data)
        self.assertNotIn(b'innerHTML', data)
        self.assertNotIn(b'https://', data)
        self.assertIn("default-src 'none'", headers['Content-Security-Policy'])
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')

    def test_wrong_host_cross_origin_and_write_requests_are_rejected(self):
        for headers in ({'Host': 'attacker.invalid'}, {'Origin': 'https://attacker.invalid'},
                        {'Sec-Fetch-Site': 'cross-site'}):
            with self.subTest(headers=headers):
                self.assertEqual(self.request('/api/search?q=test', headers=headers)[0], 403)
        self.assertEqual(self.request('/api/search?q=test', method='POST')[0], 405)

    def test_invalid_query_and_unknown_paths(self):
        for path in ('/api/search', '/api/search?q=', '/api/search?q=a&q=b',
                     '/api/search?q=%FF', '/api/search?q=x&extra=y', '/api/search?q=' + 'x' * 8001):
            with self.subTest(path=path[:80]):
                self.assertEqual(self.request(path)[0], 400)
        self.assertEqual(self.request('/../note.md')[0], 404)

    def test_only_loopback_bind_is_exposed(self):
        self.assertEqual(self.server.server_address[0], '127.0.0.1')

    def test_browser_preopened_connection_does_not_block_search(self):
        with socket.create_connection(self.server.server_address, timeout=3):
            self.assertEqual(self.request('/api/search?q=' + quote('검색'))[0], 200)

    def test_oversized_utf8_url_returns_clear_json_error(self):
        status, headers, data = self.request('/api/search?q=' + quote('한' * 8000))
        self.assertEqual(status, 414)
        self.assertIn('application/json', headers['Content-Type'])
        self.assertIn('shorten', json.loads(data)['error'])


if __name__ == '__main__':
    unittest.main()
