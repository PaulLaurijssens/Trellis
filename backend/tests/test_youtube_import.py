import unittest
from app import transcript

class YoutubeImportTests(unittest.TestCase):
    def test_supported_urls(self):
        for url in ['https://www.youtube.com/watch?v=AxzcWOxzkiw&t=3','https://youtu.be/AxzcWOxzkiw?si=abc','https://youtube.com/shorts/AxzcWOxzkiw']:
            self.assertEqual(transcript.youtube_id(url),'AxzcWOxzkiw')
        for url in ['https://evil.test/watch?v=AxzcWOxzkiw','https://youtube.com/watch?v=bad','file:///AxzcWOxzkiw']:
            with self.assertRaises(ValueError):transcript.youtube_id(url)
    def test_actionable_error_without_library_dump(self):
        RequestBlocked=type('RequestBlocked',(Exception,),{})
        message=transcript.fetch_error(RequestBlocked('private diagnostics'),'en')
        self.assertIn('blocking',message);self.assertIn('Paste transcript',message)
        self.assertNotIn('private diagnostics',message)
    def test_pasted_timestamps_preserved(self):
        data=transcript.parse('0:00\nthis is the opening sentence\n0:15\nthis is the next sentence')
        self.assertTrue(data['timed']);self.assertEqual([s['start_sec'] for s in data['segments']],[0,15])
