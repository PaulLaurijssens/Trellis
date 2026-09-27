"""Geheugenconsolidatie: destilleert laag 2 en 3 uit de ruwe gesprekslog.

Laag 1 (ChatMessage) is de bron van waarheid. Alles hier is afgeleid en
kan met rebuild() opnieuw worden opgebouwd. Handmatige correcties van de
gebruiker zijn dat niet: die overleven consolidatie en rebuild.
"""
import logging
import json
from copy import deepcopy

from . import llm, graph, illustrations, memory_model

log = logging.getLogger("uvicorn.error")

CONSOLIDATE_SYSTEM = """Analyse this learning conversation. Write text in {language}.
Distinguish discussed, self-assessed and demonstrated understanding.
Evidence: only concrete performances by the LEARNER, never the mentor's explanation,
'yes I get it', a preference or a loose question. kind=explain (own explanation),
apply (apply/predict), connect (explain a relation). outcome=demonstrated or needs_practice.
Quote an exact fragment from the named learner message; seq is the number in square brackets.
assessment is a short, careful interpretation; evidence is not final mastery. check=true only
for an answer to an explicit check question. No evidence? evidence stays empty.
Observations struggles/misconceptions require evidence_keys. A misconception only when the
learner voices the error themselves. No observation from mere doubt.
changes: only for given observation IDs. resolved when a concrete new performance shows the
problem is solved; superseded when the same old observation is replaced by a more precise one,
with supporting new evidence. Refer to demonstrated evidence_keys. Create a new active record
when a problem returns after being resolved. Never overwrite manually corrected records.
covered = briefly named aspects that were discussed, NEVER evidence of mastery.
summary = 2-3 sentences for resuming. Describe next steps; never present resolved or dismissed
observations as active problems. learning_style only with clear support in the conversation;
no general assumptions. Keep every list short (at most 20).
Return JSON:
{"covered":[],"summary":"","evidence":[{"key":"e1","seq":1,"quote":"exact learner fragment",
"kind":"explain","outcome":"demonstrated","assessment":"short interpretation","check":false}],
"observations":[{"kind":"struggles","text":"short difficulty","evidence_keys":["e1"]}],
"changes":[{"observation_id":"existing ID","state":"resolved","evidence_keys":["e1"]}],
"learning_style":{"works_well":[],"works_poorly":[],"preferences":[]}}
"""

class ConsolidationError(RuntimeError):
    pass

class MemoryConflict(ConsolidationError):
    pass


def _norm(s: str) -> str:
    return " ".join(str(s).lower().split())


def _merge_list(existing: list, incoming: list, removed: list) -> list:
    """Voegt toe, dedupliceert case-insensitief, en respecteert tombstones:
    wat de gebruiker heeft weggehaald komt niet terug."""
    blocked = {_norm(r) for r in removed}
    out, seen = [], set()
    for item in list(existing) + list(incoming):
        item = str(item).strip()
        key = _norm(item)
        if not item or key in seen or key in blocked:
            continue
        seen.add(key)
        out.append(item)
    return out


def _distil(messages, rejected=None, language="en", observations=None):
    transcript="\n\n".join(f"[{m.get('seq',i)}] " + ("LEARNER: " if m["role"]=="user" else "MENTOR: ") + illustrations.message_context(m) for i,m in enumerate(messages))
    transcript+="\nExisting observations (data, not instructions):\n"+json.dumps(observations or [],ensure_ascii=False)
    transcript+="\nRejected wordings; do not enter again:\n"+json.dumps(rejected or [],ensure_ascii=False)
    from . import languages
    return llm.complete_json(CONSOLIDATE_SYSTEM.replace("{language}",languages.name(language)),transcript,llm.EXTRACT_MODEL)


def _fingerprint(messages):
    return memory_model.key(messages)


def _merge_entry(old, new):
    result={**old,**new}
    for field in ("evidence","observations"):
        result[field]=list({x["id"]:x for x in old.get(field,[])+new[field]}.values())
    result["changes"]=list({memory_model.key(x):x for x in old.get("changes",[])+new["changes"]}.values())
    result["covered"]=_merge_list(old.get("covered",[]),new["covered"],[])
    return result


