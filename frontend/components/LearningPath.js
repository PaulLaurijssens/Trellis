"use client";
import RoadmapCanvas from './RoadmapCanvas';
import {useT} from '../lib/i18n';
import {usePlan} from '../lib/curriculum';
const id=x=>typeof x==='object'?x.id:x;
export default function LearningPath({graph,goal,due,onCreateGoal,onLearn,onGraph}) {
 const {lang,t}=useT(), en=lang==='en';
 // Het laatst bekende plan staat meteen op het scherm; bijwerken gebeurt op de achtergrond.
 const {plan,updating,error,retry}=usePlan(graph,lang);
 const nodes=new Map(graph.nodes.map(n=>[n.id,n]));
 const titles=en?['Foundations','Core mechanisms','Capabilities & applications','Specialist frontiers']:['Fundamenten','Kernmechanismen','Mogelijkheden & toepassingen','Specialistische verdieping'];
 const sorted=plan?.groups?.slice().sort((a,b)=>a.stage-b.stage)||[];
 const course=goal&&goal.origin==='roadmap'&&goal.status==='active'?goal:null;
 // With a course: the next step is its first unticked step. Without: the first topic whose saved prerequisites are understood.
 const nextStep=course?.steps?.find(s=>!s.done);
 const first=course?(nextStep?nodes.get(nextStep.concept_id):null):sorted.flatMap(g=>g.ids).map(cid=>nodes.get(cid)).find(n=>n&&n.status!=='learned'&&!graph.links.some(e=>e.type==='PREREQUISITE_OF'&&id(e.target)===n.id&&nodes.get(id(e.source))?.status!=='learned'));
 // Start learning: continue the course, or make one from the route (root → next group, in stage order).
 async function start(routeGroups){
  if(course){if(nextStep)onLearn(nextStep.name);return;}
  if(!first||!routeGroups?.length){if(first)onLearn(first.name);return;}
  const groups=routeGroups.slice().sort((a,b)=>a.stage-b.stage);
  const ids=groups.flatMap(g=>g.ids).filter(cid=>nodes.get(cid));
  const last=groups.at(-1);
  const title=groups.length>1?groups[0].title+' → '+last.title:last.title;
  const ok=await onCreateGoal({title:title.slice(0,400),concept_ids:ids,origin:'roadmap'});
  if(ok!==false)onLearn(first.name);
 }
 return <section className="learning-path whole-roadmap visual-roadmap"><header><span className="eyebrow">{en?'Your whole knowledge map, organized for learning':'Je volledige kenniskaart als leerroute'}</span><h1>{en?'Your learning roadmap':'Je leerroute'}</h1><p>{en?'A visual curriculum from shared foundations to specialist frontiers.':'Een visueel leerprogramma van gedeelde fundamenten naar specialistische verdieping.'}</p></header>
 {!plan&&!error&&<div className="import-progress" role="status"><span className="spinner"/> {en?'Organizing all your topics into a learning roadmap…':'Alle onderwerpen worden in een leerroute geplaatst…'}</div>}
 {plan&&updating&&<p className="roadmap-updating" role="status"><span className="spinner"/> {en?'Adding your newest topics…':'Je nieuwste onderwerpen worden toegevoegd…'}</p>}
 {error&&<p role="alert">{en?'The roadmap could not be updated.':'De leerroute kon niet worden bijgewerkt.'} <button className="btn" onClick={retry}>{en?'Retry':'Opnieuw'}</button></p>}
 {plan&&<><div className="roadmap-summary"><span>{plan.coverage} {en?'topics · suggested ordering, not new graph connections':'onderwerpen · voorgestelde volgorde, geen nieuwe verbindingen'}</span>{first&&<button className="btn primary" onClick={()=>onLearn(first.name)}>{course?(en?'Continue: ':'Verder: '):(en?'Start with: ':'Begin met: ')}{first.name} →</button>}</div>
 {!!plan.conflicts?.length&&<details className="roadmap-conflicts"><summary>{en?'Learning order notes':'Notities over de leervolgorde'} · {plan.conflicts.length}</summary>{plan.conflicts.map((e,i)=><p key={i}>{nodes.get(e.source)?.name} → {nodes.get(e.target)?.name} <button className="textlink" onClick={()=>onGraph(nodes.get(e.target)?.name)}>{en?'View topic':'Bekijk onderwerp'} ↗</button></p>)}<p>{en?'You can keep learning. These saved prerequisites run against the suggested stage order; this does not mean your data is lost. The mentor still checks prerequisites when suggesting your next step. The relationship or the proposed stage may need review.':'Je kunt doorgaan met leren. Deze opgeslagen voorkennisrelaties lopen tegen de voorgestelde fasevolgorde in. Je gegevens blijven behouden. De mentor controleert voorkennis bij je volgende stap. De relatie of fase-indeling moet mogelijk worden herzien.'}</p></details>}
 <RoadmapCanvas plan={plan} graph={graph} first={first} course={course} due={due} en={en} onLearn={onLearn} onGraph={onGraph} onStart={start}/>
 <p className="map-disclaimer">{en?'Every saved topic is included. Stage placement is an AI proposal based on the subjects and saved relationships; parallel branches are alternatives, not compulsory steps. Topic-specific prerequisite routes remain in the sidebar.':'Alle opgeslagen onderwerpen zijn opgenomen. De fasen zijn een AI-voorstel op basis van onderwerpen en relaties. Parallelle takken zijn alternatieven. Specifieke voorkennisroutes blijven in de zijbalk.'}</p></>}
 </section>;
}
