from __future__ import annotations
import csv,json,shutil,zipfile
from pathlib import Path
from . import db
def _safe(s):return ''.join(c if c.isalnum() or c in '-_ ' else '_' for c in str(s)).strip().replace(' ','_')[:70] or 'post'
def export_campaign(cid):
    c=db.get_campaign(cid)
    if not c:raise ValueError("Campaign not found")
    root=Path("data/exports")/cid
    if root.exists():shutil.rmtree(root)
    root.mkdir(parents=True)
    with (root/"calendar.csv").open("w",newline="",encoding="utf-8-sig") as f:
        w=csv.writer(f);w.writerow(["date","time","platform","format","title","status","review_score"])
        for x in c.get("posts",[]):
            s=x.get("slot",{});p=x.get("post",{});rv=x.get("review",{});w.writerow([s.get("date"),s.get("time"),s.get("platform"),s.get("format"),p.get("title"),x.get("status"),rv.get("score")])
    (root/"strategy.json").write_text(json.dumps(c.get("strategy",{}),ensure_ascii=False,indent=2),encoding="utf-8")
    for i,x in enumerate(c.get("posts",[]),1):
        s=x.get("slot",{});p=x.get("post",{});rv=x.get("review",{});d=root/f"{i:02d}_{s.get('platform','social')}_{_safe(p.get('title','post'))}";d.mkdir()
        caption=p.get("caption","")
        if p.get("hashtags"):caption+="\n\n"+" ".join(h if str(h).startswith("#") else "#"+str(h) for h in p["hashtags"])
        (d/"CAPTION.txt").write_text(caption,encoding="utf-8");(d/"CTA.txt").write_text(p.get("cta",""),encoding="utf-8");(d/"FIRST_COMMENT.txt").write_text(p.get("first_comment",""),encoding="utf-8")
        if p.get("carousel_slides"):(d/"CAROUSEL.txt").write_text("\n".join(f"{n+1}. {v}" for n,v in enumerate(p["carousel_slides"])),encoding="utf-8")
        if p.get("thread_posts"):(d/"THREAD.txt").write_text("\n\n---\n\n".join(p["thread_posts"]),encoding="utf-8")
        if p.get("reel_script"):(d/"REEL_SCRIPT.txt").write_text("\n".join(f"{n+1}. {v}" for n,v in enumerate(p["reel_script"])),encoding="utf-8")
        creative=p.get("creative",{});(d/"VISUAL_BRIEF.txt").write_text((p.get("visual_brief") or "")+"\n\n"+(creative.get("art_direction") or "")+"\n\nIMAGE PROMPT:\n"+(creative.get("image_prompt") or ""),encoding="utf-8");(d/"REVIEW.json").write_text(json.dumps(rv,ensure_ascii=False,indent=2),encoding="utf-8")
        url=x.get("image_url") or ""
        if "/assets/" in url:
            fp=Path("data/assets")/url.rsplit("/assets/",1)[1]
            if fp.exists():shutil.copy2(fp,d/"VISUAL.png")
    zp=Path("data/exports")/f"{cid}_READY_TO_PUBLISH.zip"
    if zp.exists():zp.unlink()
    with zipfile.ZipFile(zp,"w",zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            if p.is_file():z.write(p,p.relative_to(root))
    return zp
