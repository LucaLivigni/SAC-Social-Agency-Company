from __future__ import annotations
import json
from . import db
from .providers import ask_text
from .organization import org_summary
from .permissions import ensure_requests_for_missing_access
def _recent(project_id,actor=None,limit=30):
    msgs=db.list_messages(project_id,limit=limit)
    if actor:msgs=[m for m in msgs if actor in (m["from_actor"],m["to_actor"]) or m["to_actor"]=="owner" or m["from_actor"]=="owner"]
    return [{"from":m["from_actor"],"to":m["to_actor"],"kind":m["kind"],"content":m["content"]} for m in msgs[-limit:]]
async def chat_with_chief(project_id,user_message):
    p=db.get_project(project_id)
    if not p:raise ValueError("Project not found")
    db.message(project_id,f"chief:{project_id}","owner","chief",user_message,kind="user")
    context={"product":p.get("profile") or p.get("analysis") or {},"hardware_context":p.get("hardware_context",""),"team":org_summary(project_id),"pending_requests":db.list_requests(project_id,"pending"),"recent_messages":_recent(project_id,"chief",20)}
    data=await ask_text("chief","""Talk to the owner as the head of the AI marketing department.
You already know the shared product memory, so never ask for information already present.
You may recommend hiring an agent, changing priorities, requesting access, or asking one necessary question.
Keep the reply concise and operational.
If you need to remember an owner preference, put it in memory.
If you need access or an owner decision, populate request with {type,title,detail,payload}.
Otherwise request must be null.""",json.dumps({"context":context,"owner_message":user_message},ensure_ascii=False))
    reply=data.get("reply","");db.message(project_id,f"chief:{project_id}","chief","owner",reply,kind="chief")
    if data.get("memory"):
        for k,v in data["memory"].items():db.memory_set(project_id,"chief","shared",k,v)
    req=data.get("request")
    if req:db.create_request(project_id,"chief",req.get("type","question"),req.get("title","Chief needs you"),req.get("detail",""),req.get("payload") or {})
    return {"reply":reply,"request":req}
async def chat_with_agent(project_id,agent_id,user_message):
    p=db.get_project(project_id);a=db.get_agent(agent_id)
    if not p or not a:raise ValueError("Project or agent not found")
    db.message(project_id,f"agent:{agent_id}","owner",agent_id,user_message,kind="user");memory=db.memory_get(project_id,agent_id,["private","shared"])
    context={"product":p.get("profile") or p.get("analysis") or {},"agent_manifest":a.get("manifest",{}),"private_memory":memory,"recent_messages":_recent(project_id,agent_id,20),"connections":db.connections()}
    data=await ask_text(agent_id,"""You are talking directly with the owner.
Stay inside your specialist role. Do not re-interview the owner about shared product facts.
Ask a focused question only when it improves your specialist work.
If a preference should persist for your future work, put it in memory.
If you need a permission, API, credential or owner decision, populate request.
Otherwise request must be null.""",json.dumps({"context":context,"owner_message":user_message},ensure_ascii=False))
    reply=data.get("reply","");db.message(project_id,f"agent:{agent_id}",agent_id,"owner",reply,kind="agent")
    if data.get("memory"):
        for k,v in data["memory"].items():db.memory_set(project_id,agent_id,"private",k,v)
    req=data.get("request")
    if req:db.create_request(project_id,agent_id,req.get("type","question"),req.get("title",f"{a['name']} needs you"),req.get("detail",""),req.get("payload") or {})
    ensure_requests_for_missing_access(project_id,a);return {"reply":reply,"request":req}
