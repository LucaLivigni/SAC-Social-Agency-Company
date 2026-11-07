from __future__ import annotations
from . import db

TOOL_REGISTRY={
 "github.read":{"connection":"github","label":"Read GitHub repositories","risk":"low"},
 "instagram.read_profile":{"connection":"instagram","label":"Read Instagram profile","risk":"low"},
 "instagram.read_insights":{"connection":"instagram","label":"Read Instagram insights","risk":"low"},
 "instagram.read_comments":{"connection":"instagram","label":"Read Instagram comments","risk":"low"},
 "instagram.reply_comments":{"connection":"instagram","label":"Reply to Instagram comments","risk":"medium"},
 "instagram.publish":{"connection":"instagram","label":"Publish to Instagram","risk":"high"},
 "linkedin.read_page":{"connection":"linkedin","label":"Read LinkedIn page","risk":"low"},
 "linkedin.read_analytics":{"connection":"linkedin","label":"Read LinkedIn analytics","risk":"low"},
 "linkedin.read_comments":{"connection":"linkedin","label":"Read LinkedIn comments","risk":"low"},
 "linkedin.publish":{"connection":"linkedin","label":"Publish to LinkedIn","risk":"high"},
 "x.read":{"connection":"x","label":"Read X timeline/search","risk":"low"},
 "x.search":{"connection":"x","label":"Search X trends/topics","risk":"low"},
 "x.reply":{"connection":"x","label":"Reply on X","risk":"medium"},
 "x.publish":{"connection":"x","label":"Publish on X","risk":"high"},
 "image.generate":{"connection":"openai","label":"Generate images","risk":"medium"},
 "video.generate":{"connection":"video","label":"Generate videos","risk":"medium"},
 "memory.read_shared":{"connection":None,"label":"Read shared memory","risk":"low"},
 "memory.shared_write":{"connection":None,"label":"Write shared memory","risk":"medium"},
 "messages.internal":{"connection":None,"label":"Message other agents","risk":"low"},
 "requests.create":{"connection":None,"label":"Ask owner for access/decision","risk":"low"},
 "team.create_agent":{"connection":None,"label":"Create agent proposals","risk":"medium"},
 "team.assign_task":{"connection":None,"label":"Assign tasks to agents","risk":"medium"}
}
def connection_status(provider):
    if provider=="openai":
        from .secrets import get_secret
        from .config import settings
        return "connected" if (get_secret("openai-api","OPENAI_API_KEY") or settings.openai_api_key) else "not_connected"
    r=db.connections().get(provider);return r["status"] if r else "not_connected"
def agent_capabilities(agent):
    manifest=(agent or {}).get("manifest",{});tools=list(dict.fromkeys((manifest.get("tools") or [])+(manifest.get("permissions") or [])));out=[]
    for tool in tools:
        meta=TOOL_REGISTRY.get(tool,{"connection":None,"label":tool,"risk":"low"});conn=meta.get("connection");status="available" if not conn else connection_status(conn);out.append({"tool":tool,**meta,"status":status})
    return out
def missing_access(agent):return [x for x in agent_capabilities(agent) if x["connection"] and x["status"]!="connected"]
def ensure_requests_for_missing_access(project_id,agent):
    existing={(r["agent_id"],r.get("payload",{}).get("tool")) for r in db.list_requests(project_id,"pending")};created=[]
    for cap in missing_access(agent):
        key=(agent["id"],cap["tool"])
        if key in existing:continue
        created.append(db.create_request(project_id,agent["id"],"access",f"{agent['name']} needs {cap['label']}",f"Connect {cap['connection']} or grant the required permission before this capability can run.",{"tool":cap["tool"],"connection":cap["connection"],"risk":cap["risk"]}))
    return created
