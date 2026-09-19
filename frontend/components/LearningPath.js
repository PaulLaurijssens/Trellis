"use client";
import {useEffect,useMemo,useState} from 'react';
import RoadmapCanvas from './RoadmapCanvas';
import {useT} from '../lib/i18n';
const id=x=>typeof x==='object'?x.id:x;
export default function LearningPath({graph,onLearn,onGraph}) {
 const {lang,t}=useT(), en=lang==='en';
 const [plan,setPlan]=useState(null),[error,setError]=useState(false),[retry,setRetry]=useState(0);
 const snapshot=useMemo(()=>JSON.stringify({nodes:graph.nodes.map(({id,name,definition,domain})=>({id,name,definition,domain})),links:graph.links.map(e=>({source:id(e.source),target:id(e.target),type:e.type})),language:lang}),[graph,lang]);
 useEffect(()=>{let alive=true;const abort=new AbortController();setPlan(null);setError(false);fetch((process.env.NEXT_PUBLIC_API_URL||'http://localhost:8000')+'/curriculum',{method:'POST',headers:{'Content-Type':'application/json'},body:snapshot,signal:abort.signal}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(p=>{if(alive)setPlan(p);}).catch(()=>{if(alive)setError(true);});return()=>{alive=false;abort.abort();};},[snapshot,retry]);
 const nodes=new Map(graph.nodes.map(n=>[n.id,n]));
 const titles=en?['Foundations','Core mechanisms','Capabilities & applications','Specialist frontiers']:['Fundamenten','Kernmechanismen','Mogelijkheden & toepassingen','Specialistische verdieping'];
 const sorted=plan?.groups?.slice().sort((a,b)=>a.stage-b.stage)||[];
 const first=sorted.flatMap(g=>g.ids).map(cid=>nodes.get(cid)).find(n=>n&&n.status!=='learned'&&!graph.links.some(e=>e.type==='PREREQUISITE_OF'&&id(e.target)===n.id&&nodes.get(id(e.source))?.status!=='learned'));
 return <section className="learning-path whole-roadmap visual-roadmap"><header><span className="eyebrow">{en?'Your whole knowledge map, organized for learning':'Je volledige kenniskaart als leerroute'}</span><h1>{en?'From foundations to new frontiers':'Van fundamenten naar nieuwe grenzen'}</h1><p>{en?'A suggested curriculum across every topic. Start with shared foundations, then follow the branches that interest you.':'Een voorgesteld leerprogramma voor alle onderwerpen. Begin bij gedeelde fundamenten en verken daarna de vertakkingen.'}</p></header>
 {!plan&&!error&&<div className="import-progress" role="status"><span className="spinner"/> {en?'Organizing all your topics into a learning roadmap…':'Alle onderwerpen worden in een leerroute geplaatst…'}</div>}
 {error&&<p role="alert">{en?'The roadmap could not be generated.':'De leerroute kon niet worden gemaakt.'} <button className="btn" onClick={()=>setRetry(x=>x+1)}>{en?'Retry':'Opnieuw'}</button></p>}
 {plan&&<><div className="roadmap-summary"><span>{plan.coverage} {en?'topics · suggested ordering, not new graph connections':'onderwerpen · voorgestelde volgorde, geen nieuwe verbindingen'}</span>{first&&<button className="btn primary" onClick={()=>onLearn(first.name)}>{en?'Start with: ':'Begin met: '}{first.name} →</button>}</div>
 {!!plan.conflicts?.length&&<details className="roadmap-conflicts"><summary>{en?'Learning order notes':'Notities over de leervolgorde'} · {plan.conflicts.length}</summary>{plan.conflicts.map((e,i)=><p key={i}>{nodes.get(e.source)?.name} → {nodes.get(e.target)?.name} <button className="textlink" onClick={()=>onGraph(nodes.get(e.target)?.name)}>{en?'View topic':'Bekijk onderwerp'} ↗</button></p>)}<p>{en?'You can keep learning. These saved prerequisites run against the suggested stage order; this does not mean your data is lost. The mentor still checks prerequisites when suggesting your next step. The relationship or the proposed stage may need review.':'Je kunt doorgaan met leren. Deze opgeslagen voorkennisrelaties lopen tegen de voorgestelde fasevolgorde in. Je gegevens blijven behouden. De mentor controleert voorkennis bij je volgende stap. De relatie of fase-indeling moet mogelijk worden herzien.'}</p></details>}
 <RoadmapCanvas plan={plan} graph={graph} first={first} en={en} onLearn={onLearn} onGraph={onGraph}/>
 <p className="map-disclaimer">{en?'Every saved topic is included. Stage placement is an AI proposal based on the subjects and saved relationships; parallel branches are alternatives, not compulsory steps. Topic-specific prerequisite routes remain in the sidebar.':'Alle opgeslagen onderwerpen zijn opgenomen. De fasen zijn een AI-voorstel op basis van onderwerpen en relaties. Parallelle takken zijn alternatieven. Specifieke voorkennisroutes blijven in de zijbalk.'}</p></>}
 </section>;
}
