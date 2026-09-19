// Normalize browser-specific recordings into mono 16-bit WAV for transcription.
export async function toWav(blob) {
  const context = new AudioContext();
  try {
    const audio = await context.decodeAudioData(await blob.arrayBuffer());
    const rate = 16000, length = Math.ceil(audio.duration * rate);
    if (audio.duration > 125) throw new Error('Recording too long');
    const offline = new OfflineAudioContext(1, length, rate);
    const source = offline.createBufferSource(); source.buffer = audio; source.connect(offline.destination); source.start();
    const samples = (await offline.startRendering()).getChannelData(0);
    const buffer = new ArrayBuffer(44 + samples.length * 2), view = new DataView(buffer);
    const str = (offset, value) => [...value].forEach((c, i) => view.setUint8(offset+i, c.charCodeAt(0)));
    str(0,'RIFF'); view.setUint32(4,36+samples.length*2,true); str(8,'WAVE'); str(12,'fmt ');
    view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true);
    view.setUint32(24,rate,true); view.setUint32(28,rate*2,true); view.setUint16(32,2,true); view.setUint16(34,16,true);
    str(36,'data'); view.setUint32(40,samples.length*2,true);
    samples.forEach((s,i)=>view.setInt16(44+i*2,Math.max(-1,Math.min(1,s))*(s<0?32768:32767),true));
    return new Blob([buffer], {type:'audio/wav'});
  } finally { await context.close(); }
}
