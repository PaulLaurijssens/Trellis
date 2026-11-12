"use client";
import RoadmapCanvas from './RoadmapCanvas';
import {useT} from '../lib/i18n';
import {usePlan} from '../lib/curriculum';
const id=x=>typeof x==='object'?x.id:x;
export default function LearningPath({graph,goal,due,onCreateGoal,onLearn,onGraph}) {
 const {lang,t}=useT();
 // The last known plan shows right away; updating happens in the background.
 const {plan,updating,error,retry}=usePlan(graph,lang);
 const nodes=new Map(graph.nodes.map(n=>[n.id,n]));
 const titles=[0,1,2,3].map(i=>t('roadmap.stageTitle.'+i));
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
 return <section className="learning-path whole-roadmap visual-roadmap"><header><span className="eyebrow">{t('roadmap.yourWholeKnowledgeMap')}</span><h1>{t('roadmap.yourLearningRoadmap')}</h1><p>{t('roadmap.aVisualCurriculumFrom')}</p></header>
 {!plan&&!error&&<div className="import-progress" role="status"><span className="spinner"/> {t('roadmap.organizingAllYourTopics')}</div>}
 {plan&&updating&&<p className="roadmap-updating" role="status"><span className="spinner"/> {t('roadmap.addingYourNewestTopics')}</p>}
 {error&&<p role="alert">{t('roadmap.theRoadmapCouldNot')} <button className="btn" onClick={retry}>{t('roadmap.retry')}</button></p>}
 {plan&&<><div className="roadmap-summary"><span>{plan.coverage} {t('roadmap.topicsSuggestedOrderingNot')}</span>{first&&<button className="btn primary" onClick={()=>onLearn(first.name)}>{course?(t('roadmap.continue')):(t('roadmap.startWith'))}{first.name} →</button>}</div>
 {!!plan.conflicts?.length&&<details className="roadmap-conflicts"><summary>{t('roadmap.learningOrderNotes')} · {plan.conflicts.length}</summary>{plan.conflicts.map((e,i)=><p key={i}>{nodes.get(e.source)?.name} → {nodes.get(e.target)?.name} <button className="textlink" onClick={()=>onGraph(nodes.get(e.target)?.name)}>{t('roadmap.viewTopic')} ↗</button></p>)}<p>{t('roadmap.youCanKeepLearning')}</p></details>}
 <RoadmapCanvas plan={plan} graph={graph} first={first} course={course} due={due} onLearn={onLearn} onGraph={onGraph} onStart={start}/>
 <p className="map-disclaimer">{t('roadmap.everySavedTopicIs')}</p></>}
 </section>;
}
