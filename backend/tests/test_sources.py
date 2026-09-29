"""PDF / audio / URL / podcast ingest helpers, without network or model calls."""
import importlib
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


class SourcesTests(unittest.TestCase):
    def setUp(self):
        pkg = types.ModuleType('sources_test_app')
        pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'app')]
        fake_llm = types.ModuleType('sources_test_app.llm'); fake_llm.EXTRACT_MODEL = 'gemini/flash'
        self.modules = patch.dict(sys.modules, {'sources_test_app': pkg, 'sources_test_app.llm': fake_llm,
                                                'httpx': MagicMock(), 'litellm': MagicMock()})
        self.modules.start(); self.addCleanup(self.modules.stop)
        self.sources = importlib.import_module('sources_test_app.sources')

    def test_kind_by_name_or_content_type(self):
        s = self.sources
        self.assertEqual(s.kind_of('paper.PDF', None), 'pdf')
        self.assertEqual(s.kind_of('x', 'application/pdf'), 'pdf')
        self.assertEqual(s.kind_of('episode.m4a', 'application/octet-stream'), 'audio')
        self.assertEqual(s.kind_of('notes.md', None), 'text')
        with self.assertRaises(s.SourceError):
            s.kind_of('photo.png', 'image/png')

    def test_private_and_bad_addresses_are_refused_before_any_fetch(self):
        s = self.sources
        for url in ('ftp://x', 'http://localhost:8000/x', 'http://192.168.1.5/a', 'http://10.0.0.1/', 'not a url'):
            with self.assertRaises(s.SourceError):
                s._fetch(url, 1000)

    def test_podcast_feed_lists_episodes_with_audio_only(self):
        s = self.sources
        rss = b'''<rss><channel><title>My Show</title>
          <item><title>Ep 1</title><enclosure url="https://cdn/ep1.mp3" length="1234" type="audio/mpeg"/><pubDate>Mon</pubDate></item>
          <item><title>No audio</title></item>
          <item><title>Ep 2</title><enclosure url="https://cdn/ep2.mp3" length="x"/></item></channel></rss>'''
        with patch.object(s, '_fetch', return_value=(rss, 'application/rss+xml')):
            out = s.podcast_episodes('https://feed')
        self.assertEqual(out['title'], 'My Show')
        self.assertEqual([e['title'] for e in out['episodes']], ['Ep 1', 'Ep 2'])
        self.assertEqual(out['episodes'][0]['bytes'], 1234); self.assertIsNone(out['episodes'][1]['bytes'])

    def test_audio_size_cap_and_format(self):
        s = self.sources
        with self.assertRaises(s.SourceError):
            s.audio_transcript(b'0' * (s.MAX_AUDIO_BYTES + 1), 'audio/mpeg', 'a.mp3', 'English')
        with self.assertRaises(s.SourceError):
            s.audio_transcript(b'0', 'application/zip', 'a.zip', 'English')

    def test_url_fetch_switch(self):
        s = self.sources
        with patch.object(s, 'URL_FETCH', False):
            with self.assertRaises(s.SourceError) as err:
                s._fetch('https://example.org', 1000)
            self.assertIn('INGEST_URL_FETCH', str(err.exception))


if __name__ == '__main__':
    unittest.main()


class CleanUrlTests(unittest.TestCase):
    def test_tracking_parameters_are_dropped(self):
        import importlib, sys, types
        from unittest.mock import MagicMock, patch
        pkg = types.ModuleType('sources_clean_app'); pkg.__path__ = [str(Path(__file__).resolve().parents[1] / 'app')]
        fake_llm = types.ModuleType('sources_clean_app.llm'); fake_llm.EXTRACT_MODEL = 'x'
        with patch.dict(sys.modules, {'sources_clean_app': pkg, 'sources_clean_app.llm': fake_llm, 'httpx': MagicMock(), 'litellm': MagicMock()}):
            s = importlib.import_module('sources_clean_app.sources')
            self.assertEqual(s.clean_url('https://a.b/x/?li_fat_id=1&utm_source=li&page=2#frag'), 'https://a.b/x/?page=2')
            self.assertEqual(s.clean_url('https://a.b/x'), 'https://a.b/x')
