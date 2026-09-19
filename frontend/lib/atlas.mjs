import { forceSimulation, forceManyBody, forceLink, forceCollide, forceX, forceY } from "d3-force-3d";
export const idOf = (value) => typeof value === "object" ? value?.id : value;
const byName = (a, b) => a.name.localeCompare(b.name);

// Only prerequisite edges establish learning order. PART_OF and RELATED_TO
// remain visible on the map, but are never silently treated as prerequisites.
export function learningRoute(graph, targetId) {
  const nodes = new Map(graph.nodes.map((n) => [n.id, n]));
  const links = graph.links.filter((l) => l.type === "PREREQUISITE_OF" && nodes.has(idOf(l.source)) && nodes.has(idOf(l.target)));
  const needed = new Set();
  function collect(id) {
    if (needed.has(id)) return;
    needed.add(id);
    links.filter((l) => idOf(l.target) === id).forEach((l) => collect(idOf(l.source)));
  }
  if (!nodes.has(targetId)) return { nodes: [], edges: [], cycle: false };
  collect(targetId);
  const edges = links.filter((l) => needed.has(idOf(l.source)) && needed.has(idOf(l.target)));
  const degree = new Map([...needed].map((id) => [id, 0]));
  edges.forEach((l) => degree.set(idOf(l.target), degree.get(idOf(l.target)) + 1));
  const ready = [...needed].filter((id) => degree.get(id) === 0).map((id) => nodes.get(id)).sort(byName);
  const order = [];
  while (ready.length) {
    const n = ready.shift(); order.push(n);
    edges.filter((l) => idOf(l.source) === n.id).forEach((l) => {
      const id = idOf(l.target); degree.set(id, degree.get(id) - 1);
      if (degree.get(id) === 0) { ready.push(nodes.get(id)); ready.sort(byName); }
    });
  }
  const cycle = order.length !== needed.size;
  return { nodes: cycle ? [] : order, edges: cycle ? [] : edges, cycle };
}

