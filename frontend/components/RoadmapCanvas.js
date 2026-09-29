"use client";
import {useEffect,useMemo,useRef,useState} from 'react';
import {roadmapLayout,routeKeys,STAGE_WIDTH,STAGE_LEFT} from '../lib/roadmap-layout.mjs';
// One small line icon per stage: foundations, mechanisms, applications, frontiers.
const ICONS=[
 <svg viewBox="0 0 20 20" key="0"><path d="M3 6.5 10 3l7 3.5-7 3.5z"/><path d="M3 10.5 10 14l7-3.5"/><path d="M3 14.5 10 18l7-3.5"/></svg>,
 <svg viewBox="0 0 20 20" key="1"><circle cx="5" cy="5" r="2.2"/><circle cx="15" cy="5" r="2.2"/><circle cx="10" cy="15" r="2.2"/><path d="M6.6 6.4 8.6 13M13.4 6.4l-2 6.6M7.2 5h5.6"/></svg>,
 <svg viewBox="0 0 20 20" key="2"><path d="M11 2 4 11h5l-1 7 8-10h-5z"/></svg>,
 <svg viewBox="0 0 20 20" key="3"><circle cx="10" cy="10" r="7.5"/><path d="m13.5 6.5-2 5-5 2 2-5z"/></svg>,
];
export default function RoadmapCanvas({plan,graph,first,course,due,en,onLearn,onGraph,onStart}) {
 const viewport=useRef(null),drag=useRef(null);
 const [size,setSize]=useState({width:1000,height:600}),[zoom,setZoom]=useState(1),[expanded,setExpanded]=useState(null),[scroll,setScroll]=useState({x:0,y:0});
 const mobile=size.width<600;
 useEffect(()=>{const el=viewport.current;const observer=new ResizeObserver(()=>setSize({width:el.clientWidth,height:el.clientHeight}));observer.observe(el);return()=>observer.disconnect();},[]);
 const stages=en?[['Foundations','Build core knowledge'],['Mechanisms','Understand how it works'],['Applications','See it in action'],['Frontiers','Explore what’s next']]
                :[['Fundamenten','Bouw kernkennis op'],['Mechanismen','Begrijp hoe het werkt'],['Toepassingen','Zie het in actie'],['Verdieping','Verken wat komt']];
 const nodes=new Map(graph.nodes.map(n=>[n.id,n]));
 const layout=useMemo(()=>roadmapLayout(plan,graph,mobile,size.width),[plan,graph,mobile,size.width]);
 // Route: the course's groups when one is active, else the chain from the next group back to its root.
 const courseIds=useMemo(()=>new Set(course?.steps?.map(s=>s.concept_id)||[]),[course]);
 const doneIds=useMemo(()=>new Set(course?.steps?.filter(s=>s.done).map(s=>s.concept_id)||[]),[course]);
 const route=useMemo(()=>course?new Set(layout.groups.filter(g=>g.ids.some(id=>courseIds.has(id))).map(g=>g.key)):routeKeys(layout,first),[layout,first,course,courseIds]);
 const routeGroups=layout.groups.filter(g=>route.has(g.key));
 const dueIds=useMemo(()=>new Set((due||[]).map(d=>d.concept_id)),[due]);
 const selected=layout.groups.find(g=>g.key===expanded);
 function changeZoom(next){setZoom(Math.max(.3,Math.min(1.6,next)));}
 // Fit the whole map when it is larger than the viewport, but never smaller than half size: readable first.
 const fitZoom=()=>mobile?1:Math.max(.5,Math.min(1,size.width/layout.width,size.height/layout.height));
 const fitted=useRef(false);
 useEffect(()=>{const el=viewport.current;if(fitted.current||mobile||!el||!el.clientWidth||size.width!==el.clientWidth)return;fitted.current=true;setZoom(fitZoom());},[layout,size,mobile]);
 useEffect(()=>{const el=viewport.current;setScroll({x:el.scrollLeft,y:el.scrollTop});},[zoom,expanded]);
 // Op de telefoon scrolt de kaart niet zelf maar loopt hij mee met de pagina (geen scroll in
 // scroll). Dan moet "naar een groep gaan" de PAGINA scrollen in plaats van het kaartvlak.
 const inFlow=()=>viewport.current.scrollHeight<=viewport.current.clientHeight+4;
 function overview(){setExpanded(null);setZoom(fitZoom());if(inFlow())viewport.current.scrollIntoView({block:'start',behavior:'smooth'});else viewport.current.scrollTo(0,0);setScroll({x:0,y:0});}
 function nextStep(){const g=layout.groups.find(g=>g.ids.includes(first?.id));if(!g)return;setExpanded(g.key);setZoom(1);requestAnimationFrame(()=>{if(inFlow())viewport.current.querySelector(`[data-group="${g.key}"]`)?.scrollIntoView({block:'center',behavior:'smooth'});else viewport.current.scrollTo({left:Math.max(0,g.x-size.width/2+g.width/2),top:Math.max(0,g.y-24),behavior:'smooth'});});}
 // Slepen om te verschuiven is voor de muis. Op een touchscherm pant de browser zelf; pointer
 // capture op een vinger zou dat alleen maar in de weg zitten.
 function down(e){if(e.pointerType!=='mouse'||e.button!==0||e.target.closest('button,a,input,summary,.map-topic-list'))return;drag.current={x:e.clientX,y:e.clientY,left:viewport.current.scrollLeft,top:viewport.current.scrollTop};e.currentTarget.setPointerCapture(e.pointerId);}
 function move(e){if(!drag.current)return;viewport.current.scrollTo(drag.current.left+drag.current.x-e.clientX,drag.current.top+drag.current.y-e.clientY);}
 // Trackpad pinch emits a control-wheel event. Ordinary wheel retains native scrolling.
 useEffect(()=>{const el=viewport.current;const wheel=e=>{if(e.ctrlKey){e.preventDefault();changeZoom(zoom*Math.exp(-e.deltaY*.01));}};el.addEventListener('wheel',wheel,{passive:false});return()=>el.removeEventListener('wheel',wheel);},[zoom]);
 // Smooth S-curves: out of the node's right edge, into the child's left edge, bending at the midpoint.
 function edgePath({a,b}){if(mobile){const x1=a.x+a.width/2,y1=a.y+a.height,x2=b.x+b.width/2,y2=b.y,my=(y1+y2)/2;return `M${x1},${y1} C${x1},${my} ${x2},${my} ${x2},${y2}`;}const x1=a.x+a.width,y1=a.y+a.height/2,x2=b.x,y2=b.y+b.height/2,mx=(x1+x2)/2;return `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;}
 const onRoute=e=>route.has(e.b.key)&&route.has(e.a.key);
 return <div className="curriculum-map">
 <div className="map-tools"><button className="btn ghost" onClick={overview}>{en?'Overview':'Overzicht'}</button><button className="btn" disabled={!first} onClick={nextStep}>{en?'My next step':'Mijn volgende stap'}</button></div>
 {!mobile&&<div className="map-stage-window" style={{height:70*zoom}}><div className="map-stage-headings" style={{width:layout.width,gridTemplateColumns:`repeat(4,${STAGE_WIDTH}px)`,paddingLeft:STAGE_LEFT,transform:`translateX(${-scroll.x}px) scale(${zoom})`,transformOrigin:"0 0"}}>{stages.map(([t,sub])=><div key={t}><strong>{t}</strong><span>{sub}</span></div>)}</div></div>}
 <div ref={viewport} className="map-viewport" aria-label={en?'Learning roadmap':'Leerroute'} tabIndex={0} onScroll={e=>setScroll({x:e.currentTarget.scrollLeft,y:e.currentTarget.scrollTop})} onPointerDown={down} onPointerMove={move} onPointerUp={()=>drag.current=null} onPointerCancel={()=>drag.current=null}>
 <div style={{width:layout.width*zoom,height:layout.height*zoom,position:'relative'}}><div className="map-world" style={{width:layout.width,height:layout.height,transform:`scale(${zoom})`}}>
 <svg className="map-connections" width={layout.width} height={layout.height} aria-hidden="true">
  {!mobile&&[0,1,2,3].map(i=><line key={i} className="map-stage-line" x1={STAGE_LEFT+i*STAGE_WIDTH-24} x2={STAGE_LEFT+i*STAGE_WIDTH-24} y1={16} y2={layout.height-16}/>)}
  {layout.edges.filter(e=>!onRoute(e)).map((e,i)=><path key={'b'+i} className={'map-edge'+(e.suggested?' suggested':'')} d={edgePath(e)}/>)}
  {layout.edges.filter(onRoute).map((e,i)=><path key={'r'+i} className="map-edge route" d={edgePath(e)}/>)}
 </svg>
 {layout.groups.map(g=>{const isNext=g.ids.includes(first?.id),understood=g.ids.filter(cid=>nodes.get(cid)?.status==='learned').length,inCourse=g.ids.filter(cid=>courseIds.has(cid)).length,done=g.ids.filter(cid=>doneIds.has(cid)).length,dueCount=g.ids.filter(cid=>dueIds.has(cid)).length;return <article key={g.key} data-group={g.key} className={'map-node'+(isNext?' next-node':'')+(route.has(g.key)?' on-route':'')+(expanded===g.key?' open':'')} style={{left:g.x,top:g.y,width:g.width,height:g.height}}>
 {mobile&&<span className="map-mobile-stage">{g.stage+1} · {stages[g.stage][0]}</span>}
 <button className="map-node-btn" aria-expanded={expanded===g.key} onClick={()=>setExpanded(expanded===g.key?null:g.key)}><span className="map-node-icon" aria-hidden="true">{ICONS[g.stage]||ICONS[3]}</span><span className="map-node-text"><strong>{g.title}</strong><span>{inCourse?`${done}/${inCourse} ${en?'done':'klaar'}`:`${g.ids.length} ${en?'topics':'onderwerpen'}`}{understood?` · ${understood} ${en?'understood':'begrepen'}`:''}</span></span></button>
 {dueCount>0&&<i className="map-node-due" title={en?`${dueCount} due for a quick check`:`${dueCount} te herhalen`}>{dueCount}</i>}
 {isNext&&<b className="map-node-badge">{course?(en?'Continue here':'Ga hier verder'):(en?'Start here':'Begin hier')}</b>}
 </article>;})}
 </div></div>
 </div>

 {selected&&<aside className="map-detail" aria-label={en?'Topic group details':'Onderwerpgroep'}><button className="map-detail-close" aria-label={en?'Close group':'Sluit groep'} onClick={()=>setExpanded(null)}>×</button><span className="eyebrow">{stages[selected.stage]?.[0]}</span><h2>{selected.title}</h2><div className="map-topic-list"><p>{selected.reason}</p>{selected.ids.map(cid=>{const n=nodes.get(cid);return n&&<div className="map-topic" key={cid}><button onClick={()=>onLearn(n.name)}><i className={'status-dot '+(n.status||'suggested')}/>{n.name}{cid===first?.id?' →':''}{dueIds.has(cid)&&<em className="due-tag">{en?'due':'herhalen'}</em>}</button><button aria-label={(en?'View in graph: ':'Bekijk in kaart: ')+n.name} onClick={()=>onGraph(n.name)}>↗</button></div>;})}</div>{first&&selected.ids.includes(first.id)&&<button className="btn primary map-detail-start" onClick={()=>onStart(routeGroups)}>{course?(en?'Continue course':'Cursus vervolgen'):(en?'Start learning':'Begin met leren')} →</button>}
 {first&&selected.ids.includes(first.id)&&!course&&<p className="hint map-detail-hint">{en?'Makes a course from the green route and opens the first topic.':'Maakt een cursus van de groene route en opent het eerste onderwerp.'}</p>}</aside>}
 {!mobile&&(zoom!==1||scroll.x>10||scroll.y>10)&&<svg className="map-minimap" viewBox={`0 0 ${layout.width} ${layout.height}`} aria-label={en?'Map position overview':'Kaartpositie'}>{layout.groups.map(g=><rect key={g.key} x={g.x} y={g.y} width={g.width} height={g.height} rx="14" fill={route.has(g.key)?'#5FCE9E':'#365b70'}/>)}<rect x={scroll.x/zoom} y={scroll.y/zoom} width={size.width/zoom} height={size.height/zoom} fill="#5FCE9E18" stroke="#5FCE9E" strokeWidth="8"/></svg>}
 <div className="map-footer">
  <div className="map-zoom" role="group" aria-label={en?'Zoom':'Zoom'}><button aria-label={en?'Zoom out':'Uitzoomen'} onClick={()=>changeZoom(zoom-.15)}>−</button><span>{Math.round(zoom*100)}%</span><button aria-label={en?'Zoom in':'Inzoomen'} onClick={()=>changeZoom(zoom+.15)}>+</button></div>
  <div className="map-legend-line"><span><i className="route"/>{course?(en?'Your course':'Jouw cursus'):(en?'Suggested route':'Voorgestelde route')}</span><span><i className="branch"/>{en?'Explore any branch':'Verken elke tak'}</span><span><i className="branch dotted"/>{en?'Proposed order, no saved prerequisite':'Voorgestelde volgorde, geen opgeslagen voorkennis'}</span></div>
 </div>
 </div>;
}
