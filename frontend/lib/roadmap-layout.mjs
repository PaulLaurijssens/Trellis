// A readable spanning forest: one displayed parent per module. Extra graph
// prerequisites remain available in the mentor, rather than crossing this map.
// Desktop: compact pill nodes in four stage columns, joined by smooth curves.
export const STAGE_WIDTH=320, STAGE_LEFT=48, NODE_WIDTH=232, NODE_HEIGHT=68, ROW_STEP=104, TOP=72;
export function roadmapLayout(plan, graph, mobile, viewportWidth) {
 const groups=plan.groups.map((g,key)=>({...g,key,children:[],width:mobile?Math.max(250,viewportWidth-48):NODE_WIDTH,height:NODE_HEIGHT}));
 const owner=new Map(groups.flatMap(g=>g.ids.map(id=>[id,g]))), weights=new Map();
 const id=x=>typeof x==='object'?x?.id:x;
 for(const e of graph.links){if(e.type!=='PREREQUISITE_OF')continue;const a=owner.get(id(e.source)),b=owner.get(id(e.target));if(!a||!b||a.stage>=b.stage)continue;const k=a.key+':'+b.key;weights.set(k,(weights.get(k)||0)+1);}
 const edges=[];
 for(const b of [...groups].sort((a,b)=>a.stage-b.stage)){
  const earlier=groups.filter(a=>a.stage<b.stage);if(!earlier.length)continue;
  const recorded=earlier.filter(a=>weights.has(a.key+':'+b.key)).sort((a,c)=>weights.get(c.key+':'+b.key)-weights.get(a.key+':'+b.key)||c.stage-a.stage);
  const candidates=earlier.filter(a=>a.stage===Math.max(...earlier.map(g=>g.stage))).sort((a,c)=>a.children.length-c.children.length||a.key-c.key);
  const parent=recorded[0]||candidates[0];parent.children.push(b);b.parent=parent.key;edges.push({a:parent,b,suggested:!recorded.length});
 }
 let row=0;
 function place(g){if(g.children.length){g.children.forEach(place);g.y=(g.children[0].y+g.children.at(-1).y)/2;}else {g.y=TOP+row*ROW_STEP;row++;}g.x=STAGE_LEFT+g.stage*STAGE_WIDTH;}
 groups.filter(g=>g.parent===undefined).forEach(g=>{place(g);row+=.5;});
 if(mobile){let y=48;const visit=g=>{g.x=24;g.y=y;y+=NODE_HEIGHT+56;g.children.forEach(visit);};groups.filter(g=>g.parent===undefined).forEach(visit);}
 // The route: the chain from the first not-yet-understood group back to its root.
 return {groups,edges,width:mobile?viewportWidth:Math.max(STAGE_LEFT+4*STAGE_WIDTH,...groups.map(g=>g.x+g.width+64)),height:Math.max(480,...groups.map(g=>g.y+g.height+96))};
}
export function routeKeys(layout, first) {
 const keys=new Set();let g=layout.groups.find(g=>first&&g.ids.includes(first.id));
 while(g){keys.add(g.key);g=g.parent===undefined?null:layout.groups.find(x=>x.key===g.parent);}
 return keys;
}
