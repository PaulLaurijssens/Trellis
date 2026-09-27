"use client";
import {useEffect, useRef, useState} from 'react';
import {useT} from '../lib/i18n';
import {toWav} from '../lib/voice';

export default function VoiceInput({disabled, onText, onBusy}) {
  const {lang}=useT(); const en=lang==='en';
  const [phase,setPhase]=useState('idle'),[error,setError]=useState(''),[seconds,setSeconds]=useState(0);
  const current=useRef(null), callback=useRef(onText); callback.current=onText;
  const stopTracks=s=>s.stream?.getTracks().forEach(t=>t.stop());
  function cancel() {
    const s=current.current; current.current=null;
    if(s){clearInterval(s.timer);s.abort?.abort();if(s.recorder?.state==='recording')s.recorder.stop();stopTracks(s);}
    setPhase('idle');onBusy(false);
  }
  useEffect(()=>()=>{const s=current.current;current.current=null;if(s){clearInterval(s.timer);s.abort?.abort();if(s.recorder?.state==='recording')s.recorder.stop();stopTracks(s);}onBusy(false);},[]);
  async function start() {
    if(current.current)return;
    if(!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder){setError(en?'Voice recording is unavailable in this browser. Try Chrome or Safari.':'Opnemen is niet beschikbaar in deze browser. Probeer Chrome of Safari.');return;}
    const s={};current.current=s;setError('');setSeconds(0);setPhase('permission');onBusy(true);
    try {
      s.stream=await navigator.mediaDevices.getUserMedia({audio:true});
      if(current.current!==s){stopTracks(s);return;}
      s.recorder=new MediaRecorder(s.stream);const chunks=[];
      s.recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
      s.recorder.onerror=()=>{if(current.current===s){cancel();setError(en?'Recording failed. Please try again.':'Opnemen mislukt. Probeer opnieuw.');}};
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
          if(!response.ok)throw new Error('Transcription failed');
          const result=await response.json();if(current.current!==s)return;
          if(typeof result.text!=='string'||!result.text.trim())setError(en?'No speech detected. Please try again.':'Geen spraak herkend. Probeer opnieuw.');
          else callback.current(result.text.trim());
        }catch(e){if(current.current===s)setError(en?'Could not transcribe. Please record again or type your question.':'Transcriptie mislukt. Neem opnieuw op of typ je vraag.');}
        finally{if(current.current===s){current.current=null;setPhase('idle');onBusy(false);}}
      };
      s.recorder.start();setPhase('recording');const started=Date.now();
      s.timer=setInterval(()=>{const elapsed=Math.floor((Date.now()-started)/1000);setSeconds(elapsed);if(elapsed>=120&&s.recorder.state==='recording')s.recorder.stop();},250);
    }catch(e){if(current.current===s){cancel();setError(e.name==='NotAllowedError'?(en?'Microphone access was denied. Allow it in your browser settings and try again.':'Microfoon geweigerd. Geef toegang in je browser en probeer opnieuw.'):(en?'Microphone unavailable. Check your microphone and try again.':'Microfoon niet beschikbaar. Controleer je microfoon.'));}}
  }
  return <div className="voice-control">
    <button type="button" className={'voice-button '+phase} disabled={disabled&&phase==='idle'||phase==='permission'||phase==='transcribing'} onClick={()=>phase==='recording'?current.current?.recorder.stop():start()} aria-label={phase==='recording'?(en?'Stop recording':'Stop opname'):(en?'Record a question':'Vraag inspreken')} title={en?'Record a question':'Vraag inspreken'}>
      {phase==='recording'?<span aria-hidden="true">■</span>:phase==='permission'||phase==='transcribing'?<span className="spinner"/>:<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true"><rect x="9" y="2" width="6" height="12" rx="3"/><path d="M5 10v2a7 7 0 0014 0v-2M12 19v3M8 22h8"/></svg>}
    </button>
    <div className="voice-status" role={error?'alert':'status'}>{error|| (phase==='recording'?`${en?'Recording':'Opname'} ${seconds}s / 120s`:phase==='transcribing'?(en?'Transcribing…':'Omzetten…'):phase==='permission'?(en?'Allow microphone access…':'Geef microfoontoegang…'):'')}{phase!=='idle'&&<button type="button" className="textlink" onClick={cancel}>{en?'Cancel':'Annuleren'}</button>}</div>
  </div>;
}
