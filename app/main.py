from __future__ import annotations
import asyncio,os
from contextlib import asynccontextmanager
from fastapi import FastAPI,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel,Field
from .config import settings
from . import db,github_client
from .secrets import get_secret,set_secret
from .workflows import analyze_repository,analyze_manual_project,finalize_project,campaign_job
from .organization import accept_team,build_custom_agent,org_summary
from .permissions import agent_capabilities
from .chat import chat_with_chief,chat_with_agent
from .exporter import export_campaign
class SecretIn(BaseModel):value:str
class ModelIn(BaseModel):name:str;provider:str;model_id:str;base_url:str="";secret:str=""
class AssignIn(BaseModel):agent_id:str;model_profile_id:str
class ProjectIn(BaseModel):name:str;repo_full_name:str="";hardware_context:str=""
class AnswerIn(BaseModel):answer:str
class CampaignIn(BaseModel):project_id:str;goal:str;context:str="";platforms:list[str]=Field(default_factory=lambda:["instagram","x","linkedin"]);posts_per_week:int=4
class ChatIn(BaseModel):project_id:str;message:str
class AgentChatIn(BaseModel):project_id:str;message:str
class BuildAgentIn(BaseModel):project_id:str;brief:str
class ResolveRequestIn(BaseModel):status:str="resolved"
class SocialConnectionIn(BaseModel):account_label:str="";notes:str=""
@asynccontextmanager
async def lifespan(app:FastAPI):
    db.init_db();db.ensure_defaults(settings.default_openai_model);yield
app=FastAPI(title="SAC Studio",version="2.0.0",lifespan=lifespan)
app.mount("/assets",StaticFiles(directory="data/assets"),name="assets");app.mount("/static",StaticFiles(directory="app/static"),name="static")
@app.get("/")
async def home():return FileResponse("app/static/index.html")
@app.get("/api/health")
async def health():return {"ok":True,"app":settings.app_name,"version":"2.0.0"}
@app.get("/api/bootstrap")
async def bootstrap(project_id:str=""):
    gh=await github_client.me()
    if gh:db.connection_set("github","connected",{"login":gh.get("login"),"avatar_url":gh.get("avatar_url")})
    projects=db.list_projects();active=next((p for p in projects if p["id"]==project_id),None) if project_id else None
    if not active:active=next((p for p in projects if p["status"] in {"ready","team_proposal","interview"}),None)
    pid=active["id"] if active else None
    return {"setup":{"openai_connected":bool(get_secret("openai-api","OPENAI_API_KEY") or settings.openai_api_key),"anthropic_connected":bool(get_secret("anthropic-api","ANTHROPIC_API_KEY") or settings.anthropic_api_key),"github_connected":bool(gh),"github_user":gh,"has_project":bool(projects),"active_project":active},"projects":projects,"active_project":active,"agents":db.list_agents(pid) if pid else db.list_agents(),"jobs":db.list_jobs(),"campaigns":db.list_campaigns(pid) if pid else db.list_campaigns(),"models":db.list_models(),"assignments":db.assignments(),"messages":db.list_messages(pid,limit=80) if pid else [],"requests":db.list_requests(pid,"pending") if pid else [],"connections":db.connections(),"organization":org_summary(pid) if pid else []}
@app.post("/api/connections/openai")
async def connect_openai(s:SecretIn):
    from openai import AsyncOpenAI
    try:c=AsyncOpenAI(api_key=s.value);await c.models.list()
    except Exception:raise HTTPException(400,"La API key OpenAI non è valida o non può accedere all'API")
    set_secret("openai-api",s.value);db.connection_set("openai","connected",{});return {"ok":True}
@app.post("/api/connections/anthropic")
async def connect_anthropic(s:SecretIn):
    from anthropic import AsyncAnthropic
    try:c=AsyncAnthropic(api_key=s.value);await c.models.list(limit=1)
    except Exception:raise HTTPException(400,"La API key Anthropic non è valida o non può accedere all'API")
    set_secret("anthropic-api",s.value);db.connection_set("anthropic","connected",{});return {"ok":True}
@app.post("/api/connections/github")
async def connect_github(s:SecretIn):
    try:return await github_client.connect(s.value)
    except Exception as e:raise HTTPException(400,str(e))
@app.delete("/api/connections/github")
async def disconnect_github():github_client.disconnect();return {"ok":True}
@app.post("/api/connections/social/{provider}")
async def mark_social_connection(provider:str,payload:SocialConnectionIn):
    if provider not in {"instagram","linkedin","x","video"}:raise HTTPException(400,"Provider non supportato")
    db.connection_set(provider,"setup_required",payload.model_dump());return {"ok":True,"status":"setup_required"}