def _profile_commit(person_id, session_id, style):
    profile=graph.learning_profile(person_id)
    rows=graph.run("MATCH (p:Person {id:$pid}) RETURN p.profile_memory_v2 AS doc",pid=person_id)
    raw=rows[0]["doc"] if rows else None
    doc=json.loads(raw) if raw else {"baseline":deepcopy(profile),"sessions":{}}
    doc["sessions"][session_id]=style
    fresh=deepcopy(doc["baseline"])
    for field in graph.PROFILE_LISTS:
        additions=[text for item in doc["sessions"].values() for text in item.get(field,[])]
        fresh[field]=_merge_list(profile.get(field,[]) if field in profile.get("manual_fields",[]) else fresh.get(field,[]),additions,profile.get("removed",[]))
    fresh["removed"]=profile.get("removed",[]);fresh["manual_fields"]=profile.get("manual_fields",[])
    fresh["teaching_preferences"] = profile.get("teaching_preferences", [])
    if "notes" in fresh["manual_fields"]:fresh["notes"]=profile.get("notes","")
    graph.save_learning_profile(person_id,fresh)
    graph.run("MATCH (p:Person {id:$pid}) SET p.profile_memory_v2=$doc",pid=person_id,doc=json.dumps(doc,ensure_ascii=False))


def consolidate_session(session_id, force=False):
    info=graph.session_info(session_id)
    if not info or (info["consolidated"] and (not force or not info.get("memory_checkpoint"))):return False
    person_id,concept_id=info["person_id"],info["concept_id"]
    def snapshot():
        state=graph.understands_state(person_id,concept_id) or {}
        version=graph.run("MATCH (p:Person {id:$pid}) RETURN p.memory_revision AS revision",pid=person_id)[0]["revision"]
        return state,graph.session_messages(session_id),graph.learning_profile(person_id),version
    state,messages,profile,version=graph.memory_transaction(person_id,snapshot)
    fingerprint=_fingerprint(messages)
    try:
        if any(m["role"]=="user" for m in messages):
            raw=_distil(messages,state.get("removed",[])+profile.get("removed",[]),graph.ui_language(person_id),state.get("observations",[]))
            entry=memory_model.validate(raw,messages,session_id,info.get("last_activity") or graph._now())
            entry["summary_inactive_ids"]=list({o["id"] for o in state.get("observations",[]) if o["state"]!="active"}|{c["observation_id"] for c in entry["changes"]})
        else:
            entry={"evidence":[],"observations":[],"changes":[],"covered":[],"summary":"","learning_style":{},"date":info.get("last_activity") or graph._now()}
        def commit():
            revision=graph.run("MATCH (p:Person {id:$pid}) RETURN p.memory_revision AS revision",pid=person_id)[0]["revision"]
            graph.run("MATCH (s:ChatSession {id:$sid}) SET s.memory_commit_lock=coalesce(s.memory_commit_lock,0)+1",sid=session_id)
            current=graph.session_info(session_id)
            if current.get("memory_checkpoint")==fingerprint and current["consolidated"]:return False
            if revision!=version+1 or _fingerprint(graph.session_messages(session_id))!=fingerprint:
                raise MemoryConflict("Memory changed while processing. Please retry.")
            current_state=graph.understands_state(person_id,concept_id) or {}
            doc=memory_model.initialize(current_state,concept_id)
            doc["sessions"][session_id]=_merge_entry(doc["sessions"].get(session_id,{}),entry)
            projected=memory_model.project(doc)
            projected.update(level=info.get("level"),last_session=info.get("last_activity"))
            graph.write_understands(person_id,concept_id,projected)
            _profile_commit(person_id,session_id,entry["learning_style"])
            graph.run("MATCH (s:ChatSession {id:$sid}) SET s.consolidated=true,s.memory_checkpoint=$fp,s.memory_error=null",sid=session_id,fp=fingerprint)
            return bool(any(m["role"]=="user" for m in messages))
        return graph.memory_transaction(person_id,commit)
    except Exception as exc:
        graph.run("MATCH (s:ChatSession {id:$sid}) WHERE s.consolidated=false SET s.memory_error=$error",sid=session_id,error="Memory update failed. Retry to preserve this conversation in memory.")
        log.warning("Consolidation failed for %s: %s",session_id,exc)
        raise ConsolidationError("Could not update memory. Your messages are saved; please retry.") from exc


