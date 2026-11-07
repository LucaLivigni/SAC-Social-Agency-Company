from __future__ import annotations
import json,uuid
from . import db
from .providers import ask_json
from .permissions import ensure_requests_for_missing_access

DEFAULT_AGENT_BLUEPRINTS={
"strategist":{"name":"Strategist","title":"Strategy Director","description":"Turns product knowledge into positioning, campaign angles and messaging architecture.","tools":["memory.read_shared","messages.internal","requests.create"],"permissions":["messages.internal"],"knowledge_scopes":["product","marketing_shared"],"kpis":["message clarity","strategic differentiation","campaign coherence"]},
"planner":{"name":"Planner","title":"Editorial Planner","description":"Turns strategy into a coherent cross-channel publishing plan.","tools":["memory.read_shared","messages.internal"],"permissions":["messages.internal"],"knowledge_scopes":["product","marketing_shared","campaigns"],"kpis":["cadence quality","format mix","brief clarity"]},
"instagram":{"name":"Instagram","title":"Instagram Specialist","description":"Owns Instagram-native concepts, copy, formats, community signals and performance learning.","tools":["instagram.read_profile","instagram.read_insights","instagram.read_comments","image.generate","messages.internal","requests.create"],"permissions":["messages.internal"],"knowledge_scopes":["product","marketing_shared","instagram_private"],"kpis":["reach","saves","shares","profile visits","qualified engagement"]},
"linkedin":{"name":"LinkedIn","title":"LinkedIn Specialist","description":"Owns B2B thought leadership, professional content and page-level learning.","tools":["linkedin.read_page","linkedin.read_analytics","linkedin.read_comments","messages.internal","requests.create"],"permissions":["messages.internal"],"knowledge_scopes":["product","marketing_shared","linkedin_private"],"kpis":["qualified impressions","comments","clicks","demo intent"]},
"x":{"name":"X","title":"X Intelligence & Content","description":"Owns concise publishing, real-time topic monitoring and market conversation intelligence.","tools":["x.read","x.search","messages.internal","requests.create"],"permissions":["messages.internal"],"knowledge_scopes":["product","marketing_shared","x_private"],"kpis":["conversation relevance","qualified engagement","trend detection"]},
"creative":{"name":"Creative","title":"Creative Director","description":"Owns art direction and coordinates image/video asset generation.","tools":["image.generate","video.generate","memory.read_shared","messages.internal","requests.create"],"permissions":["messages.internal"],"knowledge_scopes":["product","marketing_shared","brand_visual"],"kpis":["brand consistency","asset quality","format fit"]},
"revy":{"name":"Revy","title":"Quality Lead","description":"Independent reviewer with veto power over unsupported claims, weak copy and brand mismatch.","tools":["memory.read_shared","messages.internal"],"permissions":["messages.internal"],"knowledge_scopes":["product","marketing_shared","verified_facts"],"kpis":["claim accuracy","brand fit","platform fit","quality score"]},
"growth":{"name":"Growth","title":"Growth Analyst","description":"Turns real channel metrics into lessons, experiments and changes to future work.","tools":["instagram.read_insights","linkedin.read_analytics","x.read","memory.shared_write","messages.internal","requests.create"],"permissions":["messages.internal","memory.shared_write"],"knowledge_scopes":["product","marketing_shared","performance"],"kpis":["learning velocity","experiment quality","performance lift"]}
}
def _manifest(specialty,blueprint,custom=None):
    custom=custom or {}
    return {"mission":custom.get("mission") or blueprint["description"],"responsibilities":custom.get("responsibilities") or [blueprint["description"],"Collaborate with the Chief and relevant specialists","Escalate missing access, decisions or unverifiable information"],"knowledge_scopes":custom.get("knowledge_scopes") or blueprint.get("knowledge_scopes",[]),"tools":custom.get("tools") or blueprint.get("tools",[]),"permissions":custom.get("permissions") or blueprint.get("permissions",[]),"kpis":custom.get("kpis") or blueprint.get("kpis",[]),"collaboration_rules":custom.get("collaboration_rules") or ["Use internal messages for handoffs","Do not ask the owner questions already answered in shared memory","Ask the owner only when the missing information is necessary"],"escalation_policy":custom.get("escalation_policy") or ["Request access when a required connection is missing","Escalate brand, legal, pricing or claim uncertainty"],"system_prompt":custom.get("system_prompt") or f"You are SAC's {blueprint['title']}. You are highly specialized in {specialty}. Work as a real member of a coordinated marketing department."}
