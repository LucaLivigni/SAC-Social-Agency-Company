from __future__ import annotations
import json,re
from .config import settings
from .secrets import get_secret
from .db import row,assignments

def _json(text):
    text=(text or "").strip(); text=re.sub(r"^\`\`\`(?:json)?\s*|\s*\`\`\`$","",text)
    try:return json.loads(text)
    except Exception:
        m=re.search(r"(\{.*\}|\[.*\])",text,re.S)
        if not m:raise ValueError("Model did not return valid JSON")
        return json.loads(m.group(1))

def profile(agent_id):
    mid=assignments().get(agent_id,"openai-default"); return row("SELECT * FROM model_profiles WHERE id=?",(mid,))

async def ask_json(agent_id,system,user):
    p=profile(agent_id)
    if not p:raise RuntimeError(f"No model profile for {agent_id}")
    instruction=system+"\nReturn ONLY valid JSON. No markdown fences."
    if p["provider"]=="openai":
        key=get_secret(p.get("secret_name") or "openai-api","OPENAI_API_KEY") or settings.openai_api_key
        if not key:raise RuntimeError("OpenAI is not connected")
        from openai import AsyncOpenAI
        c=AsyncOpenAI(api_key=key); r=await c.responses.create(model=p["model_id"],input=[{"role":"system","content":instruction},{"role":"user","content":user}]); return _json(r.output_text)
    if p["provider"]=="anthropic":
        from anthropic import AsyncAnthropic
        key=get_secret(p.get("secret_name") or "anthropic-api","ANTHROPIC_API_KEY") or settings.anthropic_api_key
        if not key:raise RuntimeError("Anthropic is not connected")
        c=AsyncAnthropic(api_key=key); r=await c.messages.create(model=p["model_id"],max_tokens=5000,system=instruction,messages=[{"role":"user","content":user}]); return _json("".join(getattr(x,"text","") for x in r.content))
    if p["provider"]=="openai_compatible":
        key=get_secret(p.get("secret_name") or f"provider-{p['id']}") or "local"
        from openai import AsyncOpenAI
        c=AsyncOpenAI(api_key=key,base_url=p["base_url"]); r=await c.chat.completions.create(model=p["model_id"],messages=[{"role":"system","content":instruction},{"role":"user","content":user}],temperature=.4); return _json(r.choices[0].message.content)
    raise RuntimeError("Unsupported model provider")
