import test from "node:test";
import assert from "node:assert/strict";
import { atlasLayout, learningRoute, nodeOffset, zoomDepth, clusterEntry } from "../lib/atlas.mjs";
const nodes = ["Vectors", "Dot products", "Softmax", "Attention", "Transformers", "History"].map((name, i) => ({ id: String(i), name }));
const link = (a,b,type="PREREQUISITE_OF") => ({ source:String(a),target:String(b),type });

test("learning order respects all prerequisite branches and excludes other relation types", () => {
  const graph = { nodes, links:[link(0,1),link(1,3),link(2,3),link(3,4),link(5,4,"RELATED_TO"),link(5,3,"PART_OF")] };
  const route = learningRoute(graph,"4"), ids=route.nodes.map((n)=>n.id);
  assert.equal(route.cycle,false); assert.equal(ids.includes("5"),false);
  for(const e of route.edges) assert.ok(ids.indexOf(e.source)<ids.indexOf(e.target));
  assert.equal(route.edges.length,4);
});
test("cycles are reported instead of inventing an order", () => {
  const route=learningRoute({nodes,links:[link(0,1),link(1,0),link(1,3)]},"3");
  assert.equal(route.cycle,true); assert.deepEqual(route.nodes,[]); assert.deepEqual(route.edges,[]);
});
test("missing endpoints do not create phantom prerequisites", () => {
  assert.deepEqual(learningRoute({nodes,links:[link(99,3)]},"3").nodes.map((n)=>n.name),["Attention"]);
});
test("layout is stable under data ordering and keeps every node inside its group", () => {
  const graph={nodes:nodes.map((n,i)=>({...n,domain:i<3?"Foundations":"Models"})),links:[link(0,1),link(1,3)]};
  const a=atlasLayout(graph), b=atlasLayout({nodes:[...graph.nodes].reverse(),links:[...graph.links].reverse()});
  assert.deepEqual(a,b);
  for(const n of a.nodes){const g=a.groups.find((g)=>g.key===n.group); assert.ok(n.x>g.x && n.x<g.x+g.width && n.y>g.y && n.y<g.y+g.height);}
});
test("unclassified connected concepts have a named neighborhood, not fabricated categories", () => {
  const layout=atlasLayout({nodes:nodes.slice(0,2),links:[link(0,1)]});
  assert.equal(layout.groups.length,1); assert.equal(layout.groups[0].inferred,true);
  assert.ok(nodes.some((n)=>n.name===layout.groups[0].name));
});

test("visual neighborhoods follow edges despite conflicting domain names",()=>{
 const layout=atlasLayout({nodes:[{id:"a",name:"A",domain:"AI"},{id:"b",name:"B",domain:"artificial intelligence"},{id:"c",name:"C",domain:"AI"}],links:[{source:"a",target:"b",type:"RELATED_TO"}]});
 assert.equal(layout.groups.length,2);
 assert.equal(layout.nodes.find(n=>n.id==="a").group,layout.nodes.find(n=>n.id==="b").group);
 assert.notEqual(layout.nodes.find(n=>n.id==="a").group,layout.nodes.find(n=>n.id==="c").group);
 assert.deepEqual(layout.groups.find(g=>g.members.length===2).members.map(n=>n.depth).sort(),[0,1]);
});
test("cursor gently attracts nodes and zoom unfolds graph distance",()=>{
 const n={x:0,y:0}, drift=nodeOffset(0,2,null,n,1), attracted=nodeOffset(0,2,{x:70,y:0},n,1);
 assert.ok(attracted.x>drift.x && attracted.x-drift.x<15);
 assert.deepEqual(nodeOffset(0,2,{x:500,y:0},n,1),drift);
 assert.equal(zoomDepth(.5,.5),0);assert.equal(zoomDepth(.85,.5),1);assert.equal(zoomDepth(1.4,.5),2);
});

test("cluster starts with unfinished prerequisites and never treats PART_OF as a course order",()=>{
 const graph={nodes:nodes.map((n,i)=>({...n,status:i===0?"learned":"queued"})),links:[link(0,1),link(1,3),link(5,3,"PART_OF")]};
 assert.equal(clusterEntry(graph,{hubId:"3"}).node.id,"1");
 graph.nodes.forEach(n=>n.status="learned");
 assert.equal(clusterEntry(graph,{hubId:"3"}).node.id,"3");assert.equal(clusterEntry(graph,{hubId:"3"}).review,true);
 graph.links.push(link(3,1));assert.equal(clusterEntry(graph,{hubId:"3"}).route.cycle,true);
});