async def propose_team(project_id):
    p=db.get_project(project_id)
    data=await ask_json("chief","""Design the smallest effective AI marketing team for this product.
Return {"summary":string,"agents":[{"specialty":string,"reason":string,"priority":"core"|"optional","custom_mission":string,"recommended_provider":"openai"|"anthropic"|"local"}]}.
Allowed common specialties include strategist, planner, instagram, linkedin, x, creative, revy, growth.
You may invent a custom specialty when the product genuinely benefits from it, especially for hardware, technical storytelling or community operations.
Do not add a channel specialist unless there is a plausible reason to use that channel.""",json.dumps({"product":p.get("profile") or p.get("analysis"),"hardware_context":p.get("hardware_context","")},ensure_ascii=False))
    db.update_project(project_id,team_proposal=data,status="team_proposal");db.message(project_id,f"chief:{project_id}","chief","owner",f"I designed the recommended team: {data.get('summary','')}",kind="chief");return data
def create_agent_from_spec(project_id,spec,created_by="chief"):
    specialty=(spec.get("specialty") or "specialist").lower().strip().replace(" ","_");blueprint=DEFAULT_AGENT_BLUEPRINTS.get(specialty,{"name":spec.get("name") or specialty.replace("_"," ").title(),"title":spec.get("title") or specialty.replace("_"," ").title(),"description":spec.get("custom_mission") or spec.get("reason") or "Specialist agent","tools":["memory.read_shared","messages.internal","requests.create"],"permissions":["messages.internal"],"knowledge_scopes":["product","marketing_shared"],"kpis":["quality","usefulness"]});aid=f"{project_id[:8]}-{specialty}-{uuid.uuid4().hex[:5]}"
    custom={k:spec.get(k) for k in ["mission","system_prompt","tools","permissions","knowledge_scopes","kpis"] if spec.get(k)}
    if spec.get("custom_mission"):custom["mission"]=spec["custom_mission"]
    a=db.ensure_agent({"id":aid,"project_id":project_id,"name":spec.get("name") or blueprint["name"],"specialty":specialty,"title":spec.get("title") or blueprint["title"],"description":spec.get("reason") or blueprint["description"],"manifest":_manifest(specialty,blueprint,custom),"enabled":1,"created_by":created_by});ensure_requests_for_missing_access(project_id,a);return a
def accept_team(project_id):
    p=db.get_project(project_id);proposal=p.get("team_proposal") or {};created=[];specs=list(proposal.get("agents") or [])
    if not any(x.get("specialty")=="strategist" for x in specs):specs.insert(0,{"specialty":"strategist","reason":"Core strategy owner","priority":"core"})
    if not any(x.get("specialty")=="planner" for x in specs):specs.append({"specialty":"planner","reason":"Editorial coordination","priority":"core"})
    if not any(x.get("specialty")=="revy" for x in specs):specs.append({"specialty":"revy","reason":"Independent quality gate","priority":"core"})
    for spec in specs:
        if spec.get("priority","core")=="optional":continue
        created.append(db.find_agent(project_id,spec.get("specialty","")) or create_agent_from_spec(project_id,spec))
    db.update_project(project_id,status="ready");db.message(project_id,f"chief:{project_id}","chief","owner",f"Team ready. {len(created)} specialist agents are now assigned to this product.",kind="chief");return created
async def build_custom_agent(project_id,brief):
    spec=await ask_json("chief","""You are SAC's Chief Agent and Agent Builder.
Design one specialist agent from the owner's brief.
Return {"name":string,"specialty":string,"title":string,"reason":string,"custom_mission":string,"tools":[string],"permissions":[string],"knowledge_scopes":[string],"kpis":[string],"system_prompt":string,"recommended_provider":"openai"|"anthropic"|"local"}.
Use the minimum permissions needed.""",json.dumps({"brief":brief,"product":db.get_project(project_id).get("profile",{})},ensure_ascii=False))
    agent=create_agent_from_spec(project_id,spec,created_by="chief-agent-builder");db.message(project_id,f"chief:{project_id}","chief","owner",f"I created {agent['name']} ({agent['title']}).",kind="chief");return agent
def org_summary(project_id):
    return [{"id":a["id"],"name":a["name"],"title":a["title"],"specialty":a["specialty"],"status":a.get("state_status","idle"),"task":a.get("state_current_task",""),"model":a.get("model_name"),"manifest":a.get("manifest",{})} for a in db.list_agents(project_id)]
