// Optional browser integration check. Uses a running frontend and intercepts ALL
// backend requests: never calls Neo4j, model providers, or personal data.
// MENTOR_PLAYWRIGHT_MODULE may point to a temporary Playwright installation.
import assert from "node:assert/strict";
const { chromium } = await import(process.env.MENTOR_PLAYWRIGHT_MODULE || "playwright");
const browser = await chromium.launch({ headless: true, ...(process.env.MENTOR_BROWSER_PATH ? { executablePath: process.env.MENTOR_BROWSER_PATH } : {}) });
try {
  const page = await browser.newPage({ viewport: { width: 1536, height: 1024 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.addInitScript(() => {
    localStorage.setItem("trellis.lang", "en");
    if (!sessionStorage.getItem("trellis.learningTrail.paul")) {
      sessionStorage.setItem("trellis.learningTrail.paul", '["Attention"]');
    }
  });
  const names = ["Vectors", "Dot products", "Matrices", "Probability", "Softmax", "Attention", "Embeddings", "Transformers", "Multi-head attention", "Positional encoding", "Gradients", "Backpropagation", "Loss functions", "Optimization"];
  const nodes = names.map((name, i) => ({ id: name, name, status: name === "Attention" ? "learning" : i < 2 ? "learned" : i % 3 ? "suggested" : "queued", domain: i < 5 ? "Foundations" : i < 10 ? "Attention & transformers" : "Training" }));
  const edges = [["Vectors", "Dot products"], ["Dot products", "Attention"], ["Softmax", "Attention"], ["Attention", "Transformers"], ["Embeddings", "Attention"], ["Positional encoding", "Transformers"], ["Gradients", "Backpropagation"], ["Backpropagation", "Optimization"], ["Loss functions", "Optimization"], ["Probability", "Softmax"]].map(([source,target])=>({source,target,type:"PREREQUISITE_OF",reason:"This builds on the earlier concept."}));
  edges.push({source:"Multi-head attention",target:"Attention",type:"PART_OF"});
  const illustration = {type:"vectors",title:"A worked example",vectors:[{label:"Query",x:2,y:1},{label:"Key",x:1,y:2}],caption:"Illustrative vectors: compare their directions and lengths."};
  let ambient = true;
  const suggestions = [
    { id: "vectors", name: "Vector similarity", reason: "Understand what attention compares.", definition: "A collection of numerical components.", state: "pending" },
    { id: "softmax", name: "Scaling scores", reason: "Turn scores into weights.", definition: "A normalization function.", state: "pending" },
    { id: "scaling", name: "Normalization", reason: "Keep scores in a useful range.", definition: "Changing numerical magnitude.", state: "pending" },
  ];
  const messages = { Attention: [{ seq: 0, role: "user", content: "Why does attention use dot products?" }, { seq: 1, role: "assistant", content: "The dot product gives attention a compatibility score between a query and a key. When their directions align, the score tends to be larger.\n\nThink of the query as what you are looking for, and the key as what each token offers. The illustration below makes this comparison concrete.", illustration }], Vectors: [], Softmax: [] };
  let failSave = true;
  await page.route("http://localhost:8000/**", async (route) => {
    const req = route.request();
    if (req.method() === "OPTIONS") {
      await route.fulfill({ status: 204, headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "content-type", "Access-Control-Allow-Methods": "GET, POST, PATCH, OPTIONS" } });
      return;
    }
    const path = decodeURIComponent(new URL(req.url()).pathname);
    const body = req.postData() ? JSON.parse(req.postData()) : {};
    let data = {}, status = 200;
    if (path === "/levels") data = { 1: "child", 2: "student", 3: "professional", 4: "developer", 5: "expert" };
    else if (path === "/journey/paul") data = {goals:[],active_goal:null,recent:null,review:[],sources:[]};
    else if (path === "/journey/paul/examples") data = [];
    else if (path === "/graph") data = { nodes, edges };
    else if (path.startsWith("/memory")) { if(typeof body.ambient_motion === "boolean") ambient=body.ambient_motion; data = { ui_language: "en", ambient_motion: ambient, learning_profile: {}, concepts: [] }; }
    else if (path.startsWith("/concept/")) {
      const name = path.slice(9);
      data = { ...nodes.find((n) => n.name === name), definition: "A useful concept.", mentions: [], prerequisites: [], related: [] };
    } else if (path === "/learn") { data = {concept:body.concept, explanation:"Let us explore this concept.", illustration}; messages[body.concept]=[{seq:0,role:"assistant",content:data.explanation,illustration}];
    } else if (path === "/chat") {
      messages[body.concept].push({ seq: messages[body.concept].length, role: "user", content: body.message });
      messages[body.concept].push({ seq: messages[body.concept].length, role: "assistant", content: "Let us connect this to the earlier question.", illustration });
      data = { answer: "Let us connect this to the earlier question.", illustration };
    } else if (path.startsWith("/chat/")) {
      const name = path.slice(6);
      data = { session_id: name, level: name === "Attention" ? 5 : 3, messages: messages[name] || [], state: { covered: ["Weighted averages"] }, suggestions: name === "Attention" ? suggestions : [] };
    } else if (path.startsWith("/suggestions/")) {
      const [, , id, action] = path.split("/");
      const s = suggestions.find((item) => item.id === id);
      if (action === "dismiss") s.state = "dismissed";
      else if (body.action === "save" && failSave) { failSave = false; status = 503; data = { detail: "Temporary test failure. Please retry." }; }
      else {
        s.state = body.action === "save" ? "queued" : "explored";
        if (!nodes.some((n) => n.name === s.name)) {
          nodes.push({ id: s.id, name: s.name, status: body.action === "save" ? "queued" : "learning", degree: 1 });
          edges.push({ source: s.id, target: "Attention", type: "PREREQUISITE_OF" });
        }
      }
      if (status === 200) data = { id, state: s.state, concept: s.name };
    } else throw new Error("Unexpected fixture request " + path);
    await route.fulfill({ status, contentType: "application/json", headers: { "Access-Control-Allow-Origin": "*" }, body: JSON.stringify(data) });
  });
  await page.goto(process.env.MENTOR_TEST_URL || "http://127.0.0.1:3100");
  page.setDefaultTimeout(12000);
  await page.getByRole("heading", { name: "Why does attention use dot products?", exact: true }).waitFor();
  await page.locator(".teaching-figure").waitFor();
  await page.locator(".chat-log").evaluate(el => el.scrollTop=0);
  await page.screenshot({ path: (process.env.MENTOR_SHOT_DIR || "/private/tmp") + "/redesign-learn.png", fullPage:true, animations:"disabled" });
  const card = (name) => page.locator(".conversation-suggestion").filter({ has: page.locator("strong", { hasText: name }) });
  assert.equal(await page.locator(".conversation-suggestion:visible").count(), 1);
  await page.getByText(/More paths/).click();
  await card("Normalization").getByRole("button", { name:"Dismiss" }).click();
  await card("Normalization").waitFor({state:"detached"});
  assert.equal(nodes.length,14);
  await card("Scaling scores").getByRole("button",{name:"Save for later"}).click();
  await page.getByText("Temporary test failure. Please retry.",{exact:true}).waitFor();
  await card("Scaling scores").getByRole("button",{name:"Save for later"}).click();
  await card("Scaling scores").waitFor({state:"detached"});
  assert.equal(nodes.length,15);
  await card("Vector similarity").getByRole("button",{name:"Explore",exact:true}).click();
  await page.getByRole("heading",{name:"Vector similarity",exact:true}).waitFor();
  await page.reload();
  await page.getByRole("heading",{name:"Vector similarity",exact:true}).waitFor();
  await page.getByRole("button",{name:/Return to Attention$/}).click();
  await page.getByRole("heading",{name:"Why does attention use dot products?",exact:true}).waitFor();
  await page.getByRole("button",{name:"Show this visually",exact:true}).click();
  await page.getByText("Let us connect this to the earlier question.",{exact:true}).waitFor();
  await page.getByRole("navigation",{name:"Workspace"}).getByRole("button",{name:"Explore",exact:true}).click();
  await page.locator(".concept-preview").waitFor();
  assert.equal(await page.locator(".learning-route").getByRole("button",{name:/Multi-head attention/}).count(),0,"PART_OF is not a prerequisite");
  await page.getByRole("button",{name:"Fit",exact:true}).click();
  await page.screenshot({path:(process.env.MENTOR_SHOT_DIR || "/private/tmp")+"/redesign-explore.png",fullPage:true,animations:"disabled"});
  const camera = await page.locator(".atlas-layer > svg").getAttribute("viewBox");
  await page.getByRole("button",{name:/Continue learning/}).click();
  await page.getByRole("navigation",{name:"Workspace"}).getByRole("button",{name:"Explore",exact:true}).click();
  assert.equal(await page.locator(".atlas-layer > svg").getAttribute("viewBox"),camera,"map position survives Learn/Explore switching");
  for(let i=0;i<4;i++) await page.getByRole("button",{name:"Zoom out",exact:true}).click();
  assert.equal(await page.locator(".atlas-layer").getAttribute("data-detail"),"overview");
  await page.getByRole("button",{name:"Explore group Attention",exact:true}).click();
  assert.equal(await page.locator(".atlas-layer").getAttribute("data-detail"),"concepts");
  for(let i=0;i<3;i++) await page.getByRole("button",{name:"Zoom in",exact:true}).click();
  assert.equal(await page.locator(".atlas-layer").getAttribute("data-detail"),"relations");
  await page.locator(".profile-trigger").click();
  const motion = page.getByRole("checkbox",{name:/Ambient motion/});
  await motion.uncheck();
  await page.waitForFunction(()=>document.querySelector(".atlas-layer").dataset.motionEnabled==="false");
  assert.equal(ambient,false);
  await motion.check();
  await page.waitForFunction(()=>document.querySelector(".atlas-layer").dataset.motionEnabled==="true");
  await page.emulateMedia({reducedMotion:"reduce"});
  await page.waitForFunction(()=>document.querySelector(".atlas-layer").dataset.motionEnabled==="false");
  await page.locator(".profile-head .x").click();
  await page.getByRole("navigation",{name:"Workspace"}).getByRole("button",{name:"Learn",exact:true}).click();
  await page.setViewportSize({width:390,height:844});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth),"no mobile page overflow");
  await page.getByRole("button",{name:"In context",exact:true}).click();
  await page.locator(".lesson-context").waitFor({state:"visible"});
  await page.getByRole("button",{name:"In context",exact:true}).click();
  await page.locator(".chat-log").evaluate(el=>el.scrollTop=0);
  await page.screenshot({path:(process.env.MENTOR_SHOT_DIR || "/private/tmp")+"/redesign-mobile.png",fullPage:true,animations:"disabled"});
  await page.locator(".profile-trigger").click();
  await page.getByRole("button",{name:"Nederlands",exact:true}).click();
  await page.locator(".profile-head .x").click();
  await page.getByRole("button",{name:"Laat dit visueel zien",exact:true}).waitFor();
  // Empty graph remains navigable before the learner imports real content.
  nodes.splice(0); edges.splice(0);
  await page.evaluate(()=>sessionStorage.removeItem("trellis.learningTrail.paul"));
  await page.reload();
  await page.getByRole("navigation",{name:"Workspace"}).getByRole("button",{name:"Explore",exact:true}).click();
  await page.locator(".atlas-empty").waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
  assert.deepEqual(errors,[],"no browser errors");
  console.log("PASS: illustrations, progressive suggestions, failed save/retry, explore/reload/return, stable map, prerequisite routes, zoom detail, persistent motion, reduced motion, mobile layout; no browser errors.");
} finally { await browser.close(); }