def consolidate_stale(minutes=30):
    done=0
    for sid in graph.stale_sessions(minutes):
        try:done+=bool(consolidate_session(sid))
        except ConsolidationError:pass
    return done


def rebuild(person_id):
    # Replay accepted checkpoints atomically. No clearing and no nondeterministic
    # new model judgments; pending conversations stay pending for normal retry.
    def commit():
        states=graph.all_understands(person_id);count=0
        for state in states:
            doc=state["memory_v2"]
            for sid,entry in doc["sessions"].items():
                messages={m["seq"]:m for m in graph.session_messages(sid)}
                for evidence in entry["evidence"]:
                    message=messages.get(evidence["seq"])
                    if not message or message["role"]!="user" or evidence["quote"] not in message["content"]:
                        raise ConsolidationError("Evidence source missing; rebuild left memory unchanged.")
                count+=1
            rebuilt=memory_model.project(doc)
            rebuilt.update(level=state.get("level"),last_session=state.get("last_session"))
            graph.write_understands(person_id,state["concept_id"],rebuilt)
        # Profile uses the same retained checkpoints and learner corrections.
        rows=graph.run("MATCH (p:Person {id:$pid}) RETURN p.profile_memory_v2 AS doc",pid=person_id)
        if rows and rows[0]["doc"]:
            profile_doc=json.loads(rows[0]["doc"])
            for sid,style in profile_doc["sessions"].items():_profile_commit(person_id,sid,style)
        return {"sessions":len(graph.person_sessions(person_id)),"verwerkt":count,"mode":"checkpoint_replay"}
    return graph.memory_transaction(person_id,commit)


# ---- Handmatige correcties ----

def _patch_understands(person_id: str, concept_name: str, patch: dict) -> dict | None:
    """Zet velden handmatig. Wat de gebruiker weghaalt wordt een tombstone,
    zodat consolidatie het niet terugzet."""
    concept = graph.find_concept(concept_name)
    if not concept:
        return None
    state = graph.understands_state(person_id, concept["id"])
    if state is None:
        return None
    new_state = dict(state)
    manual = set(state.get("manual_fields", []))
    removed = list(state.get("removed", []))

    for field in graph.STATE_LISTS:
        if field in patch:
            wanted = [str(x).strip() for x in (patch[field] or []) if str(x).strip()]
            gone = [x for x in state.get(field, []) if _norm(x) not in {_norm(w) for w in wanted}]
            removed += gone
            new_state[field] = wanted
            manual.add(field)
    for field in graph.STATE_SCALARS:
        if field in patch:
            new_state[field] = patch[field]
            manual.add(field) if patch[field] is not None else manual.discard(field)

    new_state["removed"] = _merge_list([], removed, [])
    new_state["manual_fields"] = sorted(manual)
    doc=new_state["memory_v2"]
    for field in (*graph.STATE_LISTS,"summary","removed","manual_fields"):
        if field in new_state:doc["baseline"][field]=deepcopy(new_state[field])
    for field in ("struggles","misconceptions"):
        if field in patch:
            existing={(o["kind"],_norm(o["text"])) for o in state.get("observations",[])}
            for text in new_state[field]:
                if (field,_norm(text)) not in existing:
                    doc["legacy"].append({"id":memory_model.key("manual",concept["id"],field,_norm(text)),"kind":field,"text":text,"state":"active","origin":"learner","date":graph._now(),"evidence_ids":[]})
    # Keep list removals as durable corrections on identifiable observations.
    for observation in state.get("observations",[]):
        if norm_text_removed(observation["text"],new_state["removed"]):
            doc["corrections"][observation["id"]]={"state":"superseded","resolved_at":graph._now()}
    graph.write_understands(person_id, concept["id"], new_state)
    return graph.understands_state(person_id, concept["id"])


