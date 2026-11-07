from __future__ import annotations
import json, sqlite3, uuid
from datetime import datetime, timezone
from pathlib import Path
from .config import settings

CORE_CHIEF = {
    "id": "chief",
    "project_id": None,
    "name": "Chief",
    "specialty": "chief",
    "title": "Chief Marketing AI",
    "description": "Primary interface with the owner. Designs the team, coordinates work and escalates decisions.",
    "enabled": 1,
    "created_by": "system",
    "manifest": {
        "mission": "Understand the company and product, design the right marketing organization, coordinate specialists and involve the owner only when needed.",
        "responsibilities": [
            "Own marketing strategy and priorities",
            "Design and hire specialist agents",
            "Coordinate inter-agent work",
            "Review blockers and access needs",
            "Escalate decisions to the owner"
        ],
        "knowledge_scopes": ["company", "all_projects", "marketing_shared", "team_activity"],
        "tools": ["team.manage", "memory.read_shared", "messages.send", "requests.create", "github.read"],
        "permissions": ["team.create_agent", "team.assign_task", "messages.internal", "memory.shared_write"],
        "kpis": ["clarity", "team throughput", "quality", "owner interruptions kept necessary"],
        "collaboration_rules": ["Route specialist questions through the right agent", "Never hide blockers from the owner"],
        "escalation_policy": ["Ask the owner for missing commercial decisions, credentials, approvals or unverifiable claims"],
        "system_prompt": "You are the Chief Marketing AI. Behave like a senior CMO managing a specialist AI team."
    }
}

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

