"use client";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { atlasLayout, idOf, learningRoute, clusterEntry, nodeOffset, zoomDepth } from "../lib/atlas.mjs";
import { useT } from "../lib/i18n";

export const COL = { learning: "#54A9FF", learned: "#5FCE9E", suggested: "#91A1B5", queued: "#E5A64A" };
const clamp = k => Math.max(.08, Math.min(12, k));
const edgeKey = l => `${idOf(l.source)}:${l.type}:${idOf(l.target)}`;
const activateKey = (e, action) => { if (["Enter", " "].includes(e.key)) { e.preventDefault(); e.stopPropagation(); action(); } };
const labelLines = name => {
  if (name.length <= 25) return [name];
  const words=name.split(" "), lines=[""];
  for (const word of words) { const i=lines.length-1; if (lines[i].length+word.length>25 && lines[i]) lines.push(word); else lines[i]+=(lines[i]?" ":"")+word; }
  return lines.slice(0,3).map((line,i)=>i===2 && lines.length>3?line+"…":line);
};

export default function GraphView({ data, selectedName, highlightQuery = "", hoverName, onSelect, ambientMotion = true, reducedMotion = false, hidden = false, onStartLearning, starting = false, focusRequest, onGroupsChange, onScopeChange }) {
  const { t } = useT();
  const wrap=useRef(null), svg=useRef(null), drag=useRef(null), pointer=useRef(null), fitted=useRef(false), offsets=useRef(new Map());
  // Aanraken: touches = actieve vingers, pinch = een lopend twee-vingergebaar.
  const touches=useRef(new Map()), pinch=useRef(null), hintTimer=useRef(null);
  const [gestureHint,setGestureHint]=useState(false);
  const [size,setSize]=useState({w:1000,h:680}), [camera,setCamera]=useState({x:-500,y:-340,k:1});
  const [scope,setScope]=useState(""), [edge,setEdge]=useState(null), [hovered,setHovered]=useState(null), [,setFrame]=useState(0);
  const portrait=size.w<size.h;
  const layout=useMemo(()=>atlasLayout(data,portrait),[data,portrait]);
  useEffect(()=>{fitted.current=false;},[portrait]);
  const focusedGroup=layout.groups.find(g=>g.key===scope);
  const entry=useMemo(()=>clusterEntry(data,focusedGroup),[data,focusedGroup]);
  const selected=layout.nodes.find(n=>n.name===selectedName);
  const route=useMemo(()=>learningRoute(data,selected?.id),[data,selected?.id]);
  const routeEdges=new Set(route.edges.map(edgeKey));
  const query=highlightQuery.trim().toLowerCase();
  const matches=n=>(!scope||n.group===scope)&&(!query||n.name.toLowerCase().includes(query));
  const fittedScale=clamp(Math.min(1.25,(size.w-100)/layout.width,(size.h-160)/layout.height));
  const depth=zoomDepth(camera.k,fittedScale);
  const detail=depth===0?"overview":depth===1?"concepts":"relations";
  const motion=ambientMotion&&!reducedMotion&&!hidden;
  const [visible,setVisible]=useState(true);
  useEffect(()=>{const update=()=>setVisible(!document.hidden);document.addEventListener("visibilitychange",update);return()=>document.removeEventListener("visibilitychange",update);},[]);
  useEffect(()=>{
    const observer=new ResizeObserver(([entry])=>{if(entry.contentRect.width&&entry.contentRect.height)setSize({w:entry.contentRect.width,h:entry.contentRect.height});});
    observer.observe(wrap.current);return()=>observer.disconnect();
  },[]);
  const fit=useCallback((group)=>{
    const box=group||layout;
    const k=group?clamp(Math.min(6,(size.w-140)/box.width,(size.h-180)/box.height)):fittedScale;
    setCamera({k,x:box.x+box.width/2-size.w/(2*k),y:box.y+box.height/2-size.h/(2*k)});
  },[layout,size,fittedScale]);
  useEffect(()=>{if(!layout.nodes.length){fitted.current=false;return;}if(!fitted.current&&size.w>100){fit();fitted.current=true;}},[layout,fit,size.w]);
  useEffect(()=>{if(scope&&!layout.groups.some(g=>g.key===scope))setScope("");},[scope,layout]);
  useEffect(()=>{
    if(!motion||!visible){pointer.current=null;return;}
    let request,last=0;
    const animate=now=>{
      if(now-last>32){
        layout.nodes.forEach((n,i)=>{
          const target=nodeOffset(i,now/1000,pointer.current,n,camera.k), previous=offsets.current.get(n.id)||{x:0,y:0};
          offsets.current.set(n.id,{x:previous.x+(target.x-previous.x)*.16,y:previous.y+(target.y-previous.y)*.16});
        });
        last=now;setFrame(now);
      }
      request=requestAnimationFrame(animate);
    };
    request=requestAnimationFrame(animate);return()=>cancelAnimationFrame(request);
  },[motion,visible,layout,camera.k]);
  // Freeze in place when motion is disabled, including the OS accessibility setting.
  const nodes=new Map(layout.nodes.map(n=>{const d=offsets.current.get(n.id)||{x:0,y:0};return[n.id,{...n,x:n.x+d.x,y:n.y+d.y}];}));
  const zoom=(factor,point)=>setCamera(c=>{const k=clamp(c.k*factor),p=point||{x:size.w/2,y:size.h/2};return{k,x:c.x+p.x/c.k-p.x/k,y:c.y+p.y/c.k-p.y/k};});
  useEffect(()=>{
    const el=svg.current;
    const wheel=e=>{e.preventDefault();const r=el.getBoundingClientRect();pointer.current=null;zoom(Math.exp(-e.deltaY*.0015),{x:e.clientX-r.left,y:e.clientY-r.top});};
    el.addEventListener("wheel",wheel,{passive:false});return()=>el.removeEventListener("wheel",wheel);
  },[size]);
  const focusGroup=g=>{setScope(g.key);setEdge(null);const k=clamp(Math.max(fittedScale*1.7,Math.min(fittedScale*2.4,(size.w-120)/g.width,(size.h-160)/g.height)));setCamera({k,x:g.cx-size.w/(2*k),y:g.cy-size.h/(2*k)});};
  const changeScope=key=>{const g=layout.groups.find(g=>g.key===key);if(g)focusGroup(g);else{setScope("");setEdge(null);fit();}};
  useEffect(()=>{onGroupsChange?.(layout.groups.filter(g=>g.members.length>1).map(g=>({key:g.key,name:g.name,count:g.members.length})));},[layout,onGroupsChange]);
  useEffect(()=>{onScopeChange?.(scope);},[scope,onScopeChange]);
  useEffect(()=>{if(focusRequest)changeScope(focusRequest.key);},[focusRequest]);
  const clearScope=()=>{setScope("");setEdge(null);pointer.current=null;fit();};
  const selectNode=n=>{if(scope&&n.group!==scope)clearScope();onSelect(n.name);};
  const finishPan=e=>{
    const d=drag.current;drag.current=null;
    if(!d||d.moved||!scope)return;
    const rect=svg.current.getBoundingClientRect(),g=layout.groups.find(g=>g.key===scope);
    const x=d.camera.x+(e.clientX-rect.left)/d.camera.k,y=d.camera.y+(e.clientY-rect.top)/d.camera.k;
    if(g&&Math.hypot((x-g.cx)/g.rx,(y-g.cy)/g.ry)>1)clearScope();
  };
  // Telefoon (< 750px): de pagina scrolt, dus één vinger is voor de pagina en de kaart volgt
  // pas bij twee vingers (verschuiven + knijpzoomen). Dat is het patroon van ingesloten kaarten;
  // anders zit je met één veeg vast in de kaart en kom je de pagina niet meer door.
  const pageScrolls=()=>typeof window!=="undefined"&&window.matchMedia("(max-width: 749.98px)").matches;
  const showGestureHint=()=>{if(hintTimer.current)return;setGestureHint(true);hintTimer.current=setTimeout(()=>{setGestureHint(false);hintTimer.current=null;},1800);};
  const startPinch=()=>{
    const [a,b]=[...touches.current.values()],r=svg.current.getBoundingClientRect();
    drag.current=null;pointer.current=null;
    pinch.current={dist:Math.hypot(a.x-b.x,a.y-b.y)||1,mid:{x:(a.x+b.x)/2-r.left,y:(a.y+b.y)/2-r.top},camera};
    for(const id of touches.current.keys()){try{svg.current.setPointerCapture(id);}catch{}}
  };
  const movePinch=()=>{
    const p=pinch.current,[a,b]=[...touches.current.values()],r=svg.current.getBoundingClientRect();
    const mid={x:(a.x+b.x)/2-r.left,y:(a.y+b.y)/2-r.top},k=clamp(p.camera.k*Math.hypot(a.x-b.x,a.y-b.y)/p.dist);
    // Het wereldpunt dat onder het beginmidden lag, blijft onder de vingers: zoom en schuif tegelijk.
    const wx=p.camera.x+p.mid.x/p.camera.k,wy=p.camera.y+p.mid.y/p.camera.k;
    setCamera({k,x:wx-mid.x/k,y:wy-mid.y/k});
  };
  const endTouch=e=>{if(e.pointerType!=="touch")return;touches.current.delete(e.pointerId);if(touches.current.size<2)pinch.current=null;};
  useEffect(()=>{
    const el=svg.current;
    // Twee vingers op de kaart: de browser mag dan niet de pagina scrollen of zoomen.
    const move=e=>{if(e.touches.length>1&&e.cancelable)e.preventDefault();};
    const gesture=e=>e.preventDefault(); // iOS Safari: geen pagina-zoom bij knijpen op de kaart
    el.addEventListener("touchmove",move,{passive:false});el.addEventListener("gesturestart",gesture);
    return()=>{el.removeEventListener("touchmove",move);el.removeEventListener("gesturestart",gesture);clearTimeout(hintTimer.current);};
  },[]);
  const emphasized=n=>n.name===selectedName||n.id===hovered||n.name===hoverName||(query&&n.name.toLowerCase().includes(query));
  const shown=()=>true; // Keep the network visible; zoom controls names, not the existence of nodes.

  // Label only the current tier and ancestors. The next tier remains visible as
  // dots. Collision placement uses settled coordinates so text doesn't jitter.
  const labels=useMemo(()=>{
    const candidates=[];
    layout.groups.forEach(g=>{
      if(g.members.length>1)candidates.push({id:"group:"+g.key,group:g,name:g.name,x:g.cx,y:g.cy-g.ry+8,priority:1});
    });
    layout.nodes.forEach(n=>{
      const special=n.name===selectedName||n.id===hovered||n.name===hoverName||(query&&n.name.toLowerCase().includes(query));
      const g=layout.groups.find(g=>g.key===n.group);
      if(special||(n.depth<=depth&&(n.depth>0||g.members.length===1)))candidates.push({id:n.id,node:n,name:n.name,x:n.x,y:n.y+18/camera.k,priority:special?0:2+n.depth});
    });
    const placed=[],occupied=[];
    candidates.sort((a,b)=>a.priority-b.priority||a.name.localeCompare(b.name)).forEach(c=>{
      const lines=labelLines(c.name),w=Math.max(...lines.map(l=>l.length))*7.3+16,h=lines.length*17+8;
      const sx=(c.x-camera.x)*camera.k,sy=(c.y-camera.y)*camera.k;
      for(const delta of [0,-h-35,22]){
        const box={x:sx-w/2,y:sy+delta,w,h};
        if(box.x<3||box.x+w>size.w-3||box.y<54||box.y+h>size.h-76)continue;
        if(c.priority!==0&&occupied.some(b=>box.x<b.x+b.w+10&&box.x+w+10>b.x&&box.y<b.y+b.h+8&&box.y+h+8>b.y))continue;
        occupied.push(box);placed.push({...c,lines,screenY:sy+delta,w,h});break;
      }
    });return placed;
  },[layout,depth,camera,size,selectedName,hovered,hoverName,query]);

  return <div ref={wrap} className={"graph-layer atlas-layer living-graph"+(motion?" ambient-on":"")} data-orientation={portrait?"portrait":"landscape"} data-detail={detail} data-depth={depth} data-motion-enabled={motion&&visible}>

    {entry&&onStartLearning&&<section className="cluster-start" aria-label={t("cluster.startLabel")}>
      <span className="eyebrow">{focusedGroup.name}</span>
      <h2>{t("cluster.beginWith",{name:entry.node.name})}</h2>
      <p>{entry.route.cycle?t("explore.cycle"):entry.review?t("cluster.reviewHint"):entry.node.id!==entry.goal.id?t("cluster.prerequisiteHint",{name:entry.goal.name}):entry.goal.id!==focusedGroup.hubId?t("cluster.nextHint"):t("cluster.hubHint")}</p>
      <button className="btn primary" disabled={starting} onClick={()=>onStartLearning(entry.node.name)}>{starting?t("panel.thinking"):entry.review?t("cluster.review"):t("cluster.start")} →</button>
    </section>}
    {gestureHint&&<div className="gesture-hint" role="status">{t("graph.twoFingers")}</div>}
    <svg ref={svg} width="100%" height="100%" viewBox={`${camera.x} ${camera.y} ${size.w/camera.k} ${size.h/camera.k}`} aria-label={t("explore.map")} tabIndex={0}
      onBlur={e=>{if(e.target===svg.current)delete svg.current.dataset.pointerFocus;}}
      onKeyDown={e=>{delete svg.current.dataset.pointerFocus;if(e.key==="Escape"&&scope){e.preventDefault();clearScope();return;}if(e.target!==svg.current)return;const shifts={ArrowLeft:[-60,0],ArrowRight:[60,0],ArrowUp:[0,-60],ArrowDown:[0,60]};if(shifts[e.key]){e.preventDefault();const[x,y]=shifts[e.key];setCamera(c=>({...c,x:c.x+x/c.k,y:c.y+y/c.k}));}if(e.key==="+"||e.key==="="){e.preventDefault();zoom(1.4);}if(e.key==="-"){e.preventDefault();zoom(1/1.4);}}}
      onPointerDown={e=>{svg.current.dataset.pointerFocus="true";if(e.pointerType==="touch"){touches.current.set(e.pointerId,{x:e.clientX,y:e.clientY});if(touches.current.size===2){startPinch();return;}}if(e.target.closest("[role=button]"))return;pointer.current=null;const passive=e.pointerType==="touch"&&pageScrolls();drag.current={x:e.clientX,y:e.clientY,camera,moved:false,passive};if(!passive)svg.current.setPointerCapture(e.pointerId);}}
      onPointerMove={e=>{if(e.pointerType==="touch"&&touches.current.has(e.pointerId)){touches.current.set(e.pointerId,{x:e.clientX,y:e.clientY});if(pinch.current&&touches.current.size>=2){movePinch();return;}}const r=svg.current.getBoundingClientRect();const d=drag.current;if(d){if(Math.hypot(e.clientX-d.x,e.clientY-d.y)>5)d.moved=true;if(d.passive){if(Math.abs(e.clientX-d.x)>24&&Math.abs(e.clientX-d.x)>Math.abs(e.clientY-d.y))showGestureHint();return;}setCamera({...d.camera,x:d.camera.x-(e.clientX-d.x)/d.camera.k,y:d.camera.y-(e.clientY-d.y)/d.camera.k});}else if(e.pointerType!=="touch"){pointer.current={x:camera.x+(e.clientX-r.left)/camera.k,y:camera.y+(e.clientY-r.top)/camera.k};}}}
      onPointerLeave={()=>{pointer.current=null;setHovered(null);}} onPointerUp={e=>{endTouch(e);finishPan(e);}} onPointerCancel={e=>{endTouch(e);drag.current=null;pointer.current=null;}}>
      <defs><marker id="atlas-route-arrow" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M0 0L10 5L0 10Z" fill="#54A9FF"/></marker></defs>
      {layout.groups.filter(g=>g.members.length>1).map(g=><ellipse key={g.key} className="cluster-outline" cx={g.cx} cy={g.cy} rx={g.rx} ry={g.ry} fill="#182b40" fillOpacity={scope===g.key ? .16 : .045} stroke="#6085A8" strokeOpacity={scope&&scope!==g.key ? .09 : .3} strokeWidth={1/camera.k} pointerEvents="none"/>)}
      {data.links.map((l,i)=>{
        const a=nodes.get(idOf(l.source)),b=nodes.get(idOf(l.target));if(!a||!b||!shown(a)||!shown(b))return null;
        const hot=routeEdges.has(edgeKey(l)),adjacent=a.id===hovered||b.id===hovered||a.id===selected?.id||b.id===selected?.id;
        const faded=(scope&&(a.group!==scope||b.group!==scope))||(query&&!matches(a)&&!matches(b));
        const dx=b.x-a.x,dy=b.y-a.y,len=Math.hypot(dx,dy)||1;
        return <g key={edgeKey(l)+i} opacity={faded ? .12 : 1} className="graph-connection">
          <line x1={a.x} y1={a.y} x2={b.x-dx/len*7/camera.k} y2={b.y-dy/len*7/camera.k} stroke={hot||adjacent?"#68B5FF":"#668AAA"} strokeOpacity={hot ? .9 : adjacent ? .7 : .33} strokeWidth={(hot?1.8:adjacent?1.4:.85)/camera.k} strokeDasharray={l.type==="RELATED_TO"?`${3/camera.k} ${5/camera.k}`:l.type==="PART_OF"?`${7/camera.k} ${4/camera.k}`:undefined} markerEnd={hot?"url(#atlas-route-arrow)":undefined}/>
          {depth>1&&adjacent&&<g role="button" tabIndex={0} aria-label={`${a.name}: ${t("relation."+l.type)}: ${b.name}`} onClick={()=>setEdge({...l,a:a.name,b:b.name})} onKeyDown={e=>activateKey(e,()=>setEdge({...l,a:a.name,b:b.name}))}><circle cx={(a.x+b.x)/2} cy={(a.y+b.y)/2} r={8/camera.k} fill="#162a3e" stroke="#688aa8" strokeWidth={1/camera.k}/><text x={(a.x+b.x)/2} y={(a.y+b.y)/2+4/camera.k} textAnchor="middle" fontSize={12/camera.k} fill="#C2D8EB">i</text></g>}
        </g>;
      })}
      {[...nodes.values()].filter(shown).map(n=>{
        const active=n.name===selectedName,hot=emphasized(n),r=active?7:n.depth===0?6:n.depth<=depth?4.5:n.depth===depth+1?3:2.4;
        return <g key={n.id} role="button" tabIndex={0} data-node-id={n.id} data-tier={n.depth} className="atlas-node" aria-label={`${n.name} — ${t("status."+n.status)}`} opacity={matches(n)?1:.16} onClick={e=>{e.stopPropagation();selectNode(n);}} onKeyDown={e=>activateKey(e,()=>selectNode(n))} onFocus={()=>setHovered(n.id)} onBlur={()=>setHovered(null)} onPointerEnter={()=>setHovered(n.id)} onPointerLeave={()=>setHovered(null)}>
          <title>{n.name} · {t("status."+n.status)}</title>
          <circle className="node-halo" cx={n.x} cy={n.y} r={(r+9)/camera.k} fill={COL[n.status]||COL.suggested} opacity={hot ? .2 : .07}/>
          <circle className="node-core" cx={n.x} cy={n.y} r={r/camera.k} fill={n.status==="suggested"?"#182431":COL[n.status]||COL.suggested} stroke={COL[n.status]||COL.suggested} strokeWidth={(hot?1.8:1)/camera.k} strokeDasharray={n.status==="suggested"?`${2/camera.k} ${2/camera.k}`:undefined}/>
          {active&&<circle cx={n.x} cy={n.y} r={(r+4)/camera.k} fill="none" stroke="#78BDFF" strokeWidth={1/camera.k}/>}
        </g>;
      })}
      {labels.map(label=>{
        const n=label.node&&nodes.get(label.node.id),g=label.group;
        const x=n?n.x:label.x,y=camera.y+label.screenY/camera.k+(n?(n.y-label.node.y):0);
        const faded=scope&&(g?g.key:n.group)!==scope;
        return <g key={label.id} data-label-tier={g?"group":label.node.depth} className={g?"atlas-group-label":"graph-node-label"} role="button" tabIndex={g?0:-1} aria-label={g?t("explore.focusGroup",{name:g.name}):label.name} opacity={faded ? .2 : 1} onClick={()=>g?focusGroup(g):selectNode(n)} onKeyDown={e=>activateKey(e,()=>g?focusGroup(g):selectNode(n))}>
          <rect x={x-label.w/2/camera.k} y={y-4/camera.k} width={label.w/camera.k} height={label.h/camera.k} rx={8/camera.k} fill="#0A1018" fillOpacity={g ? .84 : .65}/>
          <text x={x} y={y+10/camera.k} textAnchor="middle" fontSize={14/camera.k} fill={g?"#BDD9F3":"#AFCAE2"}>{label.lines.map((line,i)=><tspan key={i} x={x} dy={i?17/camera.k:0}>{line}</tspan>)}</text>
        </g>;
      })}
    </svg>
    {!data.nodes.length&&<div className="atlas-empty"><h2>{t("explore.empty")}</h2><p>{t("explore.emptyHint")}</p></div>}
    {edge&&<div className="edge-detail"><button onClick={()=>setEdge(null)} aria-label={t("common.close")}>×</button><strong>{edge.a} · {t("relation."+edge.type)} · {edge.b}</strong><p>{edge.reason||t("explore.edgeNoReason")}</p></div>}
    <div className="atlas-bottom"><div className="detail-explainer" aria-live="polite"><strong>{t("zoom."+detail)}</strong><span>{t("zoom."+detail+"Hint")}</span></div><div className="zoom-controls"><button onClick={()=>zoom(1/1.4)} aria-label={t("zoom.out")}>−</button><button onClick={()=>zoom(1.4)} aria-label={t("zoom.in")}>+</button><button onClick={()=>fit(scope?layout.groups.find(g=>g.key===scope):null)}>{t("zoom.fit")}</button></div></div>
  </div>;
}