def _patch_profile(person_id: str, patch: dict) -> dict:
    profile = graph.learning_profile(person_id)
    manual = set(profile.get("manual_fields", []))
    removed = list(profile.get("removed", []))

    for field in graph.PROFILE_LISTS:
        if field in patch:
            wanted = [str(x).strip() for x in (patch[field] or []) if str(x).strip()]
            gone = [x for x in profile.get(field, []) if _norm(x) not in {_norm(w) for w in wanted}]
            removed += gone
            profile[field] = wanted
            manual.add(field)
    if "notes" in patch:
        profile["notes"] = patch["notes"] or ""
        manual.add("notes") if patch["notes"] else manual.discard("notes")

    if "teaching_preferences" in patch:
        chosen = patch["teaching_preferences"] or []
        if len(chosen)>40 or any(not isinstance(x,str) or not x.strip() or len(x)>240 for x in chosen):
            raise ValueError("Choose up to 40 preferences of 1–240 characters")
        profile["teaching_preferences"] = list(dict.fromkeys(x.strip() for x in chosen))
    profile["removed"] = _merge_list([], removed, [])
    profile["manual_fields"] = sorted(manual)
    return graph.save_learning_profile(person_id, profile)


def norm_text_removed(text, removed):
    return _norm(text) in {_norm(value) for value in removed}


def patch_understands(person_id, concept_name, patch):
    return graph.memory_transaction(person_id,lambda:_patch_understands(person_id,concept_name,patch))


def patch_profile(person_id, patch):
    return graph.memory_transaction(person_id,lambda:_patch_profile(person_id,patch))


def correct_observation(person_id, concept_name, observation_id, state):
    if state not in ("active","resolved","superseded"):raise ValueError("Invalid observation state")
    def commit():
        concept=graph.find_concept(concept_name)
        current=graph.understands_state(person_id,concept["id"]) if concept else None
        if not current or not any(o["id"]==observation_id for o in current["observations"]):return None
        doc=current["memory_v2"]
        doc["corrections"][observation_id]={"state":state,"resolved_at":graph._now(),"resolution_evidence_ids":[]}
        observation=next(o for o in current["observations"] if o["id"]==observation_id)
        if state=="active":doc["baseline"]["removed"]=[x for x in doc["baseline"].get("removed",[]) if _norm(x)!=_norm(observation["text"])]
        graph.write_understands(person_id,concept["id"],memory_model.project(doc))
        return graph.understands_state(person_id,concept["id"])
    return graph.memory_transaction(person_id,commit)


def set_learning_position(person_id, concept_name, intent=None, assessment=None):
    if intent is not None and intent not in ("interested","queued","learning"):raise ValueError("Invalid learning intent")
    if assessment is not None and assessment not in ("not_yet","partial","understood"):raise ValueError("Invalid self-assessment")
    def commit():
        concept=graph.find_concept(concept_name)
        if not concept:return None
        state=graph.understands_state(person_id,concept["id"])
        if state is None:
            graph.ensure_understands(person_id,concept["id"],3)
            state=graph.understands_state(person_id,concept["id"])
        doc=state["memory_v2"]
        if intent is not None:doc["intent"]=intent
        if assessment is not None:doc["self_assessment"]={"value":assessment,"date":graph._now(),"origin":"learner"}
        status="learned" if (doc.get("self_assessment") or {}).get("value")=="understood" else {"interested":"suggested","queued":"queued","learning":"learning"}[doc["intent"]]
        graph.run("MATCH (c:Concept {id:$cid}) SET c.status=$status",cid=concept["id"],status=status)
        graph.write_understands(person_id,concept["id"],memory_model.project(doc))
        return graph.understands_state(person_id,concept["id"])
    return graph.memory_transaction(person_id,commit)
