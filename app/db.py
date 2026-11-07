from __future__ import annotations
import json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from .config import settings

AGENTS = [
    ("strategist","Strategist","Product & campaign strategy","Turns product context into a clear campaign direction."),
    ("planner","Planner","Editorial planning","Builds the content plan, formats and publishing cadence."),
    ("instagram","Instagram","Instagram specialist","Writes Instagram-native content, carousels and reel concepts."),
    ("x","X","X specialist","Creates concise posts and threads for X."),
    ("linkedin","LinkedIn","LinkedIn specialist","Creates B2B and professional content for LinkedIn."),
    ("creative","Creative","Creative director","Defines visual concepts and image prompts."),
    ("revy","Revy","Quality lead","Reviews claims, tone, coherence and platform fit."),
    ("growth","Growth","Growth analyst","Turns real metrics into learning for the next campaign."),
]

def now(): return datetime.now(timezone.utc).isoformat()

def conn():
    p = Path(settings.database_path); p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p); c.row_factory = sqlite3.Row; return c

def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS model_profiles(id TEXT PRIMARY KEY,name TEXT NOT NULL,provider TEXT NOT NULL,model_id TEXT NOT NULL,base_url TEXT NOT NULL DEFAULT '',secret_name TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_assignments(agent_id TEXT PRIMARY KEY,model_profile_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,repo_full_name TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,analysis_json TEXT NOT NULL DEFAULT '{}',questions_json TEXT NOT NULL DEFAULT '[]',answers_json TEXT NOT NULL DEFAULT '[]',profile_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,kind TEXT NOT NULL,project_id TEXT,status TEXT NOT NULL,progress INTEGER NOT NULL DEFAULT 0,message TEXT NOT NULL DEFAULT '',result_id TEXT,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_state(agent_id TEXT PRIMARY KEY,status TEXT NOT NULL DEFAULT 'idle',current_task TEXT NOT NULL DEFAULT '',progress INTEGER NOT NULL DEFAULT 0,job_id TEXT,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,agent_id TEXT NOT NULL,status TEXT NOT NULL,message TEXT NOT NULL,job_id TEXT,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,goal TEXT NOT NULL,context TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,strategy_json TEXT NOT NULL DEFAULT '{}',calendar_json TEXT NOT NULL DEFAULT '[]',posts_json TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS metrics(id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id TEXT,platform TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL);
        """); c.commit()

def rows(sql,args=()):
    with conn() as c: return [dict(x) for x in c.execute(sql,args).fetchall()]

def row(sql,args=()):
    with conn() as c: r=c.execute(sql,args).fetchone()
    return dict(r) if r else None

def execute(sql,args=()):
    with conn() as c: c.execute(sql,args); c.commit()

def ensure_defaults(default_model):
    with conn() as c:
        if c.execute("SELECT COUNT(*) n FROM model_profiles").fetchone()["n"] == 0:
            c.execute("INSERT INTO model_profiles VALUES(?,?,?,?,?,?,?)",("openai-default","OpenAI Default","openai",default_model,"","openai-api",now()))
        for aid,_,_,_ in AGENTS:
            c.execute("INSERT OR IGNORE INTO agent_state VALUES(?,?,?,?,?,?)",(aid,"idle","Waiting for work",0,None,now()))
            c.execute("INSERT OR IGNORE INTO agent_assignments VALUES(?,?)",(aid,"openai-default"))
        c.commit()

def list_models(): return rows("SELECT * FROM model_profiles ORDER BY created_at")
def assignments(): return {x["agent_id"]:x["model_profile_id"] for x in rows("SELECT * FROM agent_assignments")}

def create_model(name,provider,model_id,base_url="",secret_name=""):
    mid=uuid.uuid4().hex
    execute("INSERT INTO model_profiles VALUES(?,?,?,?,?,?,?)",(mid,name,provider,model_id,base_url,secret_name,now()))
    return row("SELECT * FROM model_profiles WHERE id=?",(mid,))

def assign(agent_id,model_id):
    execute("INSERT INTO agent_assignments VALUES(?,?) ON CONFLICT(agent_id) DO UPDATE SET model_profile_id=excluded.model_profile_id",(agent_id,model_id))

def set_agent(agent_id,status,task,progress=0,job_id=None):
    execute("UPDATE agent_state SET status=?,current_task=?,progress=?,job_id=?,updated_at=? WHERE agent_id=?",(status,task,progress,job_id,now(),agent_id))
    execute("INSERT INTO events(agent_id,status,message,job_id,created_at) VALUES(?,?,?,?,?)",(agent_id,status,task,job_id,now()))

def agent_snapshot():
    st={x["agent_id"]:x for x in rows("SELECT * FROM agent_state")}; ass=assignments(); models={x["id"]:x for x in list_models()}; out=[]
    for aid,name,title,desc in AGENTS:
        s=st.get(aid,{}); mid=ass.get(aid,"openai-default"); m=models.get(mid,{})
        out.append({"id":aid,"name":name,"title":title,"description":desc,"status":s.get("status","idle"),"current_task":s.get("current_task","Waiting for work"),"progress":s.get("progress",0),"job_id":s.get("job_id"),"updated_at":s.get("updated_at"),"model_profile_id":mid,"model_name":m.get("name","Default"),"model_id":m.get("model_id","")})
    return out

def create_project(name,repo):
    pid=uuid.uuid4().hex; t=now()
    execute("INSERT INTO projects(id,name,repo_full_name,status,created_at,updated_at) VALUES(?,?,?,?,?,?)",(pid,name,repo,"analyzing",t,t))
    return get_project(pid)

def get_project(pid):
    r=row("SELECT * FROM projects WHERE id=?",(pid,))
    if not r:return None
    for col,key,default in [("analysis_json","analysis",{}),("questions_json","questions",[]),("answers_json","answers",[]),("profile_json","profile",{})]:
        try:r[key]=json.loads(r[col] or json.dumps(default))
        except:r[key]=default
    return r

def list_projects(): return [get_project(x["id"]) for x in rows("SELECT id FROM projects ORDER BY updated_at DESC")]

def update_project(pid,**fields):
    mapping={"analysis":"analysis_json","questions":"questions_json","answers":"answers_json","profile":"profile_json"}; pairs=[]; vals=[]
    for k,v in fields.items():
        pairs.append(f"{mapping.get(k,k)}=?"); vals.append(json.dumps(v,ensure_ascii=False) if k in mapping else v)
    pairs.append("updated_at=?"); vals.extend([now(),pid]); execute(f"UPDATE projects SET {','.join(pairs)} WHERE id=?",tuple(vals)); return get_project(pid)

def create_job(kind,project_id=None,message="Queued"):
    jid=uuid.uuid4().hex; t=now(); execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)",(jid,kind,project_id,"queued",0,message,None,None,t,t)); return get_job(jid)
def get_job(jid): return row("SELECT * FROM jobs WHERE id=?",(jid,))
def update_job(jid,**fields):
    pairs=[]; vals=[]
    for k,v in fields.items(): pairs.append(f"{k}=?"); vals.append(v)
    pairs.append("updated_at=?"); vals.extend([now(),jid]); execute(f"UPDATE jobs SET {','.join(pairs)} WHERE id=?",tuple(vals)); return get_job(jid)
def list_jobs(limit=25): return rows("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",(limit,))

def create_campaign(project_id,goal,context):
    cid=uuid.uuid4().hex; execute("INSERT INTO campaigns(id,project_id,goal,context,status,created_at) VALUES(?,?,?,?,?,?)",(cid,project_id,goal,context,"generating",now())); return get_campaign(cid)
def get_campaign(cid):
    r=row("SELECT * FROM campaigns WHERE id=?",(cid,))
    if not r:return None
    for col,key,default in [("strategy_json","strategy",{}),("calendar_json","calendar",[]),("posts_json","posts",[])]:
        try:r[key]=json.loads(r[col] or json.dumps(default))
        except:r[key]=default
    return r
def list_campaigns(project_id=None):
    q="SELECT id FROM campaigns"; args=()
    if project_id:q+=" WHERE project_id=?";args=(project_id,)
    q+=" ORDER BY created_at DESC"; return [get_campaign(x["id"]) for x in rows(q,args)]
def update_campaign(cid,**fields):
    mapping={"strategy":"strategy_json","calendar":"calendar_json","posts":"posts_json"};pairs=[];vals=[]
    for k,v in fields.items():pairs.append(f"{mapping.get(k,k)}=?");vals.append(json.dumps(v,ensure_ascii=False) if k in mapping else v)
    vals.append(cid);execute(f"UPDATE campaigns SET {','.join(pairs)} WHERE id=?",tuple(vals));return get_campaign(cid)
