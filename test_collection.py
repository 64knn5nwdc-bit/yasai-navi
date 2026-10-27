"""Offline checks: access refusals stop; OCR never becomes a published offer."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request
import collect_candidates as collector
from source_access import SourceClient, SameHostRedirects, AccessStopped, normalized_url

class AccessTests(unittest.TestCase):
    def test_missing_robots_is_distinct_from_refusal(self):
        for code in [404,410,401,403,429,500,503]:
            with self.subTest(code=code):
                client=SourceClient()
                with patch.object(client,'raw',side_effect=HTTPError('https://example.org/robots.txt',code,'test',{},None)):
                    if code in (404,410):
                        self.assertIn(str(code),client.permission('https://example.org/flyer')[1])
                    else:
                        with self.assertRaises(AccessStopped):client.permission('https://example.org/flyer')
    def test_network_and_robots_disallow_stop(self):
        for result in [URLError('test'),(b'User-agent: *\nDisallow: /\n','text/plain')]:
            client=SourceClient()
            with patch.object(client,'raw',side_effect=result if isinstance(result,Exception) else None,return_value=result):
                with self.assertRaises(AccessStopped):client.permission('https://example.org/flyer')
    def test_https_and_same_host_only(self):
        self.assertIn('%E9',normalized_url('https://example.org/野菜'))
        for u in ['http://example.org','https://user:pass@example.org']:
            with self.assertRaises(AccessStopped):normalized_url(u)
        with self.assertRaises(AccessStopped):SameHostRedirects().redirect_request(Request('https://example.org/'),None,302,'',{},'https://other.org/')

class CandidateTests(unittest.TestCase):
    def test_links_and_metadata_are_restricted(self):
        url='https://yamakishi.co.jp/news/wp-content/uploads/2026/10/1027_kawakita_omote.jpg'
        parser=collector.FlyerLinks()
        parser.feed('<h2>有効期限 10/27(火)～10/29(木) 川北店のチラシ</h2><a href="'+url+'">表</a><a href="https://other.org/1027_kawakita_omote.jpg">外部</a><h2>リフォーム</h2><a href="'+url+'">対象外</a>')
        self.assertEqual(len(parser.links),1)
        self.assertEqual(collector.flyer_period(*parser.links[0])['end'],'2026-10-29')
        with self.assertRaises(ValueError):collector.flyer_period('有効期限 10/28～10/29',url)
    def test_ocr_quote_does_not_swallow_next_rows(self):
        head='level\tpage_num\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n'
        body='5\t1\t1\t1\t1\t1\t1\t1\t1\t20\t"\n5\t1\t2\t1\t1\t1\t10\t20\t10\t90\tキャベツ\n'
        lines=collector.ocr_lines(head+body)
        hints=collector.candidates(lines,'https://example.org/flyer.jpg','abc',11)
        self.assertEqual(len(hints),1)
        self.assertEqual(hints[0]['review_status'],'unverified')
        for key in ['price_yen','unit','valid_from','valid_until']:self.assertIsNone(hints[0][key])
    def test_failure_preserves_candidates_and_prices(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            original=b'{"candidates": ["previous"]}'
            (root/'review_candidates.json').write_bytes(original)
            (root/'prices.json').write_bytes(b'unchanged')
            with patch.object(collector,'ROOT',root),patch.object(collector.shutil,'which',return_value='/usr/bin/tesseract'),patch.object(collector,'collect',side_effect=AccessStopped('robots_http_403')),patch('sys.argv',['collect_candidates.py']):collector.main()
            self.assertEqual((root/'review_candidates.json').read_bytes(),original)
            self.assertEqual((root/'prices.json').read_bytes(),b'unchanged')
            self.assertEqual(json.loads((root/'collection_status.json').read_text())['status'],'collection_stopped')
