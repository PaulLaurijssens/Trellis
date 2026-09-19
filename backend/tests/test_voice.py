import io
import wave
import unittest
from unittest.mock import AsyncMock, patch
from types import SimpleNamespace
from app import voice

def wav(seconds=1, channels=1):
    stream=io.BytesIO()
    with wave.open(stream,'wb') as w:
        w.setnchannels(channels);w.setsampwidth(2);w.setframerate(16000);w.writeframes(b'\0\0'*16000*seconds*channels)
    return stream.getvalue()

class VoiceTests(unittest.IsolatedAsyncioTestCase):
    def test_valid_and_invalid_recordings(self):
        voice.validate_audio(wav())
        for data in [b'not audio',wav(0),wav(126),wav(channels=2),wav()[:-200]]:
            with self.assertRaises(ValueError):voice.validate_audio(data)

    @patch('app.voice.litellm.acompletion',new_callable=AsyncMock)
    async def test_transcription_no_memory_context(self,complete):
        complete.return_value=SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='What is a neural network?'))])
        self.assertEqual(await voice.transcribe(wav(),'en'),'What is a neural network?')
        content=complete.call_args.kwargs['messages'][0]['content']
        self.assertEqual(content[1]['input_audio']['format'],'wav')
        self.assertIn('Do not answer',content[0]['text'])
