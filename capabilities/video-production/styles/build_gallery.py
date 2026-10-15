#!/usr/bin/env python3
"""把 video-styles.json 与 style-map.json 渲染成 gallery.html。

为什么用生成器而不是手写 HTML：
数据改了要跟着改，手写会漂。这里两个 JSON 是唯一真源，HTML 是它的视图。

示意图来自 previews/ 目录，文件名等于风格 id。有就显示，没有就标「无示意图」。
previews/ 由 build_previews.py 生成。

用法：
    python3 build_gallery.py
输出：
    同目录的 gallery.html
"""
from __future__ import annotations

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent


def load(name: str) -> dict:
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def blocked_ids(reg: dict) -> set[str]:
    """被 Conan 判为不需要的风格。条目还在 video-styles.json 里，只是不上页面。"""
    return set(reg.get("blocked", {}).get("ids", []))


def build_items(reg: dict, previews: set[str], blocked: set[str]) -> list[dict]:
    items: list[dict] = []
    for s in reg["styles"]:
        if s["id"] in blocked:
            continue
        items.append(
            {
                "id": s["id"],
                "name": s["name"],
                "kind": "风格",
                "source": s["source"],
                "summary": s["summary"],
                "best_for": s.get("best_for"),
                "ratio": s.get("ratio", "any"),
                "execution": s["execution"],
                "status": s["status"],
                "depends_on": s.get("depends_on", []),
                "entry": s.get("entry", ""),
                "group": s.get("group", ""),
                "preview": s["id"] in previews,
            }
        )
    for g in reg["grammars"]:
        if g["id"] in blocked:
            continue
        items.append(
            {
                "id": g["id"],
                "name": g["name"],
                "kind": "语法",
                "source": g["source"],
                "summary": g["summary"],
                "best_for": g.get("best_for"),
                "ratio": g.get("ratio", "any"),
                "execution": g["execution"],
                "status": g["status"],
                "depends_on": g.get("depends_on", []),
                "entry": g.get("entry", ""),
                "group": "explainer-grammar",
                "preview": g["id"] in previews,
            }
        )
    return items


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>视频风格选择 · hq-geo</title>
<style>
  :root{
    --bg:#FAFAF8; --card:#FFFFFF; --border:#E5E3DC; --border-strong:#D3D1C7;
    --text:#2B2926; --muted:#7A766E; --faint:#A8A49B;
    --accent:#993C1D; --accent-soft:#FAECE7;
    --ok:#3B6D11; --ok-soft:#EAF3DE;
    --warn:#854F0B; --warn-soft:#FAEEDA;
    --off:#5F5E5A; --off-soft:#F1EFE8;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--text);
    font-family:-apple-system,"PingFang SC","Hiragino Sans GB",sans-serif;
    font-size:14px;line-height:1.6}
  header{padding:32px 40px 20px;border-bottom:1px solid var(--border)}
  h1{margin:0 0 6px;font-size:22px;font-weight:600}
  .sub{margin:0;color:var(--muted);max-width:760px}
  .stats{display:flex;gap:24px;margin-top:16px;flex-wrap:wrap}
  .stat b{display:block;font-size:20px;font-weight:600}
  .stat span{color:var(--muted);font-size:12px}
  .wrap{padding:24px 40px 60px;max-width:1400px}
  .row{display:flex;gap:10px;align-items:baseline;flex-wrap:wrap;margin-bottom:14px}
  .row .lbl{color:var(--muted);font-size:12px;min-width:64px}
  button.chip{border:1px solid var(--border-strong);background:var(--card);color:var(--text);
    padding:5px 12px;border-radius:999px;cursor:pointer;font-size:13px;font-family:inherit}
  button.chip:hover{border-color:var(--accent)}
  button.chip.on{background:var(--accent);border-color:var(--accent);color:#fff}
  .rec{border:1px solid var(--border);background:var(--card);border-radius:12px;
    padding:16px 18px;margin:8px 0 24px}
  .rec h2{margin:0 0 8px;font-size:15px;font-weight:600}
  .rec .why{color:var(--muted);margin:6px 0 0}
  .rec .line{margin:4px 0}
  .rec .line em{font-style:normal;color:var(--muted);margin-right:6px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}
  .card{overflow:hidden;border:1px solid var(--border);background:var(--card);border-radius:12px;
    padding:0 0 14px;display:flex;flex-direction:column;gap:8px}
  .card>*:not(.thumb){margin-left:16px;margin-right:16px}
  .card.hit{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent-soft)}
  .card.dim{opacity:.42}
  .card h3{margin:0;font-size:14px;font-weight:600;display:flex;gap:8px;align-items:center}
  .thumb{width:100%;aspect-ratio:16/10;object-fit:cover;object-position:center top;
    display:block;background:var(--off-soft);margin:0 0 4px}
  .thumb.contain{object-fit:contain;object-position:center}
  .thumb.none{display:flex;align-items:center;justify-content:center;
    color:var(--faint);font-size:12px;border-bottom:1px solid var(--border)}
  .src{font-size:11px;padding:1px 7px;border-radius:999px;background:var(--off-soft);color:var(--off);font-weight:400}
  .kind{font-size:11px;padding:1px 7px;border-radius:999px;background:var(--accent-soft);color:var(--accent);font-weight:400}
  .desc{color:var(--muted);font-size:13px;margin:0}
  .meta{display:flex;flex-wrap:wrap;gap:6px;margin-top:auto;padding-top:6px}
  .tag{font-size:11px;padding:2px 8px;border-radius:6px;background:var(--off-soft);color:var(--off)}
  .tag.ok{background:var(--ok-soft);color:var(--ok)}
  .tag.warn{background:var(--warn-soft);color:var(--warn)}
  .tag.off{background:var(--off-soft);color:var(--off)}
  .grp{font-size:11px;color:var(--faint)}
  code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:var(--muted)}
  .note{margin-top:28px;padding-top:16px;border-top:1px solid var(--border);
    color:var(--muted);font-size:12px;max-width:820px}
