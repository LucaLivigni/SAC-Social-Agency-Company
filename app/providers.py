from __future__ import annotations
import json,re
from .config import settings
from .secrets import get_secret
from . import db

def _extract_json(text: str):
    text=(text or "").strip();text=re.sub(r"^```(?:json)?\s*|\s*```$","",text)
    try:return json.loads(text)
    except Exception:
        m=re.search(r"(\{.*\}|\[.*\])",text,re.S)
        if not m:raise ValueError("Model did not return valid JSON")
        return json.loads(m.group(1))

def profile_for_agent(agent_id: str):
    mid=db.assignments().get(agent_id,"openai-default");return db.row("SELECT * FROM model_profiles WHERE id=?", (mid,))

def agent_system(agent_id: str, extra: str=""):
    a=db.get_agent(agent_id);manifest=(a or {}).get("manifest",{});prompt=manifest.get("system_prompt","")
    if not prompt:prompt=f"You are {a.get('title','a specialist AI agent') if a else 'an AI agent'}."
    return prompt+("\n"+extra if extra else "")

async def ask_json(agent_id: str, system: str, user: str):
    p=profile_for_agent(agent_id)
    if not p:raise RuntimeError(f"No model profile for {agent_id}")
    provider=p["provider"];model=p["model_id"];instruction=agent_system(agent_id,system)+"\nReturn ONLY valid JSON. No markdown fences."
    if provider=="openai":
        key=get_secret(p.get("secret_name") or "openai-api","OPENAI_API_KEY") or settings.openai_api_key
        if not key:raise RuntimeError("OpenAI is not connected")
        from openai import AsyncOpenAI
        client=AsyncOpenAI(api_key=key);r=await client.responses.create(model=model,input=[{"role":"system","content":instruction},{"role":"user","content":user}]);return _extract_json(r.output_text)
    if provider=="anthropic":
        key=get_secret(p.get("secret_name") or "anthropic-api","ANTHROPIC_API_KEY") or settings.anthropic_api_key
        if not key:raise RuntimeError("Anthropic is not connected")
        from anthropic import AsyncAnthropic
        client=AsyncAnthropic(api_key=key);r=await client.messages.create(model=model,max_tokens=6000,system=instruction,messages=[{"role":"user","content":user}]);return _extract_json("".join(getattr(x,"text","") for x in r.content))
    if provider=="openai_compatible":
        key=get_secret(p.get("secret_name") or f"provider-{p['id']}") or "local"
        from openai import AsyncOpenAI
        client=AsyncOpenAI(api_key=key,base_url=p["base_url"]);r=await client.chat.completions.create(model=model,messages=[{"role":"system","content":instruction},{"role":"user","content":user}],temperature=.35);return _extract_json(r.choices[0].message.content or "{}")
    raise RuntimeError(f"Unsupported provider: {provider}")

async def ask_text(agent_id: str, system: str, user: str):
    return await ask_json(agent_id,system+'\nReturn an object {"reply": string, "memory": object, "request": object|null}.',user)