@app.get("/api/github/repos")
async def github_repos():
    try:return await github_client.repos()
    except Exception as e:raise HTTPException(400,str(e))
@app.post("/api/models")
async def add_model(m:ModelIn):
    if m.provider not in {"openai","anthropic","openai_compatible"}:raise HTTPException(400,"Provider non supportato")
    secret_name=""
    if m.secret:secret_name=f"provider-{os.urandom(8).hex()}";set_secret(secret_name,m.secret)
    elif m.provider=="openai":secret_name="openai-api"
    elif m.provider=="anthropic":secret_name="anthropic-api"
    return db.create_model(m.name,m.provider,m.model_id,m.base_url,secret_name)
@app.post("/api/models/assign")
async def assign_model(a:AssignIn):
    if not db.row("SELECT id FROM model_profiles WHERE id=?", (a.model_profile_id,)):raise HTTPException(404,"Model profile non trovato")
    if not db.get_agent(a.agent_id):raise HTTPException(404,"Agent non trovato")
    db.assign_model(a.agent_id,a.model_profile_id);return {"ok":True}
@app.post("/api/projects")
async def create_project(p:ProjectIn):
    if not p.repo_full_name and not p.hardware_context.strip():raise HTTPException(400,"Aggiungi una repository oppure una descrizione del prodotto/hardware")
    project=db.create_project(p.name,p.repo_full_name,p.hardware_context);j=db.create_job("product-analysis",project["id"],"Chief is studying the product")
    asyncio.create_task(analyze_repository(project["id"],j["id"]) if p.repo_full_name else analyze_manual_project(project["id"],j["id"]))
    return {"project":project,"job":j}
@app.get("/api/projects/{pid}")
async def project(pid:str):
    p=db.get_project(pid)
    if not p:raise HTTPException(404,"Project not found")
    return p
@app.post("/api/projects/{pid}/answer")
async def answer(pid:str,a:AnswerIn):
    p=db.get_project(pid)
    if not p:raise HTTPException(404,"Project not found")
    answers=list(p.get("answers") or []);questions=p.get("questions") or []
    if len(answers)<len(questions):
        q=questions[len(answers)];answers.append({"question_id":q.get("id",str(len(answers))),"question":q.get("question"),"answer":a.answer});p=db.update_project(pid,answers=answers)
    if len(answers)>=len(questions):await finalize_project(pid);p=db.get_project(pid)
    return p
@app.post("/api/projects/{pid}/team/accept")
async def accept_project_team(pid:str):
    if not db.get_project(pid):raise HTTPException(404,"Project not found")
    team=accept_team(pid);return {"team":team,"project":db.get_project(pid)}
@app.post("/api/agents/build")
async def build_agent(i:BuildAgentIn):
    try:return await build_custom_agent(i.project_id,i.brief)
    except Exception as e:raise HTTPException(400,str(e))
@app.get("/api/agents/{agent_id}")
async def agent_detail(agent_id:str):
    a=db.get_agent(agent_id)
    if not a:raise HTTPException(404,"Agent not found")
    a["capabilities"]=agent_capabilities(a);return a
@app.post("/api/chat/chief")
async def chief_chat(i:ChatIn):
    try:return await chat_with_chief(i.project_id,i.message)
    except Exception as e:raise HTTPException(400,str(e))
@app.post("/api/chat/agents/{agent_id}")
async def agent_chat(agent_id:str,i:AgentChatIn):
    try:return await chat_with_agent(i.project_id,agent_id,i.message)
    except Exception as e:raise HTTPException(400,str(e))
@app.post("/api/requests/{rid}/resolve")
async def resolve_request(rid:str,i:ResolveRequestIn):
    r=db.resolve_request(rid,i.status)
    if not r:raise HTTPException(404,"Request not found")
    return r
@app.post("/api/campaigns")
async def campaign(c:CampaignIn):
    p=db.get_project(c.project_id)
    if not p or p["status"]!="ready":raise HTTPException(400,"Completa discovery e team setup prima di creare una campagna")
    j=db.create_job("campaign",c.project_id,"Chief is assigning the campaign");asyncio.create_task(campaign_job(c.project_id,c.goal,c.context,c.platforms,c.posts_per_week,j["id"]));return j
@app.get("/api/campaigns/{cid}")
async def campaign_detail(cid:str):
    c=db.get_campaign(cid)
    if not c:raise HTTPException(404,"Campaign not found")
    return c
@app.get("/api/campaigns/{cid}/export")
async def campaign_export(cid:str):
    try:p=export_campaign(cid)
    except ValueError as e:raise HTTPException(404,str(e))
    return FileResponse(str(p),media_type="application/zip",filename=f"SAC_{cid[:8]}_READY_TO_PUBLISH.zip")
