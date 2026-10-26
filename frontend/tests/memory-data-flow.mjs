// My profile: the Memory tab (search, filters, corrections, Undo, phone drill-in) and Your data
// (export, import preview and apply, access keys). All API responses intercepted.
import assert from "node:assert/strict";
const {chromium}=await import(process.env.MENTOR_PLAYWRIGHT_MODULE||"playwright");
const browser=await chromium.launch({headless:true,...(process.env.MENTOR_BROWSER_PATH?{executablePath:process.env.MENTOR_BROWSER_PATH}:{})});
const ORIGIN="http://localhost:3000",CORS={"Access-Control-Allow-Origin":ORIGIN,"Access-Control-Allow-Credentials":"true"};
const ev=(id,outcome,quote)=>({id,kind:"explain",outcome,assessment:"Explained it",quote,seq:1,session_id:"s1",date:"2026-10-20T10:00:00Z",origin:"conversation"});
const concepts=[
 {concept:"Vectors",concept_status:"learned",intent:"learning",self_assessment:{value:"partial",date:"2026-10-20",origin:"learner"},summary:"Directions and magnitudes.",manual_fields:[],covered:["Dot product","Unit vectors"],evidence:[ev("e1","demonstrated","The dot product is four.")],observations:[{id:"o1",kind:"struggles",text:"Confuses magnitude and direction",state:"active",origin:"conversation",evidence_ids:["e1"]}],last_session:"2026-10-24T10:00:00Z",memory_v2:{sessions:{s1:{}},runs:{}}},
 {concept:"Matrices",concept_status:"learned",intent:"learning",self_assessment:{value:"understood",date:"2026-10-01",origin:"learner"},summary:"",manual_fields:[],covered:["Multiplication"],evidence:[],observations:[],last_session:"2026-10-01T10:00:00Z"},
 {concept:"Eigenvalues",concept_status:"learned",intent:"queued",self_assessment:null,summary:"",manual_fields:[],covered:[],evidence:[],observations:[],since:"2026-10-22T10:00:00Z"},
];
const calls=[];
try{
 for(const [w,h,phone] of [[1440,960,false],[390,844,true]]){
  const page=await browser.newPage({viewport:{width:w,height:h},acceptDownloads:true}),errors=[];
  page.on("pageerror",e=>errors.push(e.message));
  await page.addInitScript(()=>{localStorage.setItem("trellis.lang","en");});
  const state=structuredClone(concepts),keys=[];
  await page.route("http://localhost:8000/**",async route=>{
   const req=route.request(),url=new URL(req.url()),path=decodeURIComponent(url.pathname),method=req.method();
   if(method==="OPTIONS"){await route.fulfill({status:204,headers:{...CORS,"Access-Control-Allow-Headers":"content-type","Access-Control-Allow-Methods":"GET,POST,PATCH,DELETE"}});return;}
   const body=req.postData()&&req.headers()["content-type"]==="application/json"?JSON.parse(req.postData()):{};
   calls.push([method,path+url.search,body]);
   let data={},status=200,type="application/json";
   const one=name=>state.find(c=>c.concept===name);
   if(path==="/auth/status")data={setup_needed:false,authenticated:true,person:{id:"paul",name:"Paul",language:"en",is_admin:false},profiles:[],configured:true};
   else if(path==="/auth/settings")data={provider:"gemini",lesson_cost_limit:0};
   else if(path==="/health")data={ok:true,version:"test"};
   else if(path.startsWith("/teach/"))data={enabled:false,cached:0,cost_limit:0,estimated_usd:0,lessons:0,total:0,price_per_mtok:{input:0,output:0}};
   else if(path==="/curriculum")status=503;
   else if(path==="/levels")data={};
   else if(path==="/graph")data={nodes:[],edges:[]};
   else if(path==="/journey/paul")data={goals:[],review:[],sources:[]};
   else if(path==="/journey/paul/examples")data=[];
   else if(path==="/translations")data={texts:body.texts};
   else if(path==="/memory/paul")data={ui_language:"en",ambient_motion:false,learning_profile:{works_well:[],works_poorly:[],preferences:[],teaching_preferences:[],notes:""},concepts:state};
   else if(path.startsWith("/memory/paul/concept/")){
    const [,name,rest,id]=path.slice("/memory/paul/concept/".length).match(/^([^/]+)(?:\/(\w+)(?:\/(\w+))?)?$/)||[];
    const c=one(name);
    if(!rest){for(const k of Object.keys(body)){c[k]=body[k];if(k==="summary")c.manual_fields=["summary"];}}
    else if(rest==="position"){if(body.intent)c.intent=body.intent;if(body.assessment)c.self_assessment={value:body.assessment,date:"2026-10-26",origin:"learner"};}
    else if(rest==="observations"){c.observations.find(o=>o.id===id).state=body.state;}
    const {concept,...rest2}=c;data=rest2;
   }
   else if(path==="/memory/paul/export"){type="application/zip";data=null;await route.fulfill({status,contentType:type,headers:{...CORS,"Access-Control-Expose-Headers":"Content-Disposition","Content-Disposition":'attachment; filename="trellis-memory-2026-10-26.zip"'},body:Buffer.from("PK\x05\x06"+"\0".repeat(18))});return;}
   else if(path==="/memory/paul/import"){
    assert.equal(req.headers()["content-type"],"application/octet-stream");
    const counts={concepts_new:2,concepts_matched:1,understanding_new:2,understanding_merged:1,conversations_new:3,conversations_updated:0,exercises_new:0,goals_new:0};
    data={person:"Paul",exported_at:"2026-10-25T10:00:00Z",counts,warnings:[]};
   }
   else if(path==="/memory/paul/connections"&&method==="GET")data={connections:keys,scopes:{}};
   else if(path==="/memory/paul/connections"&&method==="POST"){const c={id:"k"+(keys.length+1),name:body.name,hint:"trellis_abcd…wxyz",scopes:body.scopes,created_at:"2026-10-26T10:00:00Z",last_used_at:null};keys.unshift(c);data={token:"trellis_secret_value_shown_once",connection:c};}
   else if(path.startsWith("/memory/paul/connections/")&&method==="DELETE"){keys.splice(keys.findIndex(k=>k.id===path.split("/").pop()),1);data={revoked:true};}
   else throw Error("Unexpected request "+method+" "+path);
   await route.fulfill({status,contentType:type,headers:CORS,body:JSON.stringify(data)});
  });
  await page.goto(process.env.MENTOR_TEST_URL||ORIGIN);
  await page.getByRole("button",{name:"My profile"}).first().click();
  const dialog=page.getByRole("dialog",{name:"My profile"});
  await dialog.getByRole("tab",{name:"Memory",exact:true}).click();
  const rows=dialog.locator(".memory-rows button");
  await rows.first().waitFor();
  // Status is this learner's, not the shared concept status: one understood, one learning, one planned.
  assert.deepEqual(await rows.locator(".badge").allTextContents(),["Learning now","Plan to learn","Understood"]);
  await dialog.getByRole("button",{name:/^Understood 1$/}).click();
  assert.deepEqual(await rows.locator("b").allTextContents(),["Matrices"]);
  await dialog.getByRole("button",{name:/^All 3$/}).click();
  await dialog.getByPlaceholder("Search concepts").fill("unit vec");
  assert.deepEqual(await rows.locator("b").allTextContents(),["Vectors"]);
  await dialog.getByPlaceholder("Search concepts").fill("zzz");
  await dialog.getByText("No concepts match.").waitFor();
  await dialog.getByRole("button",{name:"Clear search and filters"}).click();
  if(phone){
   assert.equal(await dialog.locator(".memory-detail").count(),0);
   await rows.filter({hasText:"Vectors"}).click();
   await dialog.getByRole("button",{name:/All concepts/}).waitFor();
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   await page.keyboard.press("Escape");
   await rows.first().waitFor();
   assert.equal(await dialog.isVisible(),true,"Escape on the phone detail goes back to the list, not out of the dialog");
   await rows.filter({hasText:"Vectors"}).click();
  } else {
   // Arrow keys move through the list and show each concept.
   await rows.first().focus();
   await page.keyboard.press("ArrowDown");
   await dialog.locator(".memory-detail-head h3",{hasText:"Eigenvalues"}).waitFor();
   await page.keyboard.press("ArrowUp");
  }
  const detail=dialog.locator(".memory-detail");
  await detail.locator("h3",{hasText:"Vectors"}).waitFor();
  await detail.getByText("Built from 1 conversation(s) and 0 exercise(s).").waitFor();
  // Where I stand: a radio group, saved at once.
  await Promise.all([page.waitForResponse(r=>r.url().endsWith("/position")),detail.getByRole("radiogroup",{name:"My understanding"}).getByRole("radio",{name:"Understood",exact:true}).check()]);
  await rows.filter({hasText:"Vectors"}).locator(".badge",{hasText:"Understood"}).waitFor().catch(async()=>{if(!phone)throw Error("row status did not follow");});
  // Arrow keys on a radio group: every press is kept, saved one at a time, the last one wins.
  const intent=detail.getByRole("radiogroup",{name:"Learning intent"});
  await intent.getByRole("radio",{name:"Learning now",exact:true}).focus();
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.press("ArrowLeft");
  await page.waitForFunction(()=>document.querySelector('.memory-detail input[value="interested"]')?.checked);
  await page.waitForTimeout(300);
  assert.equal(state[0].intent,"interested");
  await Promise.all([page.waitForResponse(r=>r.url().endsWith("/position")),intent.getByRole("radio",{name:"Learning now",exact:true}).check()]);
  // Summary edit; Escape cancels the edit and keeps the dialog open.
  await detail.getByRole("button",{name:"Edit",exact:true}).click();
  await page.keyboard.press("Escape");
  assert.equal(await dialog.isVisible(),true);
  await detail.getByRole("button",{name:"Edit",exact:true}).click();
  await detail.getByRole("textbox",{name:"Summary"}).fill("My own summary.");
  await Promise.all([page.waitForResponse(r=>r.url().endsWith("/concept/Vectors")),detail.getByRole("button",{name:"Save",exact:true}).click()]);
  await detail.getByText("Edited by you. New conversations will not overwrite it.").waitFor();
  // Remove a discussed item, then Undo puts it back.
  await Promise.all([page.waitForResponse(r=>r.url().endsWith("/concept/Vectors")),detail.getByRole("button",{name:"Remove: Unit vectors"}).click()]);
  assert.deepEqual(state[0].covered,["Dot product"]);
  assert.equal(await page.evaluate(()=>document.activeElement?.textContent),"Undo","focus moves to Undo, not to the page");
  await Promise.all([page.waitForResponse(r=>r.url().endsWith("/concept/Vectors")),detail.getByRole("button",{name:"Undo",exact:true}).click()]);
  assert.deepEqual(state[0].covered,["Dot product","Unit vectors"]);
  // Resolve the open difficulty; it moves to earlier observations.
  await Promise.all([page.waitForResponse(r=>r.url().endsWith("/observations/o1")),detail.getByRole("button",{name:"No longer a difficulty",exact:true}).click()]);
  await detail.getByText("Nothing open right now.").waitFor();
  await detail.getByText(/Earlier observations · 1/).waitFor();
  if(!phone){
   // Your data: export, import with preview, an access key shown once, revoke.
   await dialog.getByRole("tab",{name:"Your data",exact:true}).click();
   const [download]=await Promise.all([page.waitForEvent("download"),dialog.getByRole("button",{name:"Download memory (.zip)"}).click()]);
   assert.equal(download.suggestedFilename(),"trellis-memory-2026-10-26.zip");
   await dialog.locator('input[type=file]').setInputFiles({name:"memory.zip",mimeType:"application/zip",buffer:Buffer.from("PK")});
   await dialog.locator(".data-preview").getByText("Ready to import memory.zip").waitFor();
   await dialog.getByText("new conversation(s)").waitFor();
   assert.ok(calls.some(([m,p])=>m==="POST"&&p.endsWith("/import?mode=preview")));
   assert.ok(!calls.some(([m,p])=>p.endsWith("mode=apply")),"nothing applied before confirming");
   await Promise.all([page.waitForResponse(r=>r.url().endsWith("mode=apply")),dialog.getByRole("button",{name:"Import",exact:true}).click()]);
   await dialog.getByText(/^Imported\./).waitFor();
   await dialog.getByLabel("Name").fill("Claude Desktop");
   await dialog.getByRole("button",{name:"Create access key"}).click();
   await dialog.getByText("trellis_secret_value_shown_once",{exact:true}).waitFor();
   assert.deepEqual(calls.findLast(([m,p])=>m==="POST"&&p.endsWith("/connections"))[2],{name:"Claude Desktop",scopes:["memory:read"]});
   await dialog.getByRole("button",{name:"Done, I saved it"}).click();
   assert.equal(await dialog.getByText("trellis_secret_value_shown_once").count(),0);
   await dialog.getByRole("button",{name:"Revoke Claude Desktop"}).click();
   await Promise.all([page.waitForResponse(r=>r.request().method()==="DELETE"),dialog.getByRole("button",{name:"Yes, revoke"}).click()]);
   await dialog.getByText(/Key revoked/).waitFor();
   await page.screenshot({path:(process.env.MENTOR_SHOTS||"/tmp")+"/memory-data.png",fullPage:true});
  }
  assert.deepEqual(errors,[]);
  await page.close();
 }
 console.log("PASS: memory list (learner status, filters, search, keyboard, phone drill-in with Escape), corrections with Undo, summary edit, export download, import preview then apply, access key shown once and revoked.");
}finally{await browser.close();}
