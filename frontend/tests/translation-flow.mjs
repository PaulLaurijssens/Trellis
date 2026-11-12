// Memory written in another language is shown translated into the interface language, with a way
// back to the original, and a failed translation can be retried. All API responses intercepted.
import assert from 'node:assert/strict';
import {mockApi,launch,reply,shot} from './mock-api.mjs';
const ORIGINAL='Een eerdere Nederlandse samenvatting.',TRANSLATED='An earlier Dutch summary.';
const browser=await launch();
try{
 const page=await browser.newPage({viewport:{width:1450,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(12000);
 await page.addInitScript(()=>localStorage.setItem('trellis.lang','en'));
 let failOnce=true;
 const profile={works_well:[],works_poorly:[],preferences:[],teaching_preferences:[],notes:''};
 await mockApi(page,(path,{body})=>{
  if(path==='/graph')return {nodes:[],edges:[]};
  if(path==='/journey/paul')return {goals:[],review:[],sources:[]};
  if(path==='/memory/paul')return {learning_profile:profile,ui_language:'en',ambient_motion:false,
   concepts:[{concept:'Vectors',summary:ORIGINAL,concept_status:'learning',intent:'learning',self_assessment:null,manual_fields:[],covered:[],evidence:[],observations:[],last_session:'2026-10-20T10:00:00Z'}]};
  if(path==='/translations'){
   if(body.texts.includes(ORIGINAL)&&failOnce){failOnce=false;return reply(503,{detail:'Synthetic failure'});}
   return {texts:body.texts.map(x=>x===ORIGINAL?TRANSLATED:x)};
  }
 });
 await page.goto('http://localhost:3000');
 await page.getByRole('button',{name:'My profile'}).first().click();
 const dialog=page.getByRole('dialog',{name:'My profile'});
 await dialog.getByRole('tab',{name:'Memory',exact:true}).click();
 // The first attempt fails: the original stays readable with a retry.
 await dialog.getByText(ORIGINAL,{exact:true}).waitFor();
 await dialog.getByRole('button',{name:'Show translation',exact:true}).click();
 await dialog.getByText(TRANSLATED,{exact:true}).waitFor();
 await dialog.getByRole('button',{name:'Translated · Original',exact:true}).click();
 await dialog.getByText(ORIGINAL,{exact:true}).waitFor();
 await dialog.getByRole('button',{name:'Show translation',exact:true}).click();
 await dialog.getByText(TRANSLATED,{exact:true}).waitFor();
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await shot(page,'memory-translation-mobile.png',{fullPage:true,animations:'disabled'});
 assert.deepEqual(errors,[]);
 console.log('PASS: memory in another language shown translated, original toggle, translation failure and retry, phone width.');
}finally{await browser.close();}
