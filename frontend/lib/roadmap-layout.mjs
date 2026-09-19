// A readable spanning forest: one displayed parent per module. Extra graph
// prerequisites remain available in the mentor, rather than crossing this map.
export function roadmapLayout(plan, graph, mobile, viewportWidth) {
 const groups=plan.groups.map((g,key)=>({...g,key,children:[],width:mobile?Math.max(250,viewportWidth-48):260,height:112}));
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
 function place(g){if(g.children.length){g.children.forEach(place);g.y=(g.children[0].y+g.children.at(-1).y)/2;}else {g.y=70+row*190;row++;}g.x=64+g.stage*460;}
 groups.filter(g=>g.parent===undefined).forEach(g=>{place(g);row+=.5;});
 if(mobile){let y=48;const visit=g=>{g.x=24;g.y=y;y+=174;g.children.forEach(visit);};groups.filter(g=>g.parent===undefined).forEach(visit);}
 return {groups,edges,width:mobile?viewportWidth:Math.max(1940,...groups.map(g=>g.x+g.width+100)),height:Math.max(550,...groups.map(g=>g.y+g.height+100))};
}
