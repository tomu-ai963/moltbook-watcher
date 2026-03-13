#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, jsonify, render_template_string
from watcher import shared, start_watcher, stop_watcher

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Moltbook Watcher</title>
  <style>
    :root{--bg:#0e0e0e;--card:#1a1a1a;--border:#2a2a2a;--gold:#c9a84c;--gold2:#e8c97a;--text:#e8e8e8;--muted:#888;--green:#4caf50;--red:#e57373;--orange:#ffa726;}
    *{box-sizing:border-box;margin:0;padding:0;}
    body{background:var(--bg);color:var(--text);font-family:'Segoe UI',system-ui,sans-serif;min-height:100vh;}
    header{border-bottom:1px solid var(--gold);padding:16px 20px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;background:var(--bg);z-index:10;}
    .logo{font-size:1.1rem;font-weight:700;color:var(--gold);letter-spacing:.05em;}
    .logo span{color:var(--text);font-weight:300;}
    .status-dot{width:10px;height:10px;border-radius:50%;background:var(--red);display:inline-block;margin-right:6px;transition:background .3s;}
    .status-dot.running{background:var(--green);animation:pulse 1.5s infinite;}
    @keyframes pulse{0%,100%{opacity:1;}50%{opacity:.4;}}
    .controls{padding:16px 20px;display:flex;gap:10px;flex-wrap:wrap;}
    button{border:none;border-radius:6px;padding:10px 22px;font-size:.9rem;font-weight:600;cursor:pointer;transition:opacity .2s;}
    button:active{opacity:.7;}
    .btn-start{background:var(--gold);color:#111;}
    .btn-stop{background:var(--border);color:var(--text);border:1px solid var(--muted);}
    .btn-clear{background:transparent;color:var(--muted);border:1px solid var(--border);font-size:.8rem;padding:10px 14px;}
    .stats{display:flex;gap:12px;padding:0 20px 16px;flex-wrap:wrap;}
    .stat-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 16px;min-width:90px;text-align:center;}
    .stat-num{font-size:1.4rem;font-weight:700;color:var(--gold2);}
    .stat-lbl{font-size:.7rem;color:var(--muted);margin-top:2px;}
    .trend-bar{padding:8px 20px;display:flex;gap:8px;flex-wrap:wrap;align-items:center;}
    .trend-lbl{font-size:.75rem;color:var(--muted);margin-right:4px;}
    .badge{background:#1e1a0e;border:1px solid var(--gold);border-radius:20px;padding:3px 10px;font-size:.75rem;color:var(--gold2);}
    .main{display:grid;grid-template-columns:1fr 340px;gap:0;height:calc(100vh - 200px);}
    @media(max-width:700px){.main{grid-template-columns:1fr;height:auto;}}
    .posts-panel{overflow-y:auto;padding:0 20px 20px;border-right:1px solid var(--border);}
    .log-panel{overflow-y:auto;padding:0 16px 20px;}
    .panel-title{font-size:.75rem;color:var(--muted);text-transform:uppercase;letter-spacing:.1em;padding:12px 0 8px;position:sticky;top:0;background:var(--bg);}
    .post-card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px 14px;margin-bottom:10px;}
    .post-card.flagged{border-color:var(--gold);}
    .post-title{font-size:.9rem;font-weight:600;margin-bottom:4px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;}
    .post-meta{font-size:.72rem;color:var(--muted);display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:6px;}
    .importance-bar{height:3px;background:var(--border);border-radius:2px;margin:6px 0;}
    .importance-fill{height:100%;border-radius:2px;background:linear-gradient(90deg,#4caf50,var(--gold),var(--red));}
    .summary{font-size:.78rem;color:#aaa;line-height:1.5;margin-top:4px;}
    .kw-list{display:flex;gap:5px;flex-wrap:wrap;margin-top:6px;}
    .kw{background:#1a1a2e;color:#7ba7e8;border-radius:4px;padding:2px 7px;font-size:.7rem;}
    .post-link{display:inline-block;margin-top:8px;font-size:.75rem;color:var(--gold);text-decoration:none;}
    .flag-badge{background:var(--gold);color:#111;font-size:.65rem;font-weight:700;padding:2px 7px;border-radius:4px;}
    .log-entry{padding:5px 0;font-size:.78rem;border-bottom:1px solid #1a1a1a;display:flex;gap:8px;}
    .log-ts{color:var(--muted);white-space:nowrap;}
    .log-success{color:var(--green);}.log-warn{color:var(--orange);}.log-error{color:var(--red);}.log-alert{color:var(--gold2);font-weight:600;}
    .empty{text-align:center;color:var(--muted);padding:40px 0;font-size:.85rem;}
  </style>
</head>
<body>
<header>
  <div class="logo">Moltbook <span>Watcher</span></div>
  <div style="font-size:.8rem;color:var(--muted)">
    <span class="status-dot" id="dot"></span>
    <span id="status-txt">停止中</span>
  </div>
</header>
<div class="controls">
  <button class="btn-start" onclick="ctrl('start')">▶ Start</button>
  <button class="btn-stop"  onclick="ctrl('stop')">■ Stop</button>
  <button class="btn-clear" onclick="ctrl('clear')">ログ消去</button>
</div>
<div class="stats">
  <div class="stat-card"><div class="stat-num" id="s-total">0</div><div class="stat-lbl">取得件数</div></div>
  <div class="stat-card"><div class="stat-num" id="s-notified">0</div><div class="stat-lbl">重要フラグ</div></div>
  <div class="stat-card"><div class="stat-num" id="s-ai">0</div><div class="stat-lbl">AI分析</div></div>
</div>
<div class="trend-bar" id="trend-bar"><span class="trend-lbl">24h TREND:</span></div>
<div class="main">
  <div class="posts-panel">
    <div class="panel-title">新着投稿</div>
    <div id="posts-list"><div class="empty">Startを押すと取得を開始します</div></div>
  </div>
  <div class="log-panel">
    <div class="panel-title">ログ</div>
    <div id="log-list"></div>
  </div>
</div>
<script>
let pC=0,lC=0;
async function ctrl(a){await fetch('/api/'+a,{method:'POST'});}
async function poll(){
  try{
    const d=await(await fetch('/api/state')).json();
    document.getElementById('dot').className='status-dot'+(d.running?' running':'');
    document.getElementById('status-txt').textContent=d.running?'監視中':'停止中';
    document.getElementById('s-total').textContent=d.stats.total;
    document.getElementById('s-notified').textContent=d.stats.notified;
    document.getElementById('s-ai').textContent=d.stats.ai_used;
    if(d.trend.length){
      document.getElementById('trend-bar').innerHTML='<span class="trend-lbl">24h TREND:</span>'+
        d.trend.map(t=>`<span class="badge">${t.word} <b>${t.count}</b></span>`).join('');
    }
    if(d.posts.length!==pC){
      pC=d.posts.length;
      const el=document.getElementById('posts-list');
      el.innerHTML=d.posts.length?d.posts.map(p=>{
        const imp=p.importance??0;
        return`<div class="post-card ${p.flagged?'flagged':''}">
          <div class="post-title">${p.title}</div>
          <div class="post-meta">${p.flagged?'<span class="flag-badge">🔔 重要</span>':''}${p.category?`<span>${p.category}</span>`:''}<span>${p.ts}</span></div>
          ${p.importance!==null?`<div class="importance-bar"><div class="importance-fill" style="width:${imp}%"></div></div>`:''}
          ${p.summary_ja?`<div class="summary">${p.summary_ja}</div>`:''}
          ${(p.keywords||[]).length?`<div class="kw-list">${p.keywords.map(k=>`<span class="kw">${k}</span>`).join('')}</div>`:''}
          <a class="post-link" href="${p.url}" target="_blank">→ 記事を開く</a>
        </div>`;
      }).join(''):'<div class="empty">まだ投稿はありません</div>';
    }
    if(d.logs.length!==lC){
      const el=document.getElementById('log-list');
      d.logs.slice(lC).forEach(l=>{
        const div=document.createElement('div');
        div.className='log-entry';
        div.innerHTML=`<span class="log-ts">${l.ts}</span><span class="log-msg log-${l.level}">${l.msg}</span>`;
        el.prepend(div);
      });
      lC=d.logs.length;
    }
  }catch(e){console.error(e);}
}
setInterval(poll,2000);poll();
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/state")
def api_state():
    return jsonify({"running":shared["running"],"logs":shared["logs"][-50:],
                    "posts":shared["posts"][:30],"trend":shared["trend"][:10],"stats":shared["stats"]})

@app.route("/api/start",methods=["POST"])
def api_start():
    start_watcher(); return jsonify({"ok":True})

@app.route("/api/stop",methods=["POST"])
def api_stop():
    stop_watcher(); return jsonify({"ok":True})

@app.route("/api/clear",methods=["POST"])
def api_clear():
    shared["logs"]=[]; return jsonify({"ok":True})

if __name__=="__main__":
    print("="*40)
    print(" Moltbook Watcher  http://localhost:5000")
    print("="*40)
    app.run(host="0.0.0.0",port=5000,debug=False)
