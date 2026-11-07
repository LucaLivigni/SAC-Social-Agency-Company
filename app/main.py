from __future__ import annotations
import asyncio, os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from .config import settings
from . import db
from .secrets import get_secret,set_secret,delete_secret
from . import github_client
from .workflows import analyze_repository,finalize_project,campaign_job
from .exporter import export_campaign

class SecretIn(BaseModel): value:str
class ModelIn(BaseModel):
    name:str; provider:str; model_id:str; base_url:str=""; secret:str=""
class AssignIn(BaseModel): agent_id:str; model_profile_id:str
class ImportRepoIn(BaseModel): full_name:str
class AnswerIn(BaseModel): answer:str
class CampaignIn(BaseModel):
    project_id:str; goal:str; context:str=""; platforms:list[str]=["instagram","x","linkedin"]; posts_per_week:int=4

@asynccontextmanager
async def lifespan(app:FastAPI):
    db.init_db();db.ensure_defaults(settings.default_openai_model);yield

app=FastAPI(title="SAC Studio",version="1.0.0",lifespan=lifespan)
app.mount("/assets",StaticFiles(directory="data/assets"),name="assets")
app.mount("/static",StaticFiles(directory="app/static"),name="static")

@app.get("/")
async def home():return FileResponse("app/static/index.html")
@app.get("/api/health")
async def health():return {"ok":True,"app":settings.app_name}

@app.get("/api/bootstrap")
async def bootstrap():
    gh=await github_client.me();projects=db.list_projects();jobs=db.list_jobs();campaigns=db.list_campaigns();models=db.list_models()
    return {"setup":{"openai_connected":bool(get_secret("openai-api","OPENAI_API_KEY") or settings.openai_api_key),"anthropic_connected":bool(get_secret("anthropic-api","ANTHROPIC_API_KEY") or settings.anthropic_api_key),"github_connected":bool(gh),"github_user":gh,"has_project":bool(projects),"ready_project":next((p for p in projects if p["status"]=="ready"),None)},"projects":projects,"agents":db.agent_snapshot(),"jobs":jobs,"campaigns":campaigns,"models":models,"assignments":db.assignments(),"events":db.rows("SELECT * FROM events ORDER BY id DESC LIMIT 60")}

@app.post("/api/connections/openai")
async def connect_openai(s:SecretIn):
    from openai import AsyncOpenAI
    try:
        c=AsyncOpenAI(api_key=s.value);await c.models.list()
    except Exception:raise HTTPException(400,"La API key OpenAI non è valida o non può accedere all API")
    set_secret("openai-api",s.value);return {"ok":True}
@app.delete("/api/connections/openai")
async def disconnect_openai():delete_secret("openai-api");return {"ok":True}

@app.post("/api/connections/anthropic")
async def connect_anthropic(s:SecretIn):
    from anthropic import AsyncAnthropic
    try:
        c=AsyncAnthropic(api_key=s.value);await c.models.list(limit=1)
    except Exception:raise HTTPException(400,"La API key Anthropic non è valida o non può accedere all API")
    set_secret("anthropic-api",s.value);return {"ok":True}

@app.post("/api/connections/github")
async def connect_github(s:SecretIn):
    try:return await github_client.connect(s.value)
    except Exception as e:raise HTTPException(400,str(e))
@app.delete("/api/connections/github")
async def disconnect_github():github_client.disconnect();return {"ok":True}
@app.get("/api/github/repos")
async def github_repos():
    try:return await github_client.repos()
    except Exception as e:raise HTTPException(400,str(e))

@app.get("/api/models")
async def models():return {"profiles":db.list_models(),"assignments":db.assignments()}
@app.post("/api/models")
async def add_model(m:ModelIn):
    if m.provider not in {"openai","anthropic","openai_compatible"}:raise HTTPException(400,"Provider non supportato")
    secret_name=""
    if m.secret:
        secret_name=f"provider-{os.urandom(8).hex()}";set_secret(secret_name,m.secret)
    elif m.provider=="openai":secret_name="openai-api"
    elif m.provider=="anthropic":secret_name="anthropic-api"
    return db.create_model(m.name,m.provider,m.model_id,m.base_url,secret_name)
@app.post("/api/models/assign")
async def assign_model(a:AssignIn):
    if not db.row("SELECT id FROM model_profiles WHERE id=?",(a.model_profile_id,)):raise HTTPException(404,"Model profile non trovato")
    db.assign(a.agent_id,a.model_profile_id);return {"ok":True}

@app.post("/api/projects/import")
async def import_repo(i:ImportRepoIn):
    p=db.create_project(i.full_name.split("/")[-1],i.full_name);j=db.create_job("product-analysis",p["id"],"Product Analyst queued");asyncio.create_task(analyze_repository(p["id"],j["id"]));return {"project":p,"job":j}
@app.get("/api/projects/{pid}")
async def project(pid:str):
    p=db.get_project(pid)
    if not p:raise HTTPException(404,"Project not found")
    return p
@app.post("/api/projects/{pid}/answer")
async def answer(pid:str,a:AnswerIn):
    p=db.get_project(pid)
    if not p:raise HTTPException(404,"Project not found")
    answers=list(p.get("answers") or [])
    if len(answers)>=len(p.get("questions") or []):return await finalize_project(pid)
    q=p["questions"][len(answers)];answers.append({"question_id":q.get("id",str(len(answers))),"question":q.get("question"),"answer":a.answer});p=db.update_project(pid,answers=answers)
    if len(answers)>=len(p.get("questions") or []):p=await finalize_project(pid)
    return p

@app.post("/api/campaigns")
async def campaign(c:CampaignIn):
    p=db.get_project(c.project_id)
    if not p or p["status"]!="ready":raise HTTPException(400,"Completa prima l onboarding del progetto")
    j=db.create_job("campaign",c.project_id,"Campaign queued");asyncio.create_task(campaign_job(c.project_id,c.goal,c.context,c.platforms,c.posts_per_week,j["id"]));return j
@app.get("/api/jobs/{jid}")
async def job(jid:str):
    j=db.get_job(jid)
    if not j:raise HTTPException(404,"Job not found")
    return j

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
