"use client";
import { httpError } from "../lib/errors";
import {useEffect, useRef, useState} from 'react';
import {useT} from '../lib/i18n';
import {toWav} from '../lib/voice';

export default function VoiceInput({disabled, onText, onBusy}) {
  const {t,lang}=useT();
  const [phase,setPhase]=useState('idle'),[error,setError]=useState(''),[seconds,setSeconds]=useState(0);
  const current=useRef(null), callback=useRef(onText); callback.current=onText;
  const stopTracks=s=>s.stream?.getTracks().forEach(track=>track.stop());
  function cancel() {
    const s=current.current; current.current=null;
    if(s){clearInterval(s.timer);s.abort?.abort();if(s.recorder?.state==='recording')s.recorder.stop();stopTracks(s);}
    setPhase('idle');onBusy(false);
  }
  useEffect(()=>()=>{const s=current.current;current.current=null;if(s){clearInterval(s.timer);s.abort?.abort();if(s.recorder?.state==='recording')s.recorder.stop();stopTracks(s);}onBusy(false);},[]);
  async function start() {
    if(current.current)return;
    if(!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder){setError(t('voice.voiceRecordingIsUnavailable'));return;}
    const s={};current.current=s;setError('');setSeconds(0);setPhase('permission');onBusy(true);
    try {
      s.stream=await navigator.mediaDevices.getUserMedia({audio:true});
      if(current.current!==s){stopTracks(s);return;}
      s.recorder=new MediaRecorder(s.stream);const chunks=[];
      s.recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
      s.recorder.onerror=()=>{if(current.current===s){cancel();setError(t('voice.recordingFailedPleaseTry'));}};
      s.recorder.onstop=async()=>{
        clearInterval(s.timer);stopTracks(s);if(current.current!==s)return;
        setPhase('transcribing');
        try {
          const wav=await toWav(new Blob(chunks,{type:s.recorder.mimeType}));
          if(current.current!==s)return;
          s.abort=new AbortController();
          const timeout=setTimeout(()=>s.abort.abort(),60000);
          let response;
          try {response=await fetch((process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000')+'/voice/transcribe?language='+lang,{credentials:'include',method:'POST',headers:{'Content-Type':'audio/wav'},body:wav,signal:s.abort.signal});}finally{clearTimeout(timeout);}
          if(!response.ok){let data=null;try{data=await response.json();}catch{}const err=httpError(response.status,data);err.show=!!err.code;throw err;}
          const result=await response.json();if(current.current!==s)return;
          if(typeof result.text!=='string'||!result.text.trim())setError(t('voice.noSpeechDetectedPlease'));
          else callback.current(result.text.trim());
        }catch(e){if(current.current===s)setError(e.show?e.message:t('voice.couldNotTranscribePlease'));}
        finally{if(current.current===s){current.current=null;setPhase('idle');onBusy(false);}}
      };
      s.recorder.start();setPhase('recording');const started=Date.now();
      s.timer=setInterval(()=>{const elapsed=Math.floor((Date.now()-started)/1000);setSeconds(elapsed);if(elapsed>=120&&s.recorder.state==='recording')s.recorder.stop();},250);
    }catch(e){if(current.current===s){cancel();setError(e.name==='NotAllowedError'?(t('voice.microphoneAccessWasDenied')):(t('voice.microphoneUnavailableCheckYour')));}}
  }
  return <div className="voice-control">
    <button type="button" className={'voice-button '+phase} disabled={disabled&&phase==='idle'||phase==='permission'||phase==='transcribing'} onClick={()=>phase==='recording'?current.current?.recorder.stop():start()} aria-label={phase==='recording'?(t('voice.stopRecording')):(t('voice.recordAQuestion'))} title={t('voice.recordAQuestion')}>
      {phase==='recording'?<span aria-hidden="true">■</span>:phase==='permission'||phase==='transcribing'?<span className="spinner"/>:<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0014 0v-2M12 19v3M8 22h8"/></svg>}
    </button>
    <div className="voice-status" role={error?'alert':'status'}>{error|| (phase==='recording'?`${t('voice.recording')} ${seconds}s / 120s`:phase==='transcribing'?(t('voice.transcribing')):phase==='permission'?(t('voice.allowMicrophoneAccess')):'')}{phase!=='idle'&&<button type="button" className="textlink" onClick={cancel}>{t('voice.cancel')}</button>}</div>
  </div>;
}
