// Read-only UI check: optionally render a locally captured /graph response.
// ALL backend requests are intercepted; no model or database mutations occur.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
const {chromium}=await import(process.env.MENTOR_PLAYWRIGHT_MODULE||"playwright");
const graph=process.env.MENTOR_GRAPH_FIXTURE?JSON.parse(await readFile(process.env.MENTOR_GRAPH_FIXTURE,"utf8")):{nodes:Array.from({length:20},(_,i)=>({id:String(i),name:"Topic "+i,status:i%2?"learning":"suggested"})),edges:Array.from({length:19},(_,i)=>({source:String(Math.floor(i/3)),target:String(i+1),type:"PREREQUISITE_OF"}))};
const browser=await chromium.launch({headless:true,...(process.env.MENTOR_BROWSER_PATH?{executablePath:process.env.MENTOR_BROWSER_PATH}:{})});
try{
 const page=await browser.newPage({viewport:{width:1600,height:1000}}),errors=[];
 page.on("pageerror",e=>{errors.push(e.message);console.error(e.message);});
 await page.addInitScript(()=>{localStorage.setItem("dendrite.lang","en");});
 let motion=true;const started=[];
 await page.route("http://localhost:8000/**",async route=>{
  const req=route.request(),path=decodeURIComponent(new URL(req.url()).pathname),body=req.postData()?JSON.parse(req.postData()):{};
  let data={};
  if(req.method()==="OPTIONS"){await route.fulfill({status:204,headers:{"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"content-type","Access-Control-Allow-Methods":"GET, PATCH, OPTIONS"}});return;}
  if(path==="/graph")data=graph;
  else if(path==="/journey/paul")data={goals:[],active_goal:null,recent:null,review:[],sources:[]};
  else if(path==="/journey/paul/examples")data=[];
  else if(path==="/levels")data={1:"First steps",2:"Foundations",3:"Practical",4:"Technical",5:"Advanced"};
  else if(path.startsWith("/memory")){if(typeof body.ambient_motion==="boolean")motion=body.ambient_motion;data={ui_language:"en",ambient_motion:motion,learning_profile:{},concepts:[]};}
  else if(path.startsWith("/concept/")){const n=graph.nodes.find(n=>n.name===path.slice(9));data={...n,definition:"Fixture preview for navigation testing.",mentions:[]};}
  else if(path==="/learn"){started.push(body.concept);data={concept:body.concept,explanation:"A guided explanation of "+body.concept};}
  else if(path.startsWith("/chat/"))data={messages:started.includes(path.slice(6))?[{seq:0,role:"assistant",content:"A guided explanation of "+path.slice(6)}]:[],state:{},suggestions:[]};
  else if(path==="/translations")data={texts:body.texts};
  else throw Error("Unexpected request "+path);
  await route.fulfill({status:200,contentType:"application/json",headers:{"Access-Control-Allow-Origin":"*"},body:JSON.stringify(data)});
 });
 await page.goto(process.env.MENTOR_TEST_URL||"http://localhost:3000");
 await page.locator(".node-core").first().waitFor();
 await page.getByRole("button",{name:"Fit",exact:true}).click();
 const point=()=>page.locator(".node-core").first().evaluate(n=>[n.getAttribute("cx"),n.getAttribute("cy")]);
 const before=await point();
 await page.waitForFunction(p=>{const n=document.querySelector(".node-core");return n.getAttribute("cx")!==p[0]||n.getAttribute("cy")!==p[1];},before);
 assert.equal(await page.locator(".atlas-layer").getAttribute("data-depth"),"0");
 assert.ok(await page.locator('.atlas-node[data-tier="1"]').count()>0,"next tier visible even at overview");
 assert.equal(await page.locator('.graph-node-label[data-label-tier="1"]').count(),0,"next-tier names stay hidden at overview");
 assert.ok(await page.locator(".graph-connection").count()>0,"overview has graph connections");
 const dir=process.env.MENTOR_SHOT_DIR||"/private/tmp";
 await page.screenshot({path:dir+"/living-graph-overview.png"});
 const group=process.env.MENTOR_GRAPH_FIXTURE?page.getByRole("button",{name:/Explore group Information Retrieval/}):page.locator(".atlas-group-label").first();
 await group.focus();await page.keyboard.press("Enter");
 assert.ok(Number(await page.locator(".atlas-layer").getAttribute("data-depth"))>=1);
 await page.screenshot({path:dir+"/living-graph-zoom.png"});
 const recommended=await page.locator(".cluster-start h2").innerText();
 await page.getByRole("button",{name:/^(Start learning|Review with mentor)/}).click();
 await page.locator(".learn-workspace").waitFor();
 assert.ok(recommended.includes(started.at(-1)),"cluster CTA begins its recommended topic");
 await page.getByText("A guided explanation of "+started.at(-1),{exact:true}).waitFor();
 await page.getByRole("navigation",{name:"Workspace"}).getByRole("button",{name:"Explore",exact:true}).click();
 await page.getByRole("button",{name:"Zoom in",exact:true}).click();
 await page.screenshot({path:dir+"/living-graph-detail.png"});
 // Clicking outside exits focus; dragging the same background only pans.
 const focused=await page.locator(".scope-chip").innerText();
 const canvas=page.locator(".living-graph > svg"), bounds=await canvas.boundingBox();
 await page.mouse.move(bounds.x+bounds.width-30,bounds.y+80);
 await page.mouse.down();await page.mouse.move(bounds.x+bounds.width-90,bounds.y+110,{steps:5});await page.mouse.up();
 assert.equal(await page.locator(".scope-chip").innerText(),focused,"panning preserves cluster focus");
 await canvas.click({position:{x:bounds.width-30,y:80}});
 await page.locator(".scope-chip").waitFor({state:"detached"});
 assert.equal(await page.locator(".scope-chip").count(),0,"outside click clears cluster focus");
 assert.equal(await page.locator(".atlas-layer").getAttribute("data-depth"),"0","outside click restores overview");
 await group.focus();await page.keyboard.press("Enter");
 const outside=page.locator('.atlas-node[opacity="0.16"]').first();
 if(await outside.count()){
  await outside.focus();await page.keyboard.press("Enter");
  await page.locator(".scope-chip").waitFor({state:"detached"});
 assert.equal(await page.locator(".scope-chip").count(),0,"outside-node selection clears old focus");
  await page.locator(".learn-workspace").waitFor();
  await page.getByRole("button",{name:"Start lesson",exact:true}).waitFor();
  await page.screenshot({path:dir+"/lesson-start.png"});
  await page.getByRole("button",{name:"Start lesson",exact:true}).click();
  await page.getByText("A guided explanation of "+started.at(-1),{exact:true}).waitFor();
  await page.getByRole("navigation",{name:"Workspace"}).getByRole("button",{name:"Explore",exact:true}).click();
  await page.locator(".preview-close").click();
 }
 await group.focus();await page.keyboard.press("Enter");
 await canvas.focus();await page.keyboard.press("Escape");
 await page.locator(".scope-chip").waitFor({state:"detached"});
 assert.equal(await page.locator(".scope-chip").count(),0,"Escape restores overview");
 await page.locator(".profile-trigger").click();
 await page.getByRole("checkbox",{name:/Ambient motion/}).uncheck();
 await page.waitForFunction(()=>document.querySelector(".atlas-layer").dataset.motionEnabled==="false");
 const frozen=await point();
 await page.waitForTimeout(200);
 assert.deepEqual(await point(),frozen,"motion off freezes positions");
 await page.getByRole("checkbox",{name:/Ambient motion/}).check();
 await page.emulateMedia({reducedMotion:"reduce"});
 await page.waitForFunction(()=>document.querySelector(".atlas-layer").dataset.motionEnabled==="false");
 await page.locator(".profile-head .x").click();
 await page.setViewportSize({width:390,height:844});
 await page.waitForFunction(()=>{const el=document.querySelector(".living-graph"),r=el.getBoundingClientRect();return el.dataset.orientation===(r.width<r.height?"portrait":"landscape");});
 if(await page.locator(".scope-chip").count())await page.locator(".scope-chip").click();
 await page.getByRole("button",{name:"Fit",exact:true}).click();
 await page.screenshot({path:dir+"/living-graph-mobile.png"});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert.deepEqual(errors,[]);
 console.log(`PASS: ${graph.nodes.length} nodes, connected overview, next-tier dots, semantic zoom, real motion, motion off, reduced motion, keyboard cluster focus, mobile; no runtime errors.`);
}finally{await browser.close();}
