// Phase 2 UI integration, all API responses intercepted.
import assert from "node:assert/strict";
const {chromium}=await import(process.env.MENTOR_PLAYWRIGHT_MODULE||"playwright");
const browser=await chromium.launch({headless:true,...(process.env.MENTOR_BROWSER_PATH?{executablePath:process.env.MENTOR_BROWSER_PATH}:{})});
try {
 const page=await browser.newPage({viewport:{width:1500,height:1050}}),errors=[];
 page.on("pageerror",e=>errors.push(e.message));
 await page.addInitScript(()=>{localStorage.setItem("trellis.lang","en");sessionStorage.setItem("trellis.learningTrail.paul",JSON.stringify(["Vectors"]));});
 let pending=true,failOnce=true;
 const state={summary:"We compared directions.",intent:"learning",self_assessment:{value:"partial",date:"2026-09-12",origin:"learner"},covered:["Vector directions"],struggles:["Confuses magnitude and direction"],misconceptions:[],evidence:[{id:"proof",kind:"apply",outcome:"demonstrated",assessment:"Applied the dot product to this example",quote:"The dot product is four.",seq:1,session_id:"fixture",date:"2026-09-12"}],observations:[{id:"difficulty",kind:"struggles",text:"Confuses magnitude and direction",state:"active",origin:"legacy",evidence_ids:[]}]};
 const node={id:"v",name:"Vectors",status:"learning"};
 await page.route("http://localhost:8000/**",async route=>{
  const req=route.request(),path=decodeURIComponent(new URL(req.url()).pathname),body=req.postData()?JSON.parse(req.postData()):{};
  if(req.method()==="OPTIONS"){await route.fulfill({status:204,headers:{"Access-Control-Allow-Origin":"*","Access-Control-Allow-Headers":"content-type","Access-Control-Allow-Methods":"GET,POST,PATCH,OPTIONS"}});return;}
  let data={},status=200;
  if(path==="/levels")data={1:"First steps",2:"Foundations",3:"Practical",4:"Technical",5:"Advanced"};
  else if(path==="/journey/paul")data={goals:[],active_goal:null,recent:null,review:[],sources:[]};
  else if(path==="/journey/paul/examples")data=[];
  else if(path==="/graph")data={nodes:[node],edges:[]};
  else if(path==="/concept/Vectors")data={...node,definition:"A quantity with magnitude and direction.",mentions:[]};
  else if(path==="/chat/Vectors/end"){if(failOnce){failOnce=false;status=503;data={detail:"Memory update failed. Please retry."};}else{pending=false;data={consolidated:true,state};}}
  else if(path==="/chat/Vectors")data={session_id:"fixture",state,memory_error:pending?"failed":null,messages:[{seq:0,role:"user",content:"The dot product is four."},{seq:1,role:"assistant",content:"Yes, that follows from these components."}],suggestions:[]};
  else if(path.endsWith("/observations/difficulty")){state.observations[0].state=body.state;state.observations[0].corrected_by="learner";state.struggles=body.state==="active"?[state.observations[0].text]:[];data=state;}
  else if(path.endsWith("/position")){if(body.intent)state.intent=body.intent;if(body.assessment)state.self_assessment.value=body.assessment;data=state;}
  else if(path.startsWith("/memory/"))data={ambient_motion:false,ui_language:"en",learning_profile:{},concepts:[{concept:"Vectors",...state}]};
  else throw Error("Unexpected request "+path);
  await route.fulfill({status,contentType:"application/json",headers:{"Access-Control-Allow-Origin":"*"},body:JSON.stringify(data)});
 });
 await page.goto(process.env.MENTOR_TEST_URL||"http://localhost:3000");
 await page.getByRole("button",{name:"Retry memory update",exact:true}).click();
 await page.getByText("Memory update failed. Please retry.",{exact:true}).waitFor();
 await page.getByRole("button",{name:"Retry memory update",exact:true}).click();
 await page.locator(".memory-retry").waitFor({state:"detached"});
 await page.locator(".memory-recap > summary").click();
 const memory=page.locator(".memory-recap .memory-evolution");
 await Promise.all([page.waitForResponse(r=>r.url().endsWith("/position")),memory.getByLabel("My understanding",{exact:true}).selectOption("understood")]);
 assert.equal(state.self_assessment.value,"understood");
 await Promise.all([page.waitForResponse(r=>r.url().endsWith("/position")),memory.getByLabel("Learning intent",{exact:true}).selectOption("queued")]);
 assert.equal(state.intent,"queued");
 await memory.getByText(/Demonstrated understanding · 1/).click();
 await memory.getByText("The dot product is four.",{exact:true}).waitFor();
 await Promise.all([page.waitForResponse(r=>r.url().endsWith("/observations/difficulty")),memory.getByRole("button",{name:"No longer a difficulty",exact:true}).click()]);
 assert.equal(state.observations[0].state,"resolved");
 await memory.getByText(/Observation history · 1/).click();
 await memory.getByText(/Your correction/).waitFor();
 await Promise.all([page.waitForResponse(r=>r.url().endsWith("/observations/difficulty")),memory.getByRole("button",{name:"Relevant again",exact:true}).click()]);
 assert.equal(state.observations[0].state,"active");
 await page.locator(".chat-log").evaluate(el=>el.scrollTop=0);
 await page.screenshot({path:"/private/tmp/phase2-memory.png",fullPage:true});
 assert.deepEqual(errors,[]);
 console.log("PASS: memory failure/retry, self-assessment, intent, quoted evidence, resolution history and reactivation; no browser errors.");
}finally{await browser.close();}