</style>
</head>
<body>
<header>
  <h1>视频风格选择</h1>
  <p class="sub">数据来自 <code>video-styles.json</code> 与 <code>style-map.json</code>，
  示意图来自 <code>previews/</code>。
  这个页面只负责让你看清每种风格长什么样、能不能跑、要不要钱。选哪个由你定。</p>
  <div class="stats" id="stats"></div>
</header>
<div class="wrap">
  <div class="row" id="topicRow"><span class="lbl">按选题</span></div>
  <div class="row" id="srcRow"><span class="lbl">按来源</span></div>
  <div class="row" id="execRow"><span class="lbl">按执行</span></div>
  <div id="recBox"></div>
  <div class="grid" id="grid"></div>
  <p class="note" id="note"></p>
</div>
<script>
const STYLES = __STYLES__;
const MAP = __MAP__;
const REG = __REG__;

const SRC_NAME = __SRCNAME__;
const GRP_NAME = __GRPNAME__;
const EXEC = {
  "local-render": {label:"本地渲染", cls:"ok", hint:"装依赖即可跑，不调外部 API"},
  "prompt-only": {label:"只出提示词", cls:"off", hint:"缺外部生图模型，现在出不了画面"},
  "paid-api": {label:"付费接口", cls:"warn", hint:"按量计费，上线前须设月度硬上限"}
};
const STATUS = {
  "needs-install": "依赖未装",
  "prompt-only": "出不了画面",
  "needs-authorization": "未授权",
  "ready": "可跑"
};

let fTopic = null, fSrc = null, fExec = null;

