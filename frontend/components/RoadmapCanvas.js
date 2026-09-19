"use client";
import {useEffect,useMemo,useRef,useState} from 'react';
import {roadmapLayout} from '../lib/roadmap-layout.mjs';
export default function RoadmapCanvas({plan,graph,first,en,onLearn,onGraph}) {
 const viewport=useRef(null),drag=useRef(null);
 const [size,setSize]=useState({width:1000,height:600}),[zoom,setZoom]=useState(1),[expanded,setExpanded]=useState(null),[scroll,setScroll]=useState({x:0,y:0});
 const mobile=size.width<600;
 useEffect(()=>{const el=viewport.current;const observer=new ResizeObserver(()=>setSize({width:el.clientWidth,height:el.clientHeight}));observer.observe(el);return()=>observer.disconnect();},[]);
 const titles=en?['Foundations','Mechanisms','Applications','Frontiers']:['Fundamenten','Mechanismen','Toepassingen','Verdieping'];
 const nodes=new Map(graph.nodes.map(n=>[n.id,n]));
 const layout=useMemo(()=>roadmapLayout(plan,graph,mobile,size.width),[plan,graph,mobile,size.width]);
 const selected=layout.groups.find(g=>g.key===expanded);
 function changeZoom(next){setZoom(Math.max(.3,Math.min(1.6,next)));}
 useEffect(()=>{const el=viewport.current;setScroll({x:el.scrollLeft,y:el.scrollTop});},[zoom,expanded]);
 function overview(){setExpanded(null);setZoom(mobile?1:Math.max(.3,Math.min(1,size.width/layout.width,size.height/layout.height)));viewport.current.scrollTo(0,0);setScroll({x:0,y:0});}
 function nextStep(){const g=layout.groups.find(g=>g.ids.includes(first?.id));if(!g)return;setExpanded(g.key);setZoom(1);requestAnimationFrame(()=>viewport.current.scrollTo({left:Math.max(0,g.x-size.width/2+g.width/2),top:Math.max(0,g.y-24),behavior:'smooth'}));}
 function down(e){if(e.button!==0||e.target.closest('button,a,input,summary,.map-topic-list'))return;drag.current={x:e.clientX,y:e.clientY,left:viewport.current.scrollLeft,top:viewport.current.scrollTop};e.currentTarget.setPointerCapture(e.pointerId);}
 function move(e){if(!drag.current)return;viewport.current.scrollTo(drag.current.left+drag.current.x-e.clientX,drag.current.top+drag.current.y-e.clientY);}
 // Trackpad pinch emits a control-wheel event. Ordinary wheel retains native scrolling.
 useEffect(()=>{const el=viewport.current;const wheel=e=>{if(e.ctrlKey){e.preventDefault();changeZoom(zoom*Math.exp(-e.deltaY*.01));}};el.addEventListener('wheel',wheel,{passive:false});return()=>el.removeEventListener('wheel',wheel);},[zoom]);
 return <div className="curriculum-map">
 <div className="map-tools"><span>{en?'Shared foundations → specialist branches':'Gedeelde fundamenten → specialistische takken'}</span><div><button className="btn" onClick={overview}>{en?'Overview':'Overzicht'}</button><button className="btn" disabled={!first} onClick={nextStep}>{en?'My next step':'Mijn volgende stap'}</button><button className="btn" aria-label={en?'Zoom out':'Uitzoomen'} onClick={()=>changeZoom(zoom-.15)}>−</button><span>{Math.round(zoom*100)}%</span><button className="btn" aria-label={en?'Zoom in':'Inzoomen'} onClick={()=>changeZoom(zoom+.15)}>+</button></div></div>
 {!mobile&&<div className="map-stage-window"><div className="map-stage-headings" style={{width:layout.width*zoom,gridTemplateColumns:`repeat(4,${460*zoom}px)`,paddingLeft:64*zoom,transform:`translateX(${-scroll.x}px)`}}>{titles.map((t,i)=><strong key={t}><span>{i+1}</span>{t}</strong>)}</div></div>}
 <div ref={viewport} className="map-viewport" aria-label={en?'Learning roadmap':'Leerroute'} tabIndex={0} onScroll={e=>setScroll({x:e.currentTarget.scrollLeft,y:e.currentTarget.scrollTop})} onPointerDown={down} onPointerMove={move} onPointerUp={()=>drag.current=null} onPointerCancel={()=>drag.current=null}>
 <div style={{width:layout.width*zoom,height:layout.height*zoom,position:'relative'}}><div className="map-world" style={{width:layout.width,height:layout.height,transform:`scale(${zoom})`}}>
 <svg className="map-connections" width={layout.width} height={layout.height} aria-hidden="true"><defs><marker id="curriculum-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#5d9ab1"/></marker></defs>{layout.edges.map(({a,b,suggested},i)=>{const x1=mobile?a.x+a.width/2:a.x+a.width,y1=mobile?a.y+a.height:a.y+56,x2=mobile?b.x+b.width/2:b.x,y2=mobile?b.y:b.y+56;return <path key={i} d={mobile?`M${x1},${y1} C${x1},${(y1+y2)/2} ${x2},${(y1+y2)/2} ${x2},${y2}`:`M${x1},${y1} C${x1+100},${y1} ${x2-100},${y2} ${x2},${y2}`} fill="none" stroke={suggested?"#56788d":"#65cbb0"} strokeDasharray={suggested?"6 7":undefined} strokeWidth="2" opacity=".8" markerEnd="url(#curriculum-arrow)"/>;})}</svg>
 {layout.groups.map(g=><article key={g.key} className={'map-group'+(g.ids.includes(first?.id)?' next-group':'')} style={{left:g.x,top:g.y,width:g.width,height:g.height}}>
 {mobile&&<span className="map-mobile-stage">{g.stage+1} · {titles[g.stage]}</span>}
 <button className="map-group-toggle" aria-expanded={expanded===g.key} onClick={()=>setExpanded(expanded===g.key?null:g.key)}><strong>{g.title}</strong><span>{g.ids.length} {en?'topics':'onderwerpen'} · {g.ids.filter(cid=>nodes.get(cid)?.status==='learned').length} {en?'understood':'begrepen'}</span><b>{g.ids.includes(first?.id)?(en?'Start here':'Begin hier'):(expanded===g.key?'−':'+')}</b></button>

 </article>)}
 </div></div>
 </div>

 {selected&&<aside className="map-detail" aria-label={en?'Topic group details':'Onderwerpgroep'}><button className="map-detail-close" aria-label={en?'Close group':'Sluit groep'} onClick={()=>setExpanded(null)}>×</button><h2>{selected.title}</h2><div className="map-topic-list"><p>{selected.reason}</p>{selected.ids.map(cid=>{const n=nodes.get(cid);return n&&<div className="map-topic" key={cid}><button onClick={()=>onLearn(n.name)}><i className={'status-dot '+(n.status||'suggested')}/>{n.name}{cid===first?.id?' →':''}</button><button aria-label={(en?'View in graph: ':'Bekijk in kaart: ')+n.name} onClick={()=>onGraph(n.name)}>↗</button></div>;})}</div></aside>}
 {!mobile&&(zoom!==1||scroll.x>10||scroll.y>10)&&<svg className="map-minimap" viewBox={`0 0 ${layout.width} ${layout.height}`} aria-label={en?'Map position overview':'Kaartpositie'}>{layout.groups.map(g=><rect key={g.key} x={g.x} y={g.y} width={g.width} height={g.height} fill="#365b70"/>)}<rect x={scroll.x/zoom} y={scroll.y/zoom} width={size.width/zoom} height={size.height/zoom} fill="#65cbb022" stroke="#65cbb0" strokeWidth="8"/></svg>}
 <div className="map-caption">{en?'Solid: saved prerequisite · Dashed: suggested progression. Drag to explore right →':'Doorgetrokken: voorkennis · Gestippeld: voorgestelde route. Sleep naar rechts →'}</div>
 </div>;
}