// Visual neighborhoods follow actual connections. Domain strings are deliberately
// not used as taxonomy: capitalization and one-off labels fragmented the real map.
export function atlasLayout(graph, portrait = false) {
  const nodes = graph.nodes.map((n) => ({ ...n })).sort(byName);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const links = graph.links.filter((e) => byId.has(idOf(e.source)) && byId.has(idOf(e.target)))
    .map((e) => ({ ...e, source: idOf(e.source), target: idOf(e.target) }))
    .sort((a,b) => `${a.source}:${a.target}`.localeCompare(`${b.source}:${b.target}`));
  const neighbors = new Map(nodes.map((n) => [n.id, new Set()]));
  links.forEach((e) => { neighbors.get(e.source).add(e.target); neighbors.get(e.target).add(e.source); });
  const seen = new Set(), groups = [];
  for (const first of nodes) {
    if (seen.has(first.id)) continue;
    const todo = [first.id], members = [];
    while (todo.length) {
      const id = todo.pop(); if (seen.has(id)) continue;
      seen.add(id); members.push(byId.get(id));
      [...neighbors.get(id)].sort().forEach((other) => { if (!seen.has(other)) todo.push(other); });
    }
    members.sort((a,b) => neighbors.get(b.id).size - neighbors.get(a.id).size || byName(a,b));
    const hub = members[0], key = hub.id;
    // Breadth is visual graph distance, never a prerequisite/learning order.
    const depths = new Map([[hub.id,0]]), queue = [hub.id];
    for (let i=0;i<queue.length;i++) for (const id of neighbors.get(queue[i])) {
      if (!depths.has(id)) { depths.set(id, depths.get(queue[i])+1); queue.push(id); }
    }
    members.forEach((n,i) => { n.group=key; n.depth=depths.get(n.id); n.degree=neighbors.get(n.id).size;
      const angle=i*2.399963; n.x=i ? Math.cos(angle)*Math.sqrt(i)*35 : 0; n.y=i ? Math.sin(angle)*Math.sqrt(i)*35 : 0; });
    const ids = new Set(members.map(n=>n.id));
    const localLinks=links.filter(e=>ids.has(e.source)&&ids.has(e.target)).map(e=>({...e}));
    const simulation=forceSimulation(members,2).stop()
      .force("link",forceLink(localLinks).id(n=>n.id).distance(66).strength(.45))
      .force("charge",forceManyBody().strength(-170))
      .force("collision",forceCollide(19))
      .force("x",forceX(0).strength(.025)).force("y",forceY(0).strength(.025));
    simulation.tick(180); simulation.stop();
    const minX=Math.min(...members.map(n=>n.x)), maxX=Math.max(...members.map(n=>n.x));
    const minY=Math.min(...members.map(n=>n.y)), maxY=Math.max(...members.map(n=>n.y));
    members.forEach(n=>{ n.x-=(minX+maxX)/2; n.y-=(minY+maxY)/2; });
    const rx=Math.max(55,(maxX-minX)/2+46), ry=Math.max(48,(maxY-minY)/2+46);
    // Ellipse contains the corner nodes as well as the hull's extrema.
    let expand=1;
    members.forEach(n=>{expand=Math.max(expand,Math.hypot(n.x/(rx-24),n.y/(ry-24)));});
    groups.push({key,name:hub.name,inferred:true,hubId:hub.id,members,rx:rx*expand,ry:ry*expand});
  }
  groups.sort((a,b)=>b.members.length-a.members.length||a.name.localeCompare(b.name));
  groups.forEach((g,i)=>{const angle=i*2.399963;g.x=Math.cos(angle)*Math.sqrt(i)*130;g.y=Math.sin(angle)*Math.sqrt(i)*100;g.radius=Math.max(g.rx,g.ry)+24;});
  const packing=forceSimulation(groups,2).stop().force("collision",forceCollide(g=>g.radius).iterations(3))
    .force("x",forceX(0).strength(portrait ? .16 : .018)).force("y",forceY(0).strength(portrait ? .018 : .16));
  packing.tick(200);packing.stop();
  groups.forEach(g=>{g.cx=g.x;g.cy=g.y;g.x=g.cx-g.rx;g.y=g.cy-g.ry;g.width=2*g.rx;g.height=2*g.ry;g.members.forEach(n=>{n.x+=g.cx;n.y+=g.cy;});});
  const x=Math.min(-120,...groups.map(g=>g.x))-45, y=Math.min(-90,...groups.map(g=>g.y))-55;
  return {groups,nodes:groups.flatMap(g=>g.members),x,y,width:Math.max(240,...groups.map(g=>g.x+g.width))-x+45,height:Math.max(180,...groups.map(g=>g.y+g.height))-y+55};
}

// Bounded drift preserves the graph's shape; attraction never follows the cursor
// off-screen or turns into a persistent displacement. Units are screen pixels.
export function nodeOffset(index, seconds, pointer, node, scale) {
  const k=Math.max(.1,scale);
  const dx=Math.sin(seconds*.55+index*1.71)*4/k;
  const dy=Math.cos(seconds*.43+index*2.31)*3.5/k;
  if (!pointer) return {x:dx,y:dy};
  const px=(pointer.x-node.x)*k, py=(pointer.y-node.y)*k, distance=Math.hypot(px,py);
  const attraction=Math.max(0,1-distance/180)*.14;
  return {x:dx+px*attraction/k,y:dy+py*attraction/k};
}

export function zoomDepth(scale, fittedScale) {
  return Math.max(0,Math.floor(Math.log(Math.max(1,scale/fittedScale))/Math.log(1.65)+.001));
}

// Start toward the cluster's named topic, respecting only prerequisite edges.
export function clusterEntry(graph, group) {
  if (!group) return null;
  const hub=graph.nodes.find(n=>n.id===group.hubId);
  if(!hub)return null;
  let goal=hub,route=learningRoute(graph,hub.id);
  if(!route.cycle&&route.nodes.every(n=>n.status==="learned")) {
    const next=[...(group.members||[])].filter(n=>n.status!=="learned").sort(byName)[0];
    if(next){goal=next;route=learningRoute(graph,next.id);}
  }
  return {node:route.nodes.find(n=>n.status!=="learned")||goal,goal,route,review:route.nodes.length>0&&route.nodes.every(n=>n.status==="learned")};
}