function esc(s){return String(s==null?"":s).replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;"}[c]));}

function chipRow(el, label, values, getLabel, onPick){
  const row = document.getElementById(el);
  row.innerHTML = '<span class="lbl">'+label+'</span>';
  const all = document.createElement("button");
  all.className = "chip" + (onPick.value===null?" on":"");
  all.textContent = "全部";
  all.onclick = ()=>{onPick.set(null); render();};
  row.appendChild(all);
  values.forEach(v=>{
    const b = document.createElement("button");
    b.className = "chip" + (onPick.value===v?" on":"");
    b.textContent = getLabel(v);
    b.onclick = ()=>{onPick.set(onPick.value===v?null:v); render();};
    row.appendChild(b);
  });
}

const pickTopic = {value:null, set(v){fTopic=v;}};
const pickSrc = {value:null, set(v){fSrc=v;}};
const pickExec = {value:null, set(v){fExec=v;}};

function matches(item){
  if(fSrc && item.source!==fSrc) return false;
  if(fExec && item.execution!==fExec) return false;
  return true;
}

function renderRec(){
  const box = document.getElementById("recBox");
  if(!fTopic){ box.innerHTML=""; return; }
  const t = MAP.topics.find(x=>x.id===fTopic);
  const d = t || MAP.default;
  const rec = t ? t : {name:"兜底", reason:MAP.default.reason};
  const name = t ? t.name : "未命中兜底";
  const prim = STYLES.find(s=>s.id===d.primary);
  const secs = (d.secondary||[]).map(id=>STYLES.find(s=>s.id===id)).filter(Boolean);
  box.innerHTML =
    '<div class="rec"><h2>推荐：'+esc(name)+'</h2>'+
    '<div class="line"><em>首选</em>'+esc(prim?prim.name:d.primary)+
      (prim?' <span class="grp">'+esc(EXEC[prim.execution].label)+' · '+esc(SRC_NAME[prim.source]||prim.source)+'</span>':'')+'</div>'+
    (secs.length?'<div class="line"><em>备选</em>'+secs.map(s=>esc(s.name)).join(" · ")+'</div>':'')+
    '<p class="why">'+esc(d.reason)+'</p></div>';
}

function render(){
  renderRec();
  const grid = document.getElementById("grid");
  const t = fTopic ? MAP.topics.find(x=>x.id===fTopic) : null;
  const hits = new Set();
  if(t){ hits.add(t.primary); (t.secondary||[]).forEach(s=>hits.add(s)); }
  const list = STYLES.filter(matches);
  grid.innerHTML = list.map(s=>{
    const hit = hits.has(s.id);
    const dim = (fTopic && !hit);
    const ex = EXEC[s.execution] || {label:s.execution,cls:"off"};
    const thumb = s.preview
      ? '<img class="thumb'+(s.kind==="语法"?" contain":"")+'" loading="lazy" src="previews/'+esc(s.id)+'.jpg" alt="'+esc(s.name)+' 示意图">'
      : '<div class="thumb none">无示意图</div>';
    return '<div class="card'+(hit?" hit":"")+(dim?" dim":"")+'">'+
      thumb+
      '<h3>'+esc(s.name)+
        '<span class="src">'+esc(SRC_NAME[s.source]||s.source)+'</span>'+
        (s.kind==="语法"?'<span class="kind">语法</span>':'')+'</h3>'+
      '<p class="desc">'+esc(s.summary)+'</p>'+
      '<div class="meta">'+
        '<span class="tag '+ex.cls+'">'+esc(ex.label)+'</span>'+
        '<span class="tag">'+esc(s.ratio)+'</span>'+
        (s.best_for?'<span class="tag">适合 '+esc(s.best_for)+'</span>':'')+
        '<span class="grp">'+esc(GRP_NAME[s.group]||s.group)+'</span>'+
      '</div>'+
      (s.depends_on&&s.depends_on.length?'<div class="grp">依赖 '+esc(s.depends_on.join(" · "))+'</div>':'')+
    '</div>';
  }).join("");
  document.getElementById("note").textContent =
    MAP.note + " " + (MAP.cost_note||"");
}

function stats(){
  const c = k => STYLES.filter(s=>s.execution===k).length;
  const have = STYLES.filter(s=>s.preview).length;
  document.getElementById("stats").innerHTML =
    '<div class="stat"><b>'+STYLES.length+'</b><span>条目总数</span></div>'+
    '<div class="stat"><b>'+have+'</b><span>有示意图</span></div>'+
    '<div class="stat"><b>'+STYLES.filter(s=>s.kind==="风格").length+'</b><span>视觉风格</span></div>'+
    '<div class="stat"><b>'+STYLES.filter(s=>s.kind==="语法").length+'</b><span>解说语法</span></div>'+
    '<div class="stat"><b>'+c("local-render")+'</b><span>本地渲染</span></div>'+
    '<div class="stat"><b>'+c("prompt-only")+'</b><span>只出提示词</span></div>'+
    '<div class="stat"><b>'+c("paid-api")+'</b><span>付费接口</span></div>';
}

const srcs = [...new Set(STYLES.map(s=>s.source))];
chipRow("topicRow","按选题", MAP.topics.map(t=>t.id), id=>MAP.topics.find(t=>t.id===id).name, pickTopic);
chipRow("srcRow","按来源", srcs, id=>SRC_NAME[id]||id, pickSrc);
chipRow("execRow","按执行", Object.keys(EXEC), id=>EXEC[id].label, pickExec);
stats(); render();
</script>
</body>
</html>
"""


def main() -> int:
    reg = load("video-styles.json")
    mp = load("style-map.json")
    previews = {p.stem for p in (HERE / "previews").glob("*.jpg")}
    items = build_items(reg, previews, blocked_ids(reg))

    src_name = {k: v["repo"].split("/")[0] for k, v in reg["sources"].items()}
    grp_name = {g["id"]: g["name"] for g in reg.get("groups", [])}

    html = (
        TEMPLATE.replace("__STYLES__", json.dumps(items, ensure_ascii=False))
        .replace("__MAP__", json.dumps(mp, ensure_ascii=False))
        .replace("__REG__", json.dumps({"sources": reg["sources"]}, ensure_ascii=False))
        .replace("__SRCNAME__", json.dumps(src_name, ensure_ascii=False))
        .replace("__GRPNAME__", json.dumps(grp_name, ensure_ascii=False))
    )
    out = HERE / "gallery.html"
    out.write_text(html, encoding="utf-8")
    have = sum(1 for i in items if i["preview"])
    print(f"写出 {out}  ({len(html)} 字节, {len(items)} 条, 有图 {have})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
