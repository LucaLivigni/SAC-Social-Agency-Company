from __future__ import annotations
import asyncio,base64
from pathlib import Path
from urllib.parse import quote
import httpx
from .secrets import get_secret,set_secret,delete_secret
from . import db
API="https://api.github.com";SECRET="github-token";MAX_FILES=120;MAX_TOTAL=280000;MAX_PER_FILE=14000
TEXT_EXT={".md",".txt",".py",".js",".jsx",".ts",".tsx",".java",".kt",".swift",".go",".rs",".php",".rb",".cs",".html",".css",".scss",".vue",".svelte",".sql",".graphql",".gql",".yaml",".yml",".json",".toml",".xml",".properties",".gradle",".sh",".c",".cpp",".h",".hpp",".ino"}
IMPORTANT={"readme.md","readme","package.json","pyproject.toml","pom.xml","build.gradle","dockerfile","docker-compose.yml","openapi.yaml","openapi.yml","swagger.json","platformio.ini","cargo.toml"}
SENSITIVE=("secret","credential","private_key",".env","token.json","id_rsa","id_ed25519",".pem",".p12",".pfx")
def token():return get_secret(SECRET,"GITHUB_TOKEN")
def headers():
    t=token()
    if not t:raise RuntimeError("GitHub is not connected")
    return {"Authorization":f"Bearer {t}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
async def connect(value):
    h={"Authorization":f"Bearer {value}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
    async with httpx.AsyncClient(timeout=20) as c:r=await c.get(f"{API}/user",headers=h)
    if not r.is_success:raise RuntimeError("Token GitHub non valido o senza accesso all'account")
    set_secret(SECRET,value);u=r.json();db.connection_set("github","connected",{"login":u.get("login"),"avatar_url":u.get("avatar_url")});return {"login":u.get("login"),"name":u.get("name"),"avatar_url":u.get("avatar_url")}
def disconnect():delete_secret(SECRET);db.connection_set("github","not_connected",{})
async def me():
    if not token():return None
    async with httpx.AsyncClient(timeout=20) as c:r=await c.get(f"{API}/user",headers=headers())
    return r.json() if r.is_success else None
async def repos():
    h=headers();out=[];page=1
    async with httpx.AsyncClient(timeout=25) as c:
        while page<=10:
            r=await c.get(f"{API}/user/repos",headers=h,params={"per_page":100,"page":page,"sort":"updated","affiliation":"owner,collaborator,organization_member"})
            if not r.is_success:raise RuntimeError(f"GitHub error {r.status_code}")
            items=r.json();out.extend(items)
            if len(items)<100:break
            page+=1
    return [{"id":x["id"],"full_name":x["full_name"],"name":x["name"],"private":x["private"],"description":x.get("description") or "","default_branch":x.get("default_branch") or "main","language":x.get("language") or "","updated_at":x.get("updated_at"),"html_url":x.get("html_url")} for x in out]
def _candidate(path,size):
    p=Path(path);low=path.lower()
    if size and size>200000:return False
    if any(s in low for s in SENSITIVE):return False
    if {x.lower() for x in p.parts}&{".git","node_modules",".venv","venv","dist","build","target",".next","vendor","coverage","pods"}:return False
    return p.name.lower() in IMPORTANT or p.suffix.lower() in TEXT_EXT
def _priority(path):
    s=path.lower();n=Path(path).name.lower()
    if n.startswith("readme"):return 0
    if n in {"package.json","pyproject.toml","pom.xml","build.gradle","platformio.ini","cargo.toml"}:return 5
    if "docs/" in s or "manual" in s:return 10
    if any(x in s for x in ["route","controller","api/","openapi","swagger"]):return 15
    if any(x in s for x in ["page","screen","view","component","feature"]):return 20
    if any(x in s for x in ["model","entity","schema","types"]):return 25
    if any(x in s for x in ["service","domain","usecase","firmware","src/main"]):return 30
    if any(x in s for x in ["test","spec"]):return 80
    return 50
async def repo_bundle(full_name):
    owner,name=full_name.split("/",1);h=headers()
    async with httpx.AsyncClient(timeout=45) as c:
        m=await c.get(f"{API}/repos/{owner}/{name}",headers=h)
        if not m.is_success:raise RuntimeError("Repository non accessibile")
        branch=m.json().get("default_branch") or "main"
        tr=await c.get(f"{API}/repos/{owner}/{name}/git/trees/{quote(branch,safe='')}",headers=h,params={"recursive":"1"})
        if not tr.is_success:raise RuntimeError("Impossibile leggere la repository")
        tree=tr.json().get("tree",[]);cand=[x for x in tree if x.get("type")=="blob" and _candidate(x["path"],x.get("size",0))];cand.sort(key=lambda x:_priority(x["path"]));selected=cand[:MAX_FILES];sem=asyncio.Semaphore(10)
        async def fetch(item):
            async with sem:
                r=await c.get(f"{API}/repos/{owner}/{name}/contents/{quote(item['path'],safe='/')}",headers=h,params={"ref":branch})
                if not r.is_success:return None
                d=r.json()
                if d.get("encoding")!="base64" or not d.get("content"):return None
                try:
                    raw=base64.b64decode(d["content"])
                    if b"\x00" in raw[:2048]:return None
                    return item["path"],raw.decode("utf-8",errors="replace")[:MAX_PER_FILE]
                except:return None
        fetched=await asyncio.gather(*[fetch(x) for x in selected])
    blocks=[];paths=[];total=0;truncated=len(cand)>MAX_FILES or bool(tr.json().get("truncated"))
    for item in fetched:
        if not item:continue
        path,text=item;block=f"\n\n===== FILE: {path} =====\n{text}"
        if total+len(block)>MAX_TOTAL:truncated=True;break
        blocks.append(block);paths.append(path);total+=len(block)
    return {"repo":full_name,"branch":branch,"paths":paths,"content":"".join(blocks),"files_scanned":len(tree),"files_used":len(paths),"truncated":truncated}