def conn():
    p = Path(settings.database_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    return c

def _cols(c, table):
    return {r["name"] for r in c.execute(f"PRAGMA table_info({table})").fetchall()}

def _add_col(c, table, col, ddl):
    if col not in _cols(c, table):
        c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")

def init_db():
    with conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS model_profiles(id TEXT PRIMARY KEY,name TEXT NOT NULL,provider TEXT NOT NULL,model_id TEXT NOT NULL,base_url TEXT NOT NULL DEFAULT '',secret_name TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_assignments(agent_id TEXT PRIMARY KEY,model_profile_id TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL,repo_full_name TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,analysis_json TEXT NOT NULL DEFAULT '{}',questions_json TEXT NOT NULL DEFAULT '[]',answers_json TEXT NOT NULL DEFAULT '[]',profile_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,kind TEXT NOT NULL,project_id TEXT,status TEXT NOT NULL,progress INTEGER NOT NULL DEFAULT 0,message TEXT NOT NULL DEFAULT '',result_id TEXT,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS campaigns(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,goal TEXT NOT NULL,context TEXT NOT NULL DEFAULT '',status TEXT NOT NULL,strategy_json TEXT NOT NULL DEFAULT '{}',calendar_json TEXT NOT NULL DEFAULT '[]',posts_json TEXT NOT NULL DEFAULT '[]',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS metrics(id INTEGER PRIMARY KEY AUTOINCREMENT,campaign_id TEXT,platform TEXT NOT NULL,payload_json TEXT NOT NULL,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_definitions(id TEXT PRIMARY KEY,project_id TEXT,name TEXT NOT NULL,specialty TEXT NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',manifest_json TEXT NOT NULL DEFAULT '{}',enabled INTEGER NOT NULL DEFAULT 1,created_by TEXT NOT NULL DEFAULT 'chief',created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_state(agent_id TEXT PRIMARY KEY,status TEXT NOT NULL DEFAULT 'idle',current_task TEXT NOT NULL DEFAULT '',progress INTEGER NOT NULL DEFAULT 0,job_id TEXT,updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_messages(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT,thread_id TEXT NOT NULL,from_actor TEXT NOT NULL,to_actor TEXT NOT NULL,kind TEXT NOT NULL DEFAULT 'internal',content TEXT NOT NULL,metadata_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_requests(id TEXT PRIMARY KEY,project_id TEXT,agent_id TEXT NOT NULL,request_type TEXT NOT NULL,title TEXT NOT NULL,detail TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'pending',payload_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL,resolved_at TEXT);
        CREATE TABLE IF NOT EXISTS agent_memory(id INTEGER PRIMARY KEY AUTOINCREMENT,project_id TEXT,agent_id TEXT NOT NULL,scope TEXT NOT NULL,key TEXT NOT NULL,value_json TEXT NOT NULL,updated_at TEXT NOT NULL,UNIQUE(project_id,agent_id,scope,key));
        CREATE TABLE IF NOT EXISTS connections(provider TEXT PRIMARY KEY,status TEXT NOT NULL DEFAULT 'not_connected',config_json TEXT NOT NULL DEFAULT '{}',updated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS product_sources(id TEXT PRIMARY KEY,project_id TEXT NOT NULL,source_type TEXT NOT NULL,label TEXT NOT NULL,content TEXT NOT NULL DEFAULT '',metadata_json TEXT NOT NULL DEFAULT '{}',created_at TEXT NOT NULL);
        """)
        _add_col(c, "projects", "team_proposal_json", "TEXT NOT NULL DEFAULT '{}'")
        _add_col(c, "projects", "hardware_context", "TEXT NOT NULL DEFAULT ''")
        _add_col(c, "projects", "chief_memory_json", "TEXT NOT NULL DEFAULT '{}'")
        c.commit()

def rows(sql, args=()):
    with conn() as c:
        return [dict(x) for x in c.execute(sql, args).fetchall()]

def row(sql, args=()):
    with conn() as c:
        r = c.execute(sql, args).fetchone()
    return dict(r) if r else None

def execute(sql, args=()):
    with conn() as c:
        c.execute(sql, args); c.commit()

def setting_get(key, default=""):
    r = row("SELECT value FROM settings WHERE key=?", (key,))
    return r["value"] if r else default

def setting_set(key, value):
    execute("""INSERT INTO settings(key,value) VALUES(?,?)
               ON CONFLICT(key) DO UPDATE SET value=excluded.value""", (key, value))

def ensure_defaults(default_model: str):
    if not row("SELECT id FROM model_profiles LIMIT 1"):
        execute("INSERT INTO model_profiles VALUES(?,?,?,?,?,?,?)",
                ("openai-default","OpenAI Default","openai",default_model,"","openai-api",now()))
    ensure_agent(CORE_CHIEF)
    if not row("SELECT agent_id FROM agent_assignments WHERE agent_id='chief'"):
        assign_model("chief", "openai-default")
    for provider in ["github","instagram","linkedin","x"]:
        if not row("SELECT provider FROM connections WHERE provider=?", (provider,)):
            execute("INSERT INTO connections(provider,status,config_json,updated_at) VALUES(?,?,?,?)",
                    (provider, "not_connected", "{}", now()))

def create_model(name, provider, model_id, base_url="", secret_name=""):
    mid = uuid.uuid4().hex
    execute("INSERT INTO model_profiles VALUES(?,?,?,?,?,?,?)",
            (mid,name,provider,model_id,base_url,secret_name,now()))
    return row("SELECT * FROM model_profiles WHERE id=?", (mid,))

def list_models(): return rows("SELECT * FROM model_profiles ORDER BY created_at")
def assignments(): return {x["agent_id"]: x["model_profile_id"] for x in rows("SELECT * FROM agent_assignments")}

def assign_model(agent_id, model_id):
    execute("""INSERT INTO agent_assignments(agent_id,model_profile_id) VALUES(?,?)
               ON CONFLICT(agent_id) DO UPDATE SET model_profile_id=excluded.model_profile_id""",(agent_id,model_id))

def ensure_agent(a: dict):
    manifest = json.dumps(a.get("manifest", {}), ensure_ascii=False)
    execute("""INSERT INTO agent_definitions(id,project_id,name,specialty,title,description,manifest_json,enabled,created_by,created_at,updated_at)
    VALUES(?,?,?,?,?,?,?,?,?,?,?)
    ON CONFLICT(id) DO UPDATE SET project_id=excluded.project_id,name=excluded.name,specialty=excluded.specialty,title=excluded.title,description=excluded.description,manifest_json=excluded.manifest_json,enabled=excluded.enabled,updated_at=excluded.updated_at""",
    (a["id"],a.get("project_id"),a["name"],a["specialty"],a["title"],a.get("description",""),manifest,int(a.get("enabled",1)),a.get("created_by","chief"),a.get("created_at",now()),now()))
    if not row("SELECT agent_id FROM agent_state WHERE agent_id=?", (a["id"],)):
        execute("INSERT INTO agent_state VALUES(?,?,?,?,?,?)",(a["id"],"idle","Waiting for work",0,None,now()))
    if not row("SELECT agent_id FROM agent_assignments WHERE agent_id=?", (a["id"],)):
        assign_model(a["id"], "openai-default")
    return get_agent(a["id"])

def get_agent(agent_id):
    a=row("SELECT * FROM agent_definitions WHERE id=?", (agent_id,))
    if not a:return None
    try:a["manifest"]=json.loads(a["manifest_json"] or "{}")
    except:a["manifest"]={}
    s=row("SELECT * FROM agent_state WHERE agent_id=?", (agent_id,)) or {}
    a.update({f"state_{k}":v for k,v in s.items() if k!="agent_id"})
    mid=assignments().get(agent_id,"openai-default");m=row("SELECT * FROM model_profiles WHERE id=?", (mid,)) or {}
    a["model_profile_id"]=mid;a["model_name"]=m.get("name","Default");a["model_id"]=m.get("model_id","")
    return a

def list_agents(project_id=None, include_global=True):
    if project_id and include_global:
        ids=rows("""SELECT id FROM agent_definitions WHERE enabled=1 AND (project_id=? OR project_id IS NULL)
                    ORDER BY CASE WHEN id='chief' THEN 0 ELSE 1 END, created_at""",(project_id,))
    elif project_id:
        ids=rows("SELECT id FROM agent_definitions WHERE enabled=1 AND project_id=? ORDER BY created_at",(project_id,))
    else:
        ids=rows("""SELECT id FROM agent_definitions WHERE enabled=1
                    ORDER BY CASE WHEN id='chief' THEN 0 ELSE 1 END, created_at""")
    return [get_agent(x["id"]) for x in ids]

def find_agent(project_id, specialty):
    r=row("""SELECT id FROM agent_definitions WHERE enabled=1 AND specialty=? AND (project_id=? OR project_id IS NULL)
             ORDER BY CASE WHEN project_id=? THEN 0 ELSE 1 END LIMIT 1""",(specialty,project_id,project_id))
    return get_agent(r["id"]) if r else None

def set_agent(agent_id,status,task,progress=0,job_id=None):
    execute("""INSERT INTO agent_state(agent_id,status,current_task,progress,job_id,updated_at) VALUES(?,?,?,?,?,?)
               ON CONFLICT(agent_id) DO UPDATE SET status=excluded.status,current_task=excluded.current_task,progress=excluded.progress,job_id=excluded.job_id,updated_at=excluded.updated_at""",
            (agent_id,status,task,progress,job_id,now()))

def message(project_id,thread_id,from_actor,to_actor,content,kind="internal",metadata=None):
    execute("INSERT INTO agent_messages(project_id,thread_id,from_actor,to_actor,kind,content,metadata_json,created_at) VALUES(?,?,?,?,?,?,?,?)",
            (project_id,thread_id,from_actor,to_actor,kind,content,json.dumps(metadata or {},ensure_ascii=False),now()))

def list_messages(project_id=None,thread_id=None,limit=100):
    q="SELECT * FROM agent_messages WHERE 1=1";args=[]
    if project_id:q+=" AND project_id=?";args.append(project_id)
    if thread_id:q+=" AND thread_id=?";args.append(thread_id)
    q+=" ORDER BY id DESC LIMIT ?";args.append(limit)
    data=rows(q,tuple(args))
    for x in data:
        try:x["metadata"]=json.loads(x["metadata_json"] or "{}")
        except:x["metadata"]={}
    return list(reversed(data))

def create_request(project_id,agent_id,request_type,title,detail="",payload=None):
    rid=uuid.uuid4().hex
    execute("INSERT INTO agent_requests VALUES(?,?,?,?,?,?,?,?,?)",(rid,project_id,agent_id,request_type,title,detail,"pending",json.dumps(payload or {},ensure_ascii=False),now(),None))
    set_agent(agent_id,"blocked",title,0,None)
    return get_request(rid)

def get_request(rid):
    r=row("SELECT * FROM agent_requests WHERE id=?", (rid,))
    if not r:return None
    try:r["payload"]=json.loads(r["payload_json"] or "{}")
    except:r["payload"]={}
    return r

def list_requests(project_id=None,status=None):
    q="SELECT id FROM agent_requests WHERE 1=1";args=[]
    if project_id:q+=" AND project_id=?";args.append(project_id)
    if status:q+=" AND status=?";args.append(status)
    q+=" ORDER BY created_at DESC"
    return [get_request(x["id"]) for x in rows(q,tuple(args))]

def resolve_request(rid,status="resolved"):
    r=get_request(rid)
    if not r:return None
    execute("UPDATE agent_requests SET status=?,resolved_at=? WHERE id=?",(status,now(),rid))
    set_agent(r["agent_id"],"idle","Access/decision request resolved",0,None)
    return get_request(rid)

def memory_set(project_id,agent_id,scope,key,value):
    execute("""INSERT INTO agent_memory(project_id,agent_id,scope,key,value_json,updated_at) VALUES(?,?,?,?,?,?)
               ON CONFLICT(project_id,agent_id,scope,key) DO UPDATE SET value_json=excluded.value_json,updated_at=excluded.updated_at""",
            (project_id,agent_id,scope,key,json.dumps(value,ensure_ascii=False),now()))

def memory_get(project_id,agent_id=None,scopes=None):
    q="SELECT * FROM agent_memory WHERE project_id=?";args=[project_id]
    if agent_id is not None:q+=" AND agent_id=?";args.append(agent_id)
    if scopes:q+=" AND scope IN (%s)" % ",".join("?"*len(scopes));args.extend(scopes)
    out={}
    for r in rows(q,tuple(args)):
        try:v=json.loads(r["value_json"])
        except:v=r["value_json"]
        out[f'{r["scope"]}:{r["key"]}']=v
    return out

def connection_set(provider,status,config=None):
    execute("""INSERT INTO connections(provider,status,config_json,updated_at) VALUES(?,?,?,?)
               ON CONFLICT(provider) DO UPDATE SET status=excluded.status,config_json=excluded.config_json,updated_at=excluded.updated_at""",
            (provider,status,json.dumps(config or {},ensure_ascii=False),now()))

def connections():
    out={}
    for r in rows("SELECT * FROM connections ORDER BY provider"):
        try:r["config"]=json.loads(r["config_json"] or "{}")
        except:r["config"]={}
        out[r["provider"]]=r
    return out

def create_project(name,repo="",hardware_context=""):
    pid=uuid.uuid4().hex;t=now()
    execute("INSERT INTO projects(id,name,repo_full_name,status,created_at,updated_at,hardware_context) VALUES(?,?,?,?,?,?,?)",
            (pid,name,repo,"analyzing" if repo else "interview",t,t,hardware_context))
    if hardware_context:add_source(pid,"hardware","Hardware / physical product",hardware_context,{})
    return get_project(pid)

def add_source(project_id,source_type,label,content,metadata=None):
    sid=uuid.uuid4().hex
    execute("INSERT INTO product_sources VALUES(?,?,?,?,?,?,?)",(sid,project_id,source_type,label,content,json.dumps(metadata or {},ensure_ascii=False),now()))
    return sid

def list_sources(project_id):
    out=rows("SELECT * FROM product_sources WHERE project_id=? ORDER BY created_at",(project_id,))
    for r in out:
        try:r["metadata"]=json.loads(r["metadata_json"] or "{}")
        except:r["metadata"]={}
    return out

def get_project(pid):
    r=row("SELECT * FROM projects WHERE id=?", (pid,))
    if not r:return None
    for col,key,default in [("analysis_json","analysis",{}),("questions_json","questions",[]),("answers_json","answers",[]),("profile_json","profile",{}),("team_proposal_json","team_proposal",{}),("chief_memory_json","chief_memory",{})]:
        try:r[key]=json.loads(r.get(col) or json.dumps(default))
        except:r[key]=default
    r["sources"]=list_sources(pid)
    return r

def list_projects():return [get_project(x["id"]) for x in rows("SELECT id FROM projects ORDER BY updated_at DESC")]

def update_project(pid,**fields):
    mapping={"analysis":"analysis_json","questions":"questions_json","answers":"answers_json","profile":"profile_json","team_proposal":"team_proposal_json","chief_memory":"chief_memory_json"}
    pairs=[];vals=[]
    for k,v in fields.items():
        pairs.append(f"{mapping.get(k,k)}=?");vals.append(json.dumps(v,ensure_ascii=False) if k in mapping else v)
    pairs.append("updated_at=?");vals.extend([now(),pid]);execute(f"UPDATE projects SET {','.join(pairs)} WHERE id=?",tuple(vals));return get_project(pid)

def create_job(kind,project_id=None,message="Queued"):
    jid=uuid.uuid4().hex;t=now();execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?)",(jid,kind,project_id,"queued",0,message,None,None,t,t));return get_job(jid)
def get_job(jid):return row("SELECT * FROM jobs WHERE id=?", (jid,))
def update_job(jid,**fields):
    pairs=[];vals=[]
    for k,v in fields.items():pairs.append(f"{k}=?");vals.append(v)
    pairs.append("updated_at=?");vals.extend([now(),jid]);execute(f"UPDATE jobs SET {','.join(pairs)} WHERE id=?",tuple(vals));return get_job(jid)
def list_jobs(limit=30):return rows("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?",(limit,))

def create_campaign(project_id,goal,context):
    cid=uuid.uuid4().hex;execute("INSERT INTO campaigns(id,project_id,goal,context,status,created_at) VALUES(?,?,?,?,?,?)",(cid,project_id,goal,context,"generating",now()));return get_campaign(cid)
def get_campaign(cid):
    r=row("SELECT * FROM campaigns WHERE id=?", (cid,))
    if not r:return None
    for col,key,default in [("strategy_json","strategy",{}),("calendar_json","calendar",[]),("posts_json","posts",[])]:
        try:r[key]=json.loads(r[col] or json.dumps(default))
        except:r[key]=default
    return r
def list_campaigns(project_id=None):
    q="SELECT id FROM campaigns";args=()
    if project_id:q+=" WHERE project_id=?";args=(project_id,)
    q+=" ORDER BY created_at DESC";return [get_campaign(x["id"]) for x in rows(q,args)]
def update_campaign(cid,**fields):
    mapping={"strategy":"strategy_json","calendar":"calendar_json","posts":"posts_json"};pairs=[];vals=[]
    for k,v in fields.items():pairs.append(f"{mapping.get(k,k)}=?");vals.append(json.dumps(v,ensure_ascii=False) if k in mapping else v)
    vals.append(cid);execute(f"UPDATE campaigns SET {','.join(pairs)} WHERE id=?",tuple(vals));return get_campaign(cid)
