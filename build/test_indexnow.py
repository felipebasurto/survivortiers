"""IndexNow: clave, lotes, host y la petición, sin red (urlopen simulado).

    python3 -m unittest build/test_indexnow.py
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))

import sitefixture  # noqa: E402
import indexnow  # noqa: E402
import legal  # noqa: E402

KEY = "0123456789abcdef0123456789abcdef"
SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>{u}/</loc></url>
  <url><loc>{u}/en/</loc></url>
  <url><loc>{u}/</loc></url>
</urlset>
""".replace("{u}", legal.SITE_URL)


class KeyFile(unittest.TestCase):
    def test_exactly_one_key_file_with_matching_content(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / f"{KEY}.txt").write_text(KEY + "\n", encoding="utf8")
            (src / "notes.txt").write_text("x", encoding="utf8")
            self.assertEqual(indexnow.key_file(src).name, f"{KEY}.txt")

    def test_mismatched_content_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)
            (src / f"{KEY}.txt").write_text("otra cosa", encoding="utf8")
            with self.assertRaises(indexnow.IndexNowError):
                indexnow.key_file(src)

    def test_missing_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(indexnow.IndexNowError):
                indexnow.key_file(Path(d))

    def test_repo_key_file_is_valid(self) -> None:
        path = indexnow.key_file()
        self.assertRegex(path.stem, r"^[0-9a-f]{32}$")


class Payload(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sitefixture.ensure_site()

    def test_body_has_host_key_location_and_urls(self) -> None:
        body = indexnow.payloads([f"{legal.SITE_URL}/", f"{legal.SITE_URL}/en/"], KEY)[0]
        self.assertEqual(body["host"], "survivortiers.pages.dev")
        self.assertEqual(body["key"], KEY)
        self.assertEqual(body["keyLocation"], f"{legal.SITE_URL}/{KEY}.txt")
        self.assertEqual(body["urlList"], [f"{legal.SITE_URL}/", f"{legal.SITE_URL}/en/"])

    def test_batches_stay_within_ten_thousand(self) -> None:
        urls = [f"{legal.SITE_URL}/p/{i}/" for i in range(indexnow.BATCH * 2 + 5)]
        bodies = indexnow.payloads(urls, KEY)
        self.assertEqual([len(b["urlList"]) for b in bodies], [indexnow.BATCH, indexnow.BATCH, 5])

    def test_foreign_host_is_refused(self) -> None:
        with self.assertRaises(indexnow.IndexNowError):
            indexnow.payloads(["https://example.com/x"], KEY)

    def test_sitemap_urls_are_deduplicated_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            site = Path(d)
            (site / "sitemap.xml").write_text(SITEMAP, encoding="utf8")
            self.assertEqual(indexnow.sitemap_urls(site), [f"{legal.SITE_URL}/", f"{legal.SITE_URL}/en/"])


class Submit(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        sitefixture.ensure_site()

    def test_posts_json_to_the_endpoint(self) -> None:
        body = indexnow.payloads([f"{legal.SITE_URL}/"], KEY)[0]
        resp = mock.MagicMock()
        resp.status = 200
        resp.__enter__.return_value = resp
        with mock.patch("indexnow.urllib.request.urlopen", return_value=resp) as urlopen:
            self.assertEqual(indexnow.submit(body), 200)
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "https://api.indexnow.org/indexnow")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(json.loads(req.data.decode("utf8")), body)

    def test_dry_run_does_not_touch_the_network(self) -> None:
        with mock.patch("indexnow.urllib.request.urlopen") as urlopen, mock.patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(indexnow.main(["--dry-run"]), 0)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
