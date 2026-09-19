import unittest
from app.video import normalize

class VideoTests(unittest.TestCase):
    def test_no_quotes_and_valid_relationships(self):
        r=normalize({'accessible':True,'concepts':[{'name':n,'definition':'Definition','context':'Video discusses this','quote':'invented quote','start_sec':float('nan')} for n in ['A','B']], 'relations':[{'source':'A','target':'B','type':'PREREQUISITE_OF'},{'source':'A','target':'Missing','type':'PART_OF'}]})
        self.assertEqual(r['candidate_relations'],[{'from':'A','to':'B','type':'PREREQUISITE_OF','strength':0.7}])
        self.assertEqual(r['candidates'][0]['mentions'][0]['quote'],'')
        self.assertIsNone(r['candidates'][0]['mentions'][0]['start_sec'])
        self.assertIn('not a verified quotation',r['candidates'][0]['context'])
    def test_inaccessible_or_empty_fails(self):
        for value in [{}, {'accessible':False}, {'accessible':True,'concepts':[]}]:
            with self.assertRaises(ValueError):normalize(value)
    def test_video_attachment_is_not_dropped_by_adapter(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        from app import video
        import json
        payload={'accessible':True,'concepts':[{'name':'A','definition':'Meaning','context':'Discussed'}]}
        response=SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'status':'completed','steps':[{'type':'model_output','content':[{'type':'text','text':json.dumps(payload)}]}]})
        with patch.object(video.httpx,'post',return_value=response) as call:
            video.analyze('https://www.youtube.com/watch?v=AxzcWOxzkiw')
        attachment=call.call_args.kwargs['json']['input'][0]
        self.assertEqual(attachment,{'type':'video','uri':'https://www.youtube.com/watch?v=AxzcWOxzkiw','processing':'agentic'})
    def test_caption_failure_routes_to_video_and_review(self):
        from unittest.mock import patch
        from app.main import ingest_youtube, IngestYoutube
        result={'title':'Video','candidates':[],'meta':{'analysis_method':'ai_video_analysis'}}
        with patch('youtube_transcript_api.YouTubeTranscriptApi.fetch',side_effect=RuntimeError('blocked')), patch('app.video.analyze',return_value=result) as direct, patch('app.extract.stage_result',return_value={'source_id':'pending',**result}) as stage:
            value=ingest_youtube(IngestYoutube(url='https://youtu.be/AxzcWOxzkiw'))
        self.assertEqual(value['source_id'],'pending')
        self.assertEqual(direct.call_args.args[0],'https://www.youtube.com/watch?v=AxzcWOxzkiw')
        self.assertEqual(stage.call_args.args[1],'youtube')
