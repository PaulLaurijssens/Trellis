"""Pure, replayable memory records. Legacy observations never become test evidence."""
from copy import deepcopy
from hashlib import sha256
import json

FIELDS = ("covered", "struggles", "misconceptions")

def key(*parts):
    return sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]

def norm(text):
    return " ".join(str(text).casefold().split())

def initialize(state, concept_id, concept_status=None):
    if isinstance(state.get("memory_v2"), dict):
        return deepcopy(state["memory_v2"])
    baseline = {k: deepcopy(v) for k,v in state.items() if k != "memory_v2"}
    observations=[]
    for field in FIELDS:
        for text in state.get(field, []):
            observations.append({"id":key("legacy",concept_id,field,norm(text)),"kind":field,"text":text,
                                 "state":"active","origin":"legacy","evidence_ids":[],"date":None})
    return {"version":2,"baseline":baseline,"legacy":observations,"sessions":{},"corrections":{},
            "intent":"queued" if concept_status=="queued" else "interested" if concept_status=="suggested" else "learning",
            "self_assessment":{"value":"understood","date":None,"origin":"legacy"} if concept_status=="learned" else None}

def validate(data, messages, session_id, date):
    if not isinstance(data,dict) or not all(isinstance(data.get(k),list) for k in ("evidence","observations","changes")):
        raise ValueError("Invalid memory response; session remains retryable")
    source={m.get("seq",i):m for i,m in enumerate(messages)}
    evidence, refs=[],{}
    for item in data["evidence"][:30]:
        if not isinstance(item,dict): continue
        seq=item.get("seq");m=source.get(seq) if isinstance(seq,int) and not isinstance(seq,bool) else None
        quote=item.get("quote");kind=item.get("kind");outcome=item.get("outcome")
        if not m or m["role"]!="user" or not isinstance(quote,str) or not quote.strip() or quote not in m["content"]: continue
        if kind not in ("explain","apply","connect") or outcome not in ("demonstrated","needs_practice"): continue
        eid=key(session_id,seq,kind,quote)
        evidence.append({"id":eid,"kind":kind,"outcome":outcome,"quote":quote[:2000],"seq":seq,
                         "session_id":session_id,"date":m.get("ts") or date,"assessment":str(item.get("assessment", ""))[:500],
                         "check":item.get("check") is True,"origin":"conversation"})
        if isinstance(item.get("key"),str): refs[item["key"]]=eid
    by_id={e["id"]:e for e in evidence}
    def evidence_refs(item):
        values=item.get("evidence_keys",[])
        return list(dict.fromkeys(refs[v] for v in values if isinstance(v,str) and v in refs)) if isinstance(values,list) else []
    observations=[]
    for item in data["observations"][:30]:
        if not isinstance(item,dict): continue
        kind=item.get("kind");text=item.get("text");ids=evidence_refs(item)
        if kind not in ("struggles","misconceptions") or not isinstance(text,str) or not text.strip() or not ids: continue
        observations.append({"id":key(session_id,kind,norm(text),ids),"kind":kind,"text":text.strip()[:240],
                             "state":"active","origin":"conversation","date":date,"evidence_ids":ids})
    changes=[]
    for item in data["changes"][:30]:
        if not isinstance(item,dict):continue
        ids=evidence_refs(item)
        if item.get("state") not in ("resolved","superseded") or not isinstance(item.get("observation_id"),str):continue
        if not ids or any(by_id[e]["outcome"]!="demonstrated" for e in ids):continue
        changes.append({"observation_id":item["observation_id"],"state":item["state"],"evidence_ids":ids,"date":date})
    strings=lambda value:[s.strip()[:240] for s in value[:30] if isinstance(s,str) and s.strip()] if isinstance(value,list) else []
    style=data.get("learning_style") if isinstance(data.get("learning_style"),dict) else {}
    return {"evidence":list(by_id.values()),"observations":observations,"changes":changes,
            "covered":strings(data.get("covered",[])),"summary":str(data.get("summary") or "")[:1500],
            "learning_style":{f:strings(style.get(f,[])) for f in ("works_well","works_poorly","preferences")},"date":date}

def project(doc):
    state={k:deepcopy(v) for k,v in doc["baseline"].items() if k not in ("level","last_session","since","concept_id","concept_status","concept","status")}
    records={o["id"]:deepcopy(o) for o in doc["legacy"]}
    evidence={};covered=list(state.get("covered",[]));checks={};summary_inactive=set()
    blocked={norm(s) for s in state.get("removed",[])}
    for sid,entry in sorted(doc["sessions"].items(),key=lambda pair:(pair[1]["date"] or "",pair[0])):
        covered+=entry.get("covered",[])
        for e in entry["evidence"]:
            evidence[e["id"]]=e
            if e.get("check"):checks[(sid,e["seq"])]=e["outcome"]
        for o in entry["observations"]:records[o["id"]]=deepcopy(o)
        for change in entry["changes"]:
            old=records.get(change["observation_id"])
            if old:old.update(state=change["state"],resolution_evidence_ids=change["evidence_ids"],resolved_at=change["date"])
        if entry.get("summary") and "summary" not in state.get("manual_fields",[]):
            state["summary"]=entry["summary"]
            summary_inactive=set(entry.get("summary_inactive_ids",[]))
    for oid,correction in doc["corrections"].items():
        if oid in records:records[oid].update(correction,corrected_by="learner")
    for record in records.values():
        if norm(record["text"]) in blocked:record.update(state="superseded",corrected_by="learner")
    state["covered"]=list(dict.fromkeys(s for s in covered if norm(s) not in blocked))
    for field in ("struggles","misconceptions"):
        state[field]=list(dict.fromkeys(o["text"] for o in records.values() if o["kind"]==field and o["state"]=="active"))
    state["quiz_correct"]=int(doc["baseline"].get("quiz_correct",0) or 0)+sum(v=="demonstrated" for v in checks.values())
    state["quiz_wrong"]=int(doc["baseline"].get("quiz_wrong",0) or 0)+sum(v=="needs_practice" for v in checks.values())
    state["summary_stale"]="summary" not in state.get("manual_fields",[]) and any(o["state"]!="active" and o["id"] not in summary_inactive for o in records.values())
    state.update(observations=list(records.values()),evidence=list(evidence.values()),intent=doc["intent"],
                 self_assessment=doc["self_assessment"],memory_v2=doc)
    return state
