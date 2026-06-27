# BruteForcer Mutator Lab v3.3 - Ordered candidate strategies, detailed telemetry, and tunable lab controls
# Additions: resource governor, capture preflight/triage, safer SSID parsing,
# queue controls, exports, and confidence-weighted wordlist reporting.
# Existing behavior is retained unless active scheduling / dedupe options are explicitly enabled.
# v3.2.1: adds live fan speed and RPM telemetry beside CPU temperature via a lightweight status file written by fan_control.py.

import os
import json
import time
import logging
import threading
import subprocess
import re
import base64
import codecs
import csv
import io
import hashlib
import ast
from typing import Set, Optional

from flask import Flask, render_template_string, jsonify, redirect, url_for, Response, request

import pwnagotchi.plugins as plugins
import pwnagotchi.ui.fonts as fonts
from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK

# You can tweak these if you want a different bind/port
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT_DEFAULT = 5000

DASHBOARD_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SkyGotchi Command Center</title>
  <style>
    :root{--bg:#071019;--panel:#0d1b2a;--panel2:#10253a;--line:#1d3852;--text:#e5eef7;--muted:#8ba1b8;--good:#38d996;--warn:#f7c65a;--bad:#ff6b6b;--blue:#61b6ff;--purple:#b98cff;--shadow:0 16px 35px rgba(0,0,0,.26)}
    *{box-sizing:border-box} body{margin:0;background:radial-gradient(circle at top right,#123151 0,#071019 44%);color:var(--text);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;min-height:100vh}
    a{color:inherit;text-decoration:none}.shell{max-width:1600px;margin:auto;padding:18px}.top{display:flex;gap:18px;align-items:center;justify-content:space-between;border:1px solid var(--line);background:linear-gradient(135deg,rgba(13,27,42,.95),rgba(9,23,37,.92));padding:18px;border-radius:16px;box-shadow:var(--shadow)}
    .brand h1{font-size:clamp(1.15rem,3vw,1.9rem);margin:0 0 6px;letter-spacing:.07em}.brand p{margin:0;color:var(--muted);font-size:.78rem}.live{display:flex;align-items:center;gap:8px;font-size:.8rem}.dot{width:10px;height:10px;border-radius:50%;background:var(--muted);box-shadow:0 0 12px currentColor}.dot.good{color:var(--good);background:var(--good)}.dot.warn{color:var(--warn);background:var(--warn)}.dot.bad{color:var(--bad);background:var(--bad)}
    .nav{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.btn{border:1px solid var(--line);background:#0b1724;color:var(--text);padding:9px 11px;border-radius:9px;font:inherit;font-size:.76rem;cursor:pointer;transition:.15s}.btn:hover{border-color:var(--blue);transform:translateY(-1px)}.btn.primary{background:#0b3556;border-color:#226b9d}.btn.good{background:#0d3b2b;border-color:#287c5f}.btn.warn{background:#44340c;border-color:#8c6b17}.btn.bad{background:#421b23;border-color:#88404b}.btn:disabled{opacity:.45;cursor:not-allowed;transform:none}
    .statusbar{margin:14px 0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.statuschip{border:1px solid var(--line);background:rgba(10,27,42,.86);padding:10px 12px;border-radius:12px}.statuschip .k{display:block;color:var(--muted);font-size:.66rem;text-transform:uppercase;letter-spacing:.08em}.statuschip .v{display:block;margin-top:5px;font-size:.88rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px}.card{border:1px solid var(--line);background:linear-gradient(180deg,rgba(13,27,42,.98),rgba(8,20,32,.98));border-radius:14px;padding:14px;box-shadow:var(--shadow);min-width:0}.card h2{font-size:.75rem;color:#a8c2da;margin:0 0 12px;text-transform:uppercase;letter-spacing:.08em}.now{grid-column:span 8}.health{grid-column:span 4}.metrics{grid-column:span 12}.queue{grid-column:span 4}.mutator{grid-column:span 4}.lists{grid-column:span 4}.activity{grid-column:span 7}.logs{grid-column:span 5}
    .now-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.job-name{font-size:1.18rem;font-weight:800;word-break:break-word}.sub{color:var(--muted);font-size:.76rem;margin-top:6px;word-break:break-word}.badge{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);border-radius:999px;padding:5px 8px;font-size:.68rem;white-space:nowrap}.badge.good{background:#0a2c21;color:#9af0c7;border-color:#236c52}.badge.warn{background:#3c2d08;color:#ffe29a;border-color:#785e15}.badge.bad{background:#3d1b22;color:#ffadad;border-color:#803947}.badge.blue{background:#0c2945;color:#a8d7ff;border-color:#275c86}
    .progress{height:11px;border-radius:999px;background:#08131f;border:1px solid #17314a;overflow:hidden;margin:16px 0 10px}.progress>span{display:block;height:100%;background:linear-gradient(90deg,var(--blue),var(--purple));width:0%;transition:width .35s}.now-meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}.mini{background:#091624;border:1px solid #16314a;padding:9px;border-radius:9px}.mini .k{font-size:.62rem;color:var(--muted);text-transform:uppercase}.mini .v{font-size:.9rem;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
    .controls{display:flex;gap:7px;flex-wrap:wrap;margin-top:13px}.health-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.health-grid .mini{min-height:67px}.health-foot{margin-top:10px;border-top:1px solid var(--line);padding-top:10px;color:var(--muted);font-size:.73rem;line-height:1.5}.metric-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:9px}.metric{background:#091624;border:1px solid #16314a;padding:12px;border-radius:10px}.metric .k{color:var(--muted);font-size:.63rem;text-transform:uppercase}.metric .v{font-size:1.18rem;font-weight:800;margin:5px 0}.metric small{color:var(--muted);font-size:.65rem}
    .sparkrow{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin-top:13px}.spark{border:1px solid #16314a;background:#091624;border-radius:10px;padding:10px}.spark .label{color:var(--muted);font-size:.67rem;margin-bottom:8px}.spark svg{height:58px;width:100%;display:block}.spark .line{fill:none;stroke:var(--blue);stroke-width:2}.spark .gridline{stroke:#17324a;stroke-width:1}
    .list{display:flex;flex-direction:column;gap:7px;max-height:292px;overflow:auto;padding-right:3px}.item{border:1px solid #18354e;background:#0a1826;border-radius:9px;padding:9px;display:flex;justify-content:space-between;gap:10px}.item .title{font-size:.78rem;font-weight:700;word-break:break-word}.item .desc{font-size:.67rem;color:var(--muted);margin-top:3px;word-break:break-word}.item .right{font-size:.68rem;text-align:right;color:var(--muted);white-space:nowrap}.mut-body{display:grid;gap:10px}.rule{display:flex;justify-content:space-between;gap:12px;border-bottom:1px dashed #1b344d;padding-bottom:7px;font-size:.74rem}.rule:last-child{border:0;padding-bottom:0}.rule span:last-child{color:#bde0ff;text-align:right;word-break:break-word}
    .tablewrap{overflow:auto;border:1px solid #16314a;border-radius:10px}.table{width:100%;border-collapse:collapse;font-size:.72rem}.table th{text-align:left;color:#9fb9d0;background:#0c1e2d;padding:9px;position:sticky;top:0}.table td{padding:9px;border-top:1px solid #142b42;color:#d8e6f3}.table tr:hover td{background:#0d2031}.logbox{height:290px;overflow:auto;background:#050d16;border:1px solid #153149;border-radius:10px;padding:10px;color:#b9c7d5;font-size:.68rem;line-height:1.55;white-space:pre-wrap}.empty{color:var(--muted);font-size:.75rem;padding:15px 0}.foot{padding:18px 3px 4px;color:#68839c;font-size:.66rem;text-align:center}
    @media(max-width:1050px){.now,.health,.queue,.mutator,.lists,.activity,.logs{grid-column:span 12}.health-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.metric-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.statusbar{grid-template-columns:repeat(2,minmax(0,1fr))}.top{align-items:flex-start;flex-direction:column}.nav{justify-content:flex-start}.now-meta{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:570px){.shell{padding:10px}.statusbar{grid-template-columns:1fr 1fr}.metric-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.sparkrow{grid-template-columns:1fr}.now-meta{grid-template-columns:1fr 1fr}.btn{padding:8px 9px;font-size:.7rem}}
  </style>
</head>
<body>
  <main class="shell">
    <header class="top">
      <div class="brand"><h1>SKYGOTHCHI  |  COMMAND CENTER</h1><p>Offline dashboard  |  live queue, health, captures, and wordlist intelligence</p></div>
      <div class="nav">
        <a class="btn primary" href="/captures">Capture Library</a>
        <a class="btn" href="/intelligence">Intelligence</a>
        <a class="btn" href="/reports">Reports</a>
        <a class="btn" href="/mutator">Mutator Lab</a>
        <a class="btn" href="/networks">SSID & Wordlists</a>
        <a class="btn" href="/api/export/json">Export JSON</a>
        <a class="btn" href="/api/export/csv">Export CSV</a>
      </div>
    </header>

    <section class="statusbar">
      <div class="statuschip"><span class="k">Engine</span><span class="v"><span id="engineDot" class="dot"></span> <span id="engineText">Loading...</span></span></div>
      <div class="statuschip"><span class="k">Queue</span><span class="v" id="queueStatus">Loading...</span></div>
      <div class="statuschip"><span class="k">Governor</span><span class="v" id="governorStatus">Loading...</span></div>
      <div class="statuschip"><span class="k">Last refresh</span><span class="v" id="lastRefresh">-</span></div>
    </section>

    <section class="grid">
      <article class="card now">
        <div class="now-head">
          <div><h2>Now Processing</h2><div class="job-name" id="currentSsid">Idle - queue is waiting for a capture</div><div class="sub" id="currentPcap">No active capture</div></div>
          <div id="currentState" class="badge blue">IDLE</div>
        </div>
        <div class="progress"><span id="currentProgress"></span></div>
        <div class="now-meta">
          <div class="mini"><div class="k">Current stage</div><div class="v" id="currentWordlist">-</div></div>
          <div class="mini"><div class="k">Attempt</div><div class="v" id="currentAttempt">-</div></div>
          <div class="mini"><div class="k">Elapsed</div><div class="v" id="currentElapsed">0s</div></div>
          <div class="mini"><div class="k">Progress</div><div class="v" id="currentProgressText">0%</div></div>
        </div>
        <div class="controls">
          <button class="btn warn" onclick="control('pause')">Pause Queue</button>
          <button class="btn good" onclick="control('resume')">Resume</button>
          <button class="btn" onclick="control('skip')">Skip Current</button>
          <button class="btn" onclick="control('defer')">Defer Current</button>
          <button class="btn" onclick="control('requeue-current')">Requeue Current</button>
          <button class="btn bad" onclick="control('mark-bad', true)">Mark Capture Bad</button>
          <button class="btn" onclick="control('requeue-latest')">Requeue Latest</button>
        </div>
      </article>

      <article class="card health"><h2>System Health</h2>
        <div class="health-grid">
          <div class="mini"><div class="k">CPU temperature</div><div class="v" id="tempValue">-</div></div>
          <div class="mini"><div class="k">Fan speed</div><div class="v" id="fanSpeedValue">-</div></div>
          <div class="mini"><div class="k">Fan RPM</div><div class="v" id="fanRpmValue">-</div></div>
          <div class="mini"><div class="k">RAM available</div><div class="v" id="ramValue">-</div></div>
          <div class="mini"><div class="k">Swap in use</div><div class="v" id="swapValue">-</div></div>
          <div class="mini"><div class="k">1 min load</div><div class="v" id="loadValue">-</div></div>
        </div>
        <div class="health-foot"><strong id="healthHeadline">Checking system health...</strong><br><span id="healthDetail">-</span></div>
      </article>

      <article class="card metrics"><h2>Performance Snapshot</h2>
        <div class="metric-grid">
          <div class="metric"><div class="k">Processed</div><div class="v" id="processed">0/0</div><small>captures</small></div>
          <div class="metric"><div class="k">Cracked</div><div class="v" id="cracked">0</div><small>results</small></div>
          <div class="metric"><div class="k">Failed / timeout</div><div class="v" id="failed">0</div><small>results</small></div>
          <div class="metric"><div class="k">Words processed</div><div class="v" id="words">0</div><small>approximate</small></div>
          <div class="metric"><div class="k">Measured words/sec</div><div class="v" id="avgWps">0</div><small id="wpsDetail">waiting for aircrack sample</small></div>
          <div class="metric"><div class="k">Crack rate</div><div class="v" id="crackRate">0%</div><small>processed captures</small></div>
        </div>
        <div class="sparkrow">
          <div class="spark"><div class="label">Words / second</div><svg viewBox="0 0 100 40" preserveAspectRatio="none"><line class="gridline" x1="0" y1="32" x2="100" y2="32"/><polyline id="wpsSpark" class="line" points="0,32 100,32"/></svg></div>
          <div class="spark"><div class="label">Current wordlist progress</div><svg viewBox="0 0 100 40" preserveAspectRatio="none"><line class="gridline" x1="0" y1="32" x2="100" y2="32"/><polyline id="progressSpark" class="line" points="0,32 100,32"/></svg></div>
          <div class="spark"><div class="label">Job duration</div><svg viewBox="0 0 100 40" preserveAspectRatio="none"><line class="gridline" x1="0" y1="32" x2="100" y2="32"/><polyline id="elapsedSpark" class="line" points="0,32 100,32"/></svg></div>
        </div>
      </article>

      <article class="card queue"><h2>Queue & Recent Jobs</h2><div id="queueList" class="list"><div class="empty">Loading queue...</div></div></article>
      <article class="card mutator"><h2>Mutator Lab</h2><div class="mut-body">
        <div class="rule"><span>Mode / strategy</span><span id="mutMode">-</span></div>
        <div class="rule"><span>Candidate cap</span><span id="mutCap">-</span></div>
        <div class="rule"><span>Length filter</span><span id="mutLength">-</span></div>
        <div class="rule"><span>Last build</span><span id="mutLastBuild">-</span></div>
        <div class="rule"><span>Estimated pass time</span><span id="mutEstimate">-</span></div>
        <div class="rule"><span>Runs / candidates</span><span id="mutRuns">-</span></div>
        <div class="rule"><span>Cracks / share</span><span id="mutCracks">-</span></div>
        <div class="rule"><span>Custom seeds</span><span id="mutSeeds">-</span></div>
        <div class="rule"><span>Environment favorites</span><span id="mutFavs">-</span></div>
        <div class="rule"><span>Features</span><span id="mutFeatures">-</span></div>
        <div class="sub" id="mutCategorySummary">No mutator pass yet.</div>
        <div class="controls"><a class="btn" href="/mutator">Open Mutator Lab</a></div>
      </div></article>
      <article class="card lists"><h2>Wordlist Effectiveness</h2><div id="wordlistList" class="list"><div class="empty">Collecting statistics...</div></div></article>

      <article class="card activity"><h2>Activity Timeline</h2><div id="activityList" class="list"><div class="empty">No jobs yet.</div></div></article>
      <article class="card logs"><h2>Live Plugin Logs</h2><div id="logBox" class="logbox">Loading logs...</div></article>
    </section>
    <div class="foot">SkyGotchi Command Center  |  all dashboard assets are embedded for offline use  |  refreshes every 5 seconds</div>
  </main>
<script>
  const $ = id => document.getElementById(id);
  const safe = value => String(value ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  const fmtSeconds = s => { s = Math.max(0, Number(s)||0); if(s<60)return Math.round(s)+'s'; if(s<3600)return Math.floor(s/60)+'m '+Math.round(s%60)+'s'; return Math.floor(s/3600)+'h '+Math.floor((s%3600)/60)+'m'; };
  function formatCompact(value){ const n=Number(value)||0; const a=Math.abs(n); if(a>=1e9)return (n/1e9).toFixed(a>=10e9?0:1).replace(/\.0$/,'')+'G'; if(a>=1e6)return (n/1e6).toFixed(a>=10e6?0:1).replace(/\.0$/,'')+'M'; if(a>=1e3)return (n/1e3).toFixed(a>=10e3?0:1).replace(/\.0$/,'')+'K'; return Math.round(n).toLocaleString('en-US'); }
  function stateClass(status){ const s=String(status||'').toLowerCase(); if(s.includes('pause')||s.includes('hold')||s.includes('timeout'))return 'warn'; if(s.includes('fail')||s.includes('bad')||s.includes('error'))return 'bad'; if(s.includes('brute')||s.includes('run')||s.includes('done')||s.includes('crack'))return 'good'; return 'blue'; }
  function spark(id, values){ const arr=(values||[]).slice(-48).map(Number).filter(v=>Number.isFinite(v)); if(!arr.length){$(id).setAttribute('points','0,32 100,32');return;} const max=Math.max(...arr,1), min=Math.min(...arr,0), range=Math.max(max-min,1); const pts=arr.map((v,i)=>{const x=arr.length===1?50:(i/(arr.length-1))*100; const y=36-((v-min)/range)*30; return x.toFixed(1)+','+y.toFixed(1);}); $(id).setAttribute('points',pts.join(' ')); }
  async function control(action, confirmIt=false){ if(confirmIt && !confirm('Mark the active capture as bad? It will be removed from the normal queue until requeued.')) return; try{ const r=await fetch('/api/control/'+encodeURIComponent(action),{method:'POST'}); const d=await r.json(); if(!r.ok) alert(d.error||'Action was not accepted.'); else refresh(); }catch(e){alert('Dashboard control failed: '+e);} }
  function fillQueue(data){ const out=[]; const current=data.current_job||{}; if(current.ssid||current.pcap) out.push(`<div class="item"><div><div class="title">NOW  |  ${safe(current.ssid||'?')}</div><div class="desc">${safe(current.pcap||'')}  |  ${safe(current.status||'')}  |  ${fmtSeconds(current.elapsed)}</div></div><div class="right">${safe(current.attempt||0)}/${safe(current.retry_limit||0)}</div></div>`); (data.queue||[]).forEach((q,i)=>out.push(`<div class="item"><div><div class="title">NEXT ${i+1}  |  ${safe(q.ssid||'?')}</div><div class="desc">${safe(q.file||'')}</div></div><div class="right">queued</div></div>`)); if(!(data.queue||[]).length && !(current.ssid||current.pcap)) out.push('<div class="empty">Queue is empty.</div>'); $('queueList').innerHTML=out.join(''); }
  function fillActivity(data){ const items=(data.job_history||[]).slice().reverse(); if(!items.length){$('activityList').innerHTML='<div class="empty">No job history yet.</div>';return;} $('activityList').innerHTML=items.map(j=>{const cls=stateClass(j.result);return `<div class="item"><div><div class="title">${safe(j.ssid||'?')}</div><div class="desc">${safe(j.pcap||'')}  |  ${safe(j.result||'')}</div></div><div class="right"><span class="badge ${cls}">${safe(j.result||'')}</span><br>${fmtSeconds(j.duration||0)}  |  ${safe(j.attempts||0)} attempt(s)</div></div>`}).join(''); }
  function fillWordlists(data){const items=data.wordlist_summary||[];if(!items.length){$('wordlistList').innerHTML='<div class="empty">No wordlist runs have been recorded yet.</div>';return;} $('wordlistList').innerHTML=items.map(w=>`<div class="item"><div><div class="title">${safe(w.label)}</div><div class="desc">${safe(w.cracks)}/${safe(w.runs)} cracks  |  ${safe(w.estimated_words_abbr)} estimated words</div></div><div class="right"><strong>${Number(w.confidence||0).toFixed(1)}%</strong><br>confidence</div></div>`).join('');}
  function fillLogs(data){const lines=data.log_tail||[];const box=$('logBox');const atBottom=box.scrollTop+box.clientHeight>=box.scrollHeight-8;box.textContent=lines.length?lines.join('\n'):'No plugin log entries yet.';if(atBottom)box.scrollTop=box.scrollHeight;}
  function setText(id,v){$(id).textContent=v;}
  async function refresh(){try{const r=await fetch('/api/metrics',{cache:'no-store'});if(!r.ok)return;const d=await r.json();const status=d.status||'IDLE'; const cls=stateClass(status); const dot=$('engineDot');dot.className='dot '+cls;setText('engineText',status);setText('queueStatus',(d.queue_depth||0)+' waiting  |  '+(d.processed_display||'0/0')+' processed');setText('governorStatus',d.governor_blocked?'HOLD: '+(d.governor_detail||''):(d.manual_paused?'MANUAL PAUSE':(d.governor_enabled?'READY':'DISABLED')));setText('lastRefresh',new Date().toLocaleTimeString());
      const job=d.current_job||{};setText('currentSsid',job.ssid||'Idle - queue is waiting for a capture');setText('currentPcap',job.pcap||'No active capture');const st=$('currentState');st.className='badge '+cls;st.textContent=status;const p=Math.max(0,Math.min(100,Number(d.current_wordlist_progress||0)));$('currentProgress').style.width=p+'%';setText('currentProgressText',p.toFixed(0)+'%');setText('currentWordlist',d.current_wordlist_label||'Waiting');setText('currentAttempt',(job.attempt||0)+' / '+(job.retry_limit||0));setText('currentElapsed',fmtSeconds(job.elapsed||0));
      const rs=d.resources||{};const fan=rs.fan||{};setText('tempValue',rs.temp_f==null?'n/a':Number(rs.temp_f).toFixed(1)+' F');const fanLive=fan.available&&!fan.stale;setText('fanSpeedValue',fanLive&&fan.fan_percent!=null?Math.round(Number(fan.fan_percent))+'%':(fan.available?'STALE':'n/a'));setText('fanRpmValue',fanLive&&fan.fan_rpm!=null?Math.round(Number(fan.fan_rpm)).toLocaleString():(fan.available?'STALE':'n/a'));setText('ramValue',(rs.available_mem_mb??0)+' MB');setText('swapValue',(rs.swap_used_mb??0)+' MB');setText('loadValue',Number(rs.load_1m??0).toFixed(2));setText('healthHeadline',d.governor_blocked?'Governor hold active':(d.manual_paused?'Queue manually paused':'System ready'));setText('healthDetail',d.resource_summary||d.governor_detail||'-');
      setText('processed',d.processed_display||'0/0');setText('cracked',d.cracked_count??0);setText('failed',d.failed_count??0);setText('words',d.words_processed||0);const liveWps=Number(d.current_wps||0);const lastWps=Number(d.last_completed_wps||0);const avgWps=Number(d.avg_wps||0);const shownWps=liveWps||lastWps||avgWps;setText('avgWps',formatCompact(shownWps));const rawWps=Number(d.current_aircrack_reported_wps||0);let wpsLabel='waiting for tested-key sample';if(liveWps>0){wpsLabel='measured: '+(d.current_wps_source||'keys/time');}else if(lastWps>0){wpsLabel='last job: tested keys / elapsed';}else if(rawWps>0){wpsLabel='aircrack reports '+formatCompact(rawWps)+'/s (unverified)';}setText('wpsDetail',wpsLabel);setText('crackRate',Number(d.crack_rate||0).toFixed(1)+'%');spark('wpsSpark',d.wps_data);spark('progressSpark',d.progress_data);spark('elapsedSpark',d.elapsed_time_data);
      const ml=d.mutator_lab||{}; const mlc=ml.config||{}; const mll=ml.last_generation||{};setText('mutMode',(d.mutator_enabled?'Enabled':'Disabled')+' | '+(ml.strategy||d.mutator_profile||'smart'));setText('mutCap',(d.mutator_max_words||0)+' / SSID');setText('mutLength',(mlc.min_length||8)+'-'+(mlc.max_length||63)+' chars');setText('mutLastBuild',mll.ssid?(mll.ssid+' | '+formatCompact(mll.count||0)+' candidates'):'Waiting for first build');setText('mutEstimate',ml.estimated_seconds_text||'Waiting for WPS sample');setText('mutRuns',(d.mutator_runs||0)+' / '+(d.mutator_words_abbr||0));setText('mutCracks',(d.mutator_cracks||0)+' / '+Number(d.mutator_share||0).toFixed(1)+'%');setText('mutSeeds',(mlc.custom_words_count||0)+' words | '+(mlc.custom_prefixes_count||0)+' prefixes | '+(mlc.custom_suffixes_count||0)+' suffixes');setText('mutFavs',d.mutator_env_count||0);setText('mutFeatures',d.mutator_features||'none');const cats=(ml.category_rows||[]).slice(0,4).map(x=>x.name+': '+formatCompact(x.count||0)).join(' | ');setText('mutCategorySummary',cats||'No mutator pass yet.');
      fillQueue(d);fillActivity(d);fillWordlists(d);fillLogs(d);
    }catch(e){console.error(e);setText('engineText','Dashboard API unavailable');$('engineDot').className='dot bad';}}
  refresh();setInterval(refresh,5000);
</script>
</body>
</html>
"""


MUTATOR_LAB_HTML = r"""
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>SkyGotchi Mutator Lab</title><style>
:root{--bg:#071019;--panel:#0d1b2a;--line:#1d3852;--text:#e5eef7;--muted:#8ba1b8;--blue:#61b6ff;--green:#38d996}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top right,#123151 0,#071019 44%);color:var(--text);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}.shell{max-width:1500px;margin:auto;padding:18px}.top,.card{border:1px solid var(--line);background:linear-gradient(180deg,#0d1b2a,#081420);border-radius:14px;padding:15px}.top{display:flex;gap:12px;justify-content:space-between;align-items:center;flex-wrap:wrap}.top h1{font-size:1.15rem;letter-spacing:.08em;margin:0}.sub{color:var(--muted);font-size:.74rem;margin-top:6px}.btn{display:inline-block;color:var(--text);border:1px solid var(--line);background:#0b1724;padding:9px 11px;border-radius:9px;text-decoration:none;font-size:.73rem}.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px;margin-top:14px}.card h2{font-size:.75rem;color:#a8c2da;margin:0 0 12px;text-transform:uppercase;letter-spacing:.08em}.summary{grid-column:span 5}.categories{grid-column:span 4}.history{grid-column:span 3}.config{grid-column:span 12}.metricgrid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.metric{border:1px solid #16314a;background:#091624;border-radius:9px;padding:10px}.metric b{font-size:1.04rem}.metric span{display:block;color:var(--muted);font-size:.66rem;margin-top:4px}.row{display:flex;justify-content:space-between;gap:10px;padding:8px 0;border-bottom:1px dashed #1b344d;font-size:.75rem}.row:last-child{border:0}.row span:last-child{color:#bde0ff;text-align:right}.list{max-height:340px;overflow:auto}.bar{height:9px;background:#07111d;border:1px solid #17314a;border-radius:99px;overflow:hidden;margin-top:5px}.bar>i{display:block;height:100%;background:linear-gradient(90deg,#61b6ff,#b98cff)}.empty{color:var(--muted);font-size:.75rem}.table{width:100%;border-collapse:collapse;font-size:.72rem}.table th,.table td{padding:9px;text-align:left;border-bottom:1px solid #142b42}.table th{color:#9fb9d0;background:#0c1e2d}.tag{color:#9af0c7}.muted{color:var(--muted)}@media(max-width:900px){.summary,.categories,.history,.config{grid-column:span 12}.metricgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style></head><body><main class="shell"><header class="top"><div><h1>SKYGOTHCHI | MUTATOR LAB</h1><div class="sub">Candidate order, budgets, source categories, estimated pass time, and persistent run history</div></div><div><a class="btn" href="/">Command Center</a> <a class="btn" href="/intelligence">Intelligence</a> <a class="btn" href="/captures">Captures</a></div></header><section class="grid"><article class="card summary"><h2>Current Mutator</h2><div id="summary" class="metricgrid"></div><div id="last" class="sub" style="margin-top:12px"></div></article><article class="card categories"><h2>Last Candidate Mix</h2><div id="categories" class="list"></div></article><article class="card history"><h2>Recent Builds</h2><div id="history" class="list"></div></article><article class="card config"><h2>Active Tuning</h2><table class="table"><thead><tr><th>Setting</th><th>Value</th><th>What it changes</th></tr></thead><tbody id="configRows"></tbody></table></article></section></main><script>
const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));const n=v=>Number(v||0);function compact(v){const a=Math.abs(n(v));if(a>=1e6)return (n(v)/1e6).toFixed(1)+'M';if(a>=1e3)return (n(v)/1e3).toFixed(1)+'K';return Math.round(n(v)).toString()}function metric(v,k){return `<div class="metric"><b>${esc(v)}</b><span>${esc(k)}</span></div>`}async function load(){try{const d=await(await fetch('/api/mutator',{cache:'no-store'})).json(),c=d.config||{},l=d.last_generation||{};document.getElementById('summary').innerHTML=[metric(d.enabled?'Enabled':'Disabled','engine'),metric(d.strategy||'-','strategy'),metric((d.max_words||0)+' / SSID','candidate cap'),metric(d.estimated_seconds_text||'-','estimated pass time'),metric(compact(d.total_runs||0),'total runs'),metric(compact(d.total_candidates||0),'candidates generated')].join('');document.getElementById('last').textContent=l.ssid?`Last build: ${l.ssid} | ${compact(l.count)} candidates | ${l.created_text||'-'} | ${l.budget_pct||0}% of cap`:'No mutator build has been recorded yet.';const cats=d.category_rows||[];document.getElementById('categories').innerHTML=cats.length?cats.map(x=>`<div class="row"><div><b>${esc(x.name)}</b><div class="bar"><i style="width:${Math.min(100,n(x.percent))}%"></i></div></div><span>${compact(x.count)}<br><span class="muted">${n(x.percent).toFixed(1)}%</span></span></div>`).join(''):'<div class="empty">No candidate categories recorded yet.</div>';const hist=d.history||[];document.getElementById('history').innerHTML=hist.length?hist.slice().reverse().slice(0,12).map(x=>`<div class="row"><div><b>${esc(x.ssid||'?')}</b><div class="muted">${esc(x.created_text||'')}</div></div><span>${compact(x.count)}<br><span class="muted">${n(x.budget_pct).toFixed(0)}%</span></span></div>`).join(''):'<div class="empty">No builds yet.</div>';const rows=[['Strategy',d.strategy||'-','Orders lower-noise candidate families before broader ones.'],['Length filter',(c.min_length||8)+' to '+(c.max_length||63),'Drops candidates outside WPA passphrase length limits.'],['Token pairs',c.token_pairs?'on':'off','Adds small joined SSID token-pair candidates.'],['Numeric suffixes',c.numeric_suffixes?'on':'off','Uses digits already present in the SSID as suffixes.'],['Year range',(c.year_start||'-')+' to '+(c.year_end||'current'),'Controls compact year suffix generation.'],['Custom words',c.custom_words_count||0,'Local seed words added in config.'],['Custom prefixes',c.custom_prefixes_count||0,'Optional explicit prefixes.'],['Custom suffixes',c.custom_suffixes_count||0,'Optional explicit suffixes.'],['Favorite reuse',c.env_favorites?'on':'off','Reuses prior local successful strings when enabled.']];document.getElementById('configRows').innerHTML=rows.map(r=>`<tr><td>${esc(r[0])}</td><td class="tag">${esc(r[1])}</td><td class="muted">${esc(r[2])}</td></tr>`).join('')}catch(e){console.error(e)}}load();setInterval(load,5000);
</script></body></html>
"""

NETWORKS_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>BruteForcer Networks &amp; Wordlists</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
  <style>
    body {
      background: #0b1020;
      color: #e4e7ef;
    }
    .card {
      background: #151a2c;
      border: 1px solid #232a40;
      color: #e4e7ef;
    }
    table {
      font-size: 0.8rem;
    }
    thead {
      background: #1f2538;
    }
    .sub-label {
      font-size: 0.75rem;
      text-transform: uppercase;
      color: #9da5c6;
    }
  </style>
</head>
<body class="container-fluid py-3">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h2 class="mb-0">SSID &amp; Wordlist Stats</h2>
      <div class="sub-label">Historical cracking performance</div>
    </div>
    <div>
      <a href="/" class="btn btn-outline-info btn-sm">&larr; Back to Dashboard</a>
    </div>
  </div>

  <div class="card mb-3">
    <div class="card-header">Per-SSID Stats</div>
    <div class="card-body p-2">
      <div class="mb-2">
        <div class="btn-group btn-group-sm" role="group">
          <button type="button" class="btn btn-primary" data-filter="all">All</button>
          <button type="button" class="btn btn-outline-secondary" data-filter="cracked">Cracked</button>
          <button type="button" class="btn btn-outline-secondary" data-filter="failed">Failed</button>
          <button type="button" class="btn btn-outline-secondary" data-filter="pending">Pending</button>
          <button type="button" class="btn btn-outline-secondary" data-filter="timeout">Timeout</button>
        </div>
      </div>
      <div class="table-responsive">
        <table class="table table-sm table-striped table-dark align-middle mb-0">
          <thead>
            <tr>
              <th>SSID</th>
              <th>Attempts</th>
              <th>Status</th>
              <th>Success Wordlist</th>
              <th>Total Words</th>
              <th>Mut Words</th>
              <th>Mut Cracks</th>
              <th>Last Duration (s)</th>
              <th>Last Seen</th>
            </tr>
          </thead>
          <tbody>
            {% for ssid, s in ssid_stats.items() %}
              {% set attempts = s.attempts|default(0) %}
              {% set cracked = s.cracked|default(False) %}
              {% set last_result = s.last_result|default('') %}
              {% set mut = s.mutator|default({}) %}
              {% if cracked %}
                {% set row_status = 'cracked' %}
              {% elif last_result == 'Timeout' %}
                {% set row_status = 'timeout' %}
              {% elif last_result == 'Failed' %}
                {% set row_status = 'failed' %}
              {% else %}
                {% set row_status = 'pending' %}
              {% endif %}
              <tr data-status="{{ row_status }}">
                <td><a href="/ssid/{{ ssid|urlencode }}" class="link-light">{{ ssid }}</a></td>
                <td>{{ attempts }}</td>
                <td>
                  {% if cracked %}
                    <span class="badge bg-success">Cracked</span>
                  {% elif last_result == 'Timeout' %}
                    <span class="badge bg-warning text-dark">Timeout</span>
                  {% elif last_result %}
                    <span class="badge bg-secondary">{{ last_result }}</span>
                  {% else %}
                    <span class="badge bg-light text-dark">Unknown</span>
                  {% endif %}
                </td>
                <td>{{ s.success_wordlist|default('-') }}</td>
                <td>{{ s.total_words|default(0) }}</td>
                <td>{{ mut.total_words|default(0) }}</td>
                <td>{{ mut.cracks|default(0) }}</td>
                <td>{{ s.last_duration|default(0)|round(1) }}</td>
                <td>{{ s.last_seen|default('-') }}</td>
              </tr>
            {% else %}
              <tr>
                <td colspan="9" class="text-muted">No SSID stats yet.</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-header">Wordlist Effectiveness</div>
    <div class="card-body p-2">
      <div class="table-responsive">
        <table class="table table-sm table-striped table-dark align-middle mb-0">
          <thead>
            <tr>
              <th>Wordlist</th>
              <th>Runs</th>
              <th>Cracks</th>
              <th>Success %</th>
              <th>Confidence</th>
              <th>Est. Words Tried</th>
              <th>Avg Time</th>
            </tr>
          </thead>
          <tbody>
            {% for wl_name, w in wordlist_stats.items() %}
              {% set runs = w.runs|default(0) %}
              {% set cracks = w.cracks|default(0) %}
              {% if runs > 0 %}
                {% set rate = (cracks * 100.0 / runs) %}
              {% else %}
                {% set rate = 0 %}
              {% endif %}
              <tr>
                <td>{{ w.label }}</td>
                <td>{{ runs }}</td>
                <td>{{ cracks }}</td>
                <td>{{ rate|round(1) }}%</td>
                <td>{{ w.confidence|default(0)|round(1) }}%</td>
                <td>{{ w.estimated_words|default(0) }}</td>
                <td>{{ w.avg_duration|default(0)|round(1) }} s</td>
              </tr>
            {% else %}
              <tr>
                <td colspan="7" class="text-muted">No wordlist stats yet.</td>
              </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    document.addEventListener('DOMContentLoaded', function() {
      const buttons = document.querySelectorAll('[data-filter]');
      const rows = document.querySelectorAll('tbody tr[data-status]');
      buttons.forEach(btn => {
        btn.addEventListener('click', () => {
          const filter = btn.getAttribute('data-filter');
          buttons.forEach(b => {
            if (b === btn) {
              b.classList.remove('btn-outline-secondary');
              b.classList.add('btn-primary');
            } else {
              b.classList.remove('btn-primary');
              b.classList.add('btn-outline-secondary');
            }
          });
          rows.forEach(row => {
            const status = row.getAttribute('data-status');
            if (filter === 'all' || status === filter) {
              row.style.display = '';
            } else {
              row.style.display = 'none';
            }
          });
        });
      });
    });
  </script>
</body>
</html>
"""

SSID_DETAIL_HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>SSID Detail - {{ ssid }}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {
      background: #0b1020;
      color: #e4e7ef;
    }
    .card {
      background: #151a2c;
      border: 1px solid #232a40;
      color: #e4e7ef;
    }
    .sub-label {
      font-size: 0.75rem;
      text-transform: uppercase;
      color: #9da5c6;
    }
    .log-console {
      background: #050712;
      padding: 10px;
      border-radius: 6px;
      border: 1px solid #232a40;
      height: 280px;
      overflow-y: scroll;
      font-family: monospace;
      white-space: pre-wrap;
      font-size: 0.8rem;
      color: #c3c7e6;
    }
  </style>
</head>
<body class="container-fluid py-3">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h2 class="mb-0">SSID Detail</h2>
      <div class="sub-label">Per-SSID cracking history</div>
    </div>
    <div>
      <a href="/networks" class="btn btn-outline-info btn-sm">&larr; Back to SSID List</a>
    </div>
  </div>

  <div class="card mb-3">
    <div class="card-header">SSID: {{ ssid }}</div>
    <div class="card-body">
      {% if stats %}
        <div class="row">
          <div class="col-md-4">
            <div class="sub-label">Attempts</div>
            <div>{{ stats.attempts|default(0) }}</div>
          </div>
          <div class="col-md-4">
            <div class="sub-label">Last Result</div>
            <div>{{ stats.last_result|default('-') }}</div>
          </div>
          <div class="col-md-4">
            <div class="sub-label">Cracked</div>
            <div>
              {% if stats.cracked %}
                <span class="badge bg-success">Yes</span>
              {% else %}
                <span class="badge bg-secondary">No</span>
              {% endif %}
            </div>
          </div>
        </div>
        <div class="row mt-3">
          <div class="col-md-6">
            <div class="sub-label">Last Key (masked)</div>
            <div>{{ masked_key or '' }}</div>
          </div>
          <div class="col-md-6">
            <div class="sub-label">Success Wordlist</div>
            <div>{{ stats.success_wordlist|default('-') }}</div>
          </div>
        </div>
        <div class="row mt-3">
          <div class="col-md-4">
            <div class="sub-label">Total Words Tried</div>
            <div>{{ stats.total_words|default(0) }}</div>
          </div>
          <div class="col-md-4">
            <div class="sub-label">Last Duration (s)</div>
            <div>{{ stats.last_duration|default(0)|round(1) }}</div>
          </div>
          <div class="col-md-4">
            <div class="sub-label">Last Seen</div>
            <div>{{ stats.last_seen|default('-') }}</div>
          </div>
        </div>

        <div class="row mt-3">
          <div class="col-md-4">
            <div class="sub-label">Mutator runs</div>
            <div>{{ mutator.runs|default(0) }}</div>
          </div>
          <div class="col-md-4">
            <div class="sub-label">Mutator words total</div>
            <div>{{ mutator.total_words|default(0) }}</div>
          </div>
          <div class="col-md-4">
            <div class="sub-label">Mutator cracks</div>
            <div>{{ mutator.cracks|default(0) }}</div>
          </div>
        </div>

        {% set history = stats.history|default([]) %}
        <div class="mt-4">
          <div class="sub-label mb-1">Attempt History</div>
          {% if history %}
            <div class="table-responsive mb-3">
              <table class="table table-sm table-dark table-striped align-middle mb-0">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Time</th>
                    <th>Result</th>
                    <th>Wordlist</th>
                    <th>Duration (s)</th>
                    <th>Avg WPS</th>
                  </tr>
                </thead>
                <tbody>
                  {% for h in history %}
                    <tr>
                      <td>{{ h.attempt }}</td>
                      <td>{{ h.timestamp }}</td>
                      <td>{{ h.result }}</td>
                      <td>{{ h.wordlist }}</td>
                      <td>{{ h.duration|default(0)|round(1) }}</td>
                      <td>{{ h.avg_wps|default(0)|round(0) }}</td>
                    </tr>
                  {% endfor %}
                </tbody>
              </table>
            </div>
            <div class="row">
              <div class="col-md-6">
                <div class="sub-label mb-1">Attempt vs Duration</div>
                <canvas id="ssidAttemptTimeChart" height="80"></canvas>
              </div>
              <div class="col-md-6">
                <div class="sub-label mb-1">Attempt vs Avg WPS</div>
                <canvas id="ssidAttemptWpsChart" height="80"></canvas>
              </div>
            </div>
          {% else %}
            <div class="text-muted">No attempt history yet.</div>
          {% endif %}
        </div>
      {% else %}
        <p class="text-muted mb-0">No stats recorded for this SSID yet.</p>
      {% endif %}
    </div>
  </div>

  <div class="card">
    <div class="card-header">Logs for {{ ssid }}</div>
    <div class="card-body">
      <div class="log-console">
        {% if logs %}
          {% for line in logs %}
            {{ line }}<br>
          {% endfor %}
        {% else %}
          <span class="text-muted">No log lines for this SSID in the recent buffer.</span>
        {% endif %}
      </div>
    </div>
  </div>

  <script>
    document.addEventListener('DOMContentLoaded', function() {
      const history = {{ history_json|safe }};
      if (!Array.isArray(history) || !history.length) {
        return;
      }
      const attempts = history.map(h => h.attempt);
      const times = history.map(h => h.duration || 0);
      const wps = history.map(h => h.avg_wps || 0);

      const timeCtx = document.getElementById('ssidAttemptTimeChart').getContext('2d');
      const wpsCtx = document.getElementById('ssidAttemptWpsChart').getContext('2d');

      new Chart(timeCtx, {
        type: 'line',
        data: {
          labels: attempts,
          datasets: [{
            label: 'Duration (s)',
            data: times,
            tension: 0.3
          }]
        },
        options: {
          responsive: true,
          animation: false,
          plugins: { legend: { display: false }},
          scales: {
            x: { title: { display: true, text: 'Attempt #' } },
            y: { beginAtZero: true, title: { display: true, text: 'Seconds' } }
          }
        }
      });

      new Chart(wpsCtx, {
        type: 'line',
        data: {
          labels: attempts,
          datasets: [{
            label: 'Avg WPS',
            data: wps,
            tension: 0.3
          }]
        },
        options: {
          responsive: true,
          animation: false,
          plugins: { legend: { display: false }},
          scales: {
            x: { title: { display: true, text: 'Attempt #' } },
            y: { beginAtZero: true, title: { display: true, text: 'Words / second' } }
          }
        }
      });
    });
  </script>
</body>
</html>
"""



INTELLIGENCE_HTML = r"""
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SkyGotchi Intelligence</title><style>
:root{--bg:#071019;--panel:#0d1b2a;--line:#1d3852;--text:#e5eef7;--muted:#8ba1b8;--good:#38d996;--warn:#f7c65a;--bad:#ff6b6b;--blue:#61b6ff}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top right,#123151 0,#071019 44%);color:var(--text);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}.shell{max-width:1700px;margin:auto;padding:18px}.top{display:flex;justify-content:space-between;gap:12px;align-items:center;border:1px solid var(--line);background:#0d1b2a;padding:16px;border-radius:14px}.top h1{font-size:1.2rem;margin:0 0 5px}.sub{font-size:.75rem;color:var(--muted)}.btn{border:1px solid var(--line);background:#0b1724;color:var(--text);padding:9px 11px;border-radius:8px;font:inherit;font-size:.74rem;cursor:pointer}.grid{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px;margin-top:14px}.card{border:1px solid var(--line);background:#0d1b2a;border-radius:14px;padding:14px;min-width:0}.card h2{font-size:.75rem;color:#a8c2da;margin:0 0 12px;text-transform:uppercase;letter-spacing:.08em}.quality{grid-column:span 4}.queue{grid-column:span 8}.health{grid-column:span 7}.events{grid-column:span 5}.lab{grid-column:span 8}.mutator{grid-column:span 4}.duplicates{grid-column:span 6}.journal{grid-column:span 6}.cards{display:grid;grid-template-columns:repeat(5,1fr);gap:8px}.stat{border:1px solid #16314a;background:#091624;padding:12px;border-radius:10px}.stat b{font-size:1.4rem}.stat span{display:block;color:var(--muted);font-size:.66rem;margin-top:5px}.list{display:flex;flex-direction:column;gap:7px;max-height:350px;overflow:auto}.item{border:1px solid #18354e;background:#0a1826;border-radius:9px;padding:9px}.item b{font-size:.78rem}.muted{color:var(--muted);font-size:.7rem;margin-top:3px}.badge{display:inline-block;padding:4px 7px;border-radius:999px;border:1px solid var(--line);font-size:.65rem}.A,.B{background:#0a2c21;color:#a9f4cd}.C,.D{background:#3c2d08;color:#ffe29a}.X{background:#3d1b22;color:#ffb0b0}.tablewrap{overflow:auto;border:1px solid #16314a;border-radius:9px}.table{width:100%;border-collapse:collapse;font-size:.72rem}.table th,.table td{text-align:left;padding:9px;border-bottom:1px solid #17314a}.table th{color:#adcae2;background:#10253a;position:sticky;top:0}.chart{height:190px;border:1px solid #16314a;border-radius:10px;background:#091624;padding:10px}.chart svg{width:100%;height:100%}.legend{display:flex;gap:12px;flex-wrap:wrap;color:var(--muted);font-size:.67rem;margin-top:7px}@media(max-width:1000px){.quality,.queue,.health,.events,.lab,.mutator,.duplicates,.journal{grid-column:span 12}.cards{grid-template-columns:repeat(3,1fr)}}@media(max-width:600px){.shell{padding:10px}.top{align-items:flex-start;flex-direction:column}.cards{grid-template-columns:repeat(2,1fr)}}
</style></head><body><main class="shell"><header class="top"><div><h1>SKYGOTHCHI | INTELLIGENCE</h1><div class="sub">Capture quality, adaptive queue, resource history, wordlist lab, journal, and e-paper preview</div></div><div><a class="btn" href="/">Command Center</a> <a class="btn" href="/captures">Captures</a> <a class="btn" href="/reports">Reports</a></div></header><section class="grid">
<article class="card quality"><h2>Capture Quality</h2><div class="cards" id="quality">Loading...</div><div class="muted" id="captureTotal"></div></article>
<article class="card queue"><h2>Adaptive Queue <span id="queueMode" class="badge">Loading</span></h2><div class="list" id="queue"></div></article>
<article class="card health"><h2>Heat / RAM / Swap / Load History</h2><div class="chart"><svg id="healthChart" viewBox="0 0 1000 180" preserveAspectRatio="none"></svg></div><div class="legend">Blue temperature F | Green available RAM MB | Yellow swap MB | Purple load x20</div></article>
<article class="card events"><h2>Decision Timeline</h2><div class="list" id="events"></div></article>
<article class="card lab"><h2>Wordlist Lab</h2><div class="muted" id="recommendation"></div><div class="tablewrap"><table class="table"><thead><tr><th>Wordlist</th><th>Runs</th><th>Cracks</th><th>Confidence</th><th>Est. words</th><th>Avg sec</th><th>Verdict</th></tr></thead><tbody id="lab"></tbody></table></div></article>
<article class="card mutator"><h2>Mutator Pattern Breakdown</h2><div class="list" id="mutator"></div></article>
<article class="card duplicates"><h2>Duplicate Groups</h2><div class="list" id="duplicates"></div></article>
<article class="card journal"><h2>Crash-safe Journal / E-paper</h2><div id="journal" class="muted">Loading...</div><hr style="border-color:#17314a"><div class="muted">E-paper preview</div><div id="epaper" style="font-size:1.05rem;margin-top:7px"></div></article>
</section></main><script>
const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));function line(points,key,color,scale){if(!points.length)return '';let vals=points.map(p=>Number(p[key]||0)),max=Math.max(...vals,1);return `<polyline fill="none" stroke="${color}" stroke-width="3" points="${vals.map((v,i)=>`${i/(Math.max(vals.length-1,1))*1000},${170-(v/(max*scale))*155}`).join(' ')}"/>`}function draw(points){const svg=document.getElementById('healthChart');svg.innerHTML='<line x1="0" y1="170" x2="1000" y2="170" stroke="#17314a"/><line x1="0" y1="90" x2="1000" y2="90" stroke="#17314a"/>'+line(points,'temp_f','#61b6ff',1)+line(points,'available_mem_mb','#38d996',1)+line(points,'swap_used_mb','#f7c65a',1)+line(points,'load_1m','#b98cff',.05)}async function load(){try{let d=await (await fetch('/api/intelligence',{cache:'no-store'})).json();let q=d.quality_counts||{};document.getElementById('quality').innerHTML=['A','B','C','D','X'].map(g=>`<div class="stat"><b class="${g}">${g}: ${q[g]||0}</b><span>quality grade</span></div>`).join('');document.getElementById('captureTotal').textContent=(d.capture_total||0)+' captures indexed | dedupe '+(d.dedupe_auto_skip?'auto hold ON':'display only');document.getElementById('queueMode').textContent=d.adaptive_queue_enabled?'ADAPTIVE ON':'LEGACY ORDER';document.getElementById('queue').innerHTML=(d.top_queue||[]).map(i=>`<div class="item"><b>${esc(i.ssid)} <span class="badge ${esc((i.quality||{}).grade||'D')}">${esc((i.quality||{}).grade||'?')}</span> | priority ${esc(i.priority)}</b><div class="muted">${esc(i.file)} | ${(i.priority_reasons||[]).join(', ')}</div></div>`).join('')||'<div class="muted">Queue is empty.</div>';draw(d.resource_history||[]);document.getElementById('events').innerHTML=(d.events||[]).slice().reverse().map(e=>`<div class="item"><b>${esc(e.time)} | ${esc(e.kind)}</b><div class="muted">${esc(e.message)}</div></div>`).join('')||'<div class="muted">Events will appear as the engine works.</div>';let lab=(d.wordlist_lab||{});document.getElementById('recommendation').textContent=lab.recommendation||'';document.getElementById('lab').innerHTML=(lab.rows||[]).map(r=>`<tr><td>${esc(r.label)}</td><td>${r.runs}</td><td>${r.cracks}</td><td>${r.confidence}%</td><td>${esc(r.estimated_words_abbr)}</td><td>${r.avg_duration}</td><td>${esc(r.verdict)}</td></tr>`).join('')||'<tr><td colspan="7">No wordlist samples yet.</td></tr>';document.getElementById('mutator').innerHTML=(d.mutator||[]).map(m=>`<div class="item"><b>${esc(m.name)} | ${m.enabled?'ON':'OFF'}</b><div class="muted">${esc(m.detail)}</div></div>`).join('');document.getElementById('duplicates').innerHTML=(d.duplicates||[]).map(g=>`<div class="item"><b>${g.count} matching captures | best: ${esc(g.best)}</b><div class="muted">${esc((g.files||[]).join(', '))}</div></div>`).join('')||'<div class="muted">No duplicate groups found.</div>';let j=d.journal||{},rec=d.recovery_note||'';document.getElementById('journal').innerHTML=rec?'<b>'+esc(rec)+'</b>':(j.active?`Active: ${esc(j.stage||'working')} | ${esc(j.ssid||'?')} | ${esc(j.wordlist||'')}`:'No unfinished job journal.');document.getElementById('epaper').textContent=d.epaper_preview||'-'}catch(e){console.error(e)}}load();setInterval(load,7000);
</script></body></html>
"""

REPORTS_HTML = r"""
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SkyGotchi Reports</title><style>
:root{--bg:#071019;--panel:#0d1b2a;--line:#1d3852;--text:#e5eef7;--muted:#8ba1b8;--good:#38d996;--warn:#f7c65a;--blue:#61b6ff}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top right,#123151 0,#071019 44%);color:var(--text);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}.shell{max-width:1200px;margin:auto;padding:18px}.top{display:flex;justify-content:space-between;gap:12px;align-items:center;border:1px solid var(--line);background:#0d1b2a;padding:16px;border-radius:14px}.top h1{font-size:1.2rem;margin:0 0 5px}.sub{font-size:.75rem;color:var(--muted)}.btn{border:1px solid var(--line);background:#0b1724;color:var(--text);padding:9px 11px;border-radius:8px;font:inherit;font-size:.74rem}.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}.card{border:1px solid var(--line);background:#0d1b2a;border-radius:14px;padding:14px}.card h2{font-size:.8rem;color:#a8c2da;margin:0 0 12px;text-transform:uppercase}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}.metric{border:1px solid #16314a;background:#091624;border-radius:10px;padding:12px}.metric b{font-size:1.1rem}.metric span{display:block;color:var(--muted);font-size:.67rem;margin-top:5px}.muted{color:var(--muted);font-size:.75rem;margin-top:5px}@media(max-width:800px){.grid{grid-template-columns:1fr}.shell{padding:10px}.top{align-items:flex-start;flex-direction:column}}
</style></head><body><main class="shell"><header class="top"><div><h1>SKYGOTHCHI | DAILY AND WEEKLY REPORTS</h1><div class="sub" id="stamp">Loading...</div></div><div><a class="btn" href="/">Command Center</a> <a class="btn" href="/intelligence">Intelligence</a></div></header><section class="grid"><article class="card" id="today"></article><article class="card" id="week"></article></section></main><script>const esc=v=>String(v??'');function card(r){let x=r.results||{};return `<h2>${esc(r.label)}</h2><div class="metrics"><div class="metric"><b>${r.jobs||0}</b><span>jobs</span></div><div class="metric"><b>${x.Cracked||0}</b><span>cracked</span></div><div class="metric"><b>${x.Failed||0}</b><span>failed</span></div><div class="metric"><b>${x.Timeout||0}</b><span>timeout</span></div><div class="metric"><b>${esc(r.avg_wps_abbr||'0')}/s</b><span>avg sample speed</span></div><div class="metric"><b>${r.peak_temp_f||0} F</b><span>peak temperature</span></div></div><div class="muted">Avg job ${r.avg_duration||0}s | Total work ${r.total_duration||0}s | Peak load ${r.peak_load||0} | Peak swap ${r.peak_swap_mb||0} MB</div>`}async function load(){let d=await(await fetch('/api/reports',{cache:'no-store'})).json();document.getElementById('today').innerHTML=card(d.today||{});document.getElementById('week').innerHTML=card(d.week||{});document.getElementById('stamp').textContent='Generated '+(d.generated_at||'')}load();setInterval(load,30000);</script></body></html>
"""

CAPTURES_HTML = r"""
<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SkyGotchi Capture Intelligence</title>
<style>
:root{--bg:#071019;--panel:#0d1b2a;--line:#1d3852;--text:#e5eef7;--muted:#8ba1b8;--good:#38d996;--warn:#f7c65a;--bad:#ff6b6b;--blue:#61b6ff;--purple:#b98cff}*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at top right,#123151 0,#071019 44%);color:var(--text);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}.shell{max-width:1700px;margin:auto;padding:18px}.top{display:flex;justify-content:space-between;gap:12px;align-items:center;border:1px solid var(--line);background:#0d1b2a;padding:16px;border-radius:14px}.top h1{font-size:1.2rem;margin:0 0 5px}.sub{font-size:.75rem;color:var(--muted)}.btn,.filter{border:1px solid var(--line);background:#0b1724;color:var(--text);padding:9px 11px;border-radius:8px;font:inherit;font-size:.74rem}.btn{cursor:pointer}.btn:hover{border-color:var(--blue)}.filters{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}.filter{min-width:150px}.count{border:1px solid var(--line);background:#0a1725;padding:8px 10px;border-radius:999px;font-size:.7rem;color:#b8cce0}.tablewrap{border:1px solid var(--line);background:#0d1b2a;border-radius:12px;overflow:auto}.table{width:100%;border-collapse:collapse;font-size:.73rem}.table th{position:sticky;top:0;background:#10253a;color:#adcae2;text-align:left;padding:10px}.table td{padding:10px;border-top:1px solid #17314a;vertical-align:top}.table tr:hover td{background:#0f2234}.badge{display:inline-block;padding:4px 7px;border-radius:999px;border:1px solid var(--line);font-size:.65rem}.pending{background:#0c2945;color:#acd9ff}.running,.cracked,.a,.b{background:#0a2c21;color:#a9f4cd}.failed,.bad,.x{background:#3d1b22;color:#ffb0b0}.timeout,.deferred,.review,.c,.d{background:#3c2d08;color:#ffe29a}.muted{color:var(--muted)}.empty{padding:24px;color:var(--muted)}.grade{font-weight:900;font-size:.9rem}@media(max-width:850px){.shell{padding:10px}.top{align-items:flex-start;flex-direction:column}.table{font-size:.68rem}.hide-sm{display:none}}
</style></head><body><main class="shell"><header class="top"><div><h1>SKYGOTHCHI | CAPTURE INTELLIGENCE</h1><div class="sub">Quality grades, duplicate grouping, queue priority, history, and safe requeue controls</div></div><div><a class="btn" href="/">Command Center</a> <a class="btn" href="/intelligence">Intelligence</a> <a class="btn" href="/reports">Reports</a></div></header>
<section class="filters"><select id="status" class="filter" onchange="loadCaptures()"><option value="all">All states</option><option value="pending">Pending</option><option value="running">Running</option><option value="cracked">Cracked</option><option value="failed">Failed</option><option value="timeout">Timeout</option><option value="bad">Bad capture</option><option value="review">Needs review</option><option value="deferred">Deferred</option></select><input id="q" class="filter" placeholder="Search SSID or filename" oninput="debounced()"><button class="btn" onclick="loadCaptures()">Reload</button><span class="count" id="count">Loading...</span></section>
<div class="tablewrap"><table class="table"><thead><tr><th>State</th><th>Quality</th><th>SSID</th><th>Capture</th><th class="hide-sm">Priority</th><th class="hide-sm">Duplicates</th><th class="hide-sm">Attempts</th><th class="hide-sm">Health / queue note</th><th>Action</th></tr></thead><tbody id="rows"><tr><td colspan="9" class="empty">Loading capture library...</td></tr></tbody></table></div></main>
<script>
const esc=v=>String(v??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));let timer;function debounced(){clearTimeout(timer);timer=setTimeout(loadCaptures,250)}function stateClass(s){s=String(s||'').toLowerCase();if(['running','cracked'].includes(s))return s;if(['failed','bad'].includes(s))return s;if(['timeout','deferred','review'].includes(s))return s;return 'pending'}async function requeue(path){if(!confirm('Requeue this capture for the normal queue?'))return;const r=await fetch('/api/requeue?path='+encodeURIComponent(path),{method:'POST'});const d=await r.json();if(!r.ok)alert(d.error||'Could not requeue capture');else loadCaptures()}async function loadCaptures(){const st=document.getElementById('status').value,q=document.getElementById('q').value;try{const r=await fetch('/api/captures?status='+encodeURIComponent(st)+'&q='+encodeURIComponent(q),{cache:'no-store'});const d=await r.json();document.getElementById('count').textContent=(d.total||0)+' captures | '+(d.generated_at||'');const items=d.items||[],rows=document.getElementById('rows');if(!items.length){rows.innerHTML='<tr><td colspan="9" class="empty">No captures match this filter.</td></tr>';return}rows.innerHTML=items.map(i=>{const q=i.quality||{},g=String(q.grade||'?').toLowerCase(),dup=i.duplicate||{};return `<tr><td><span class="badge ${stateClass(i.state)}">${esc(i.state)}</span></td><td><span class="badge grade ${g}">${esc(q.grade||'?')}</span><div class="muted">${esc(q.score||0)}/100</div></td><td><a href="/ssid/${encodeURIComponent(i.ssid||'')}" style="color:#bde0ff">${esc(i.ssid||'?')}</a></td><td>${esc(i.file||'')}<div class="muted">${Math.round(i.size_kb||0)} KB</div></td><td class="hide-sm">${esc(i.priority||'-')}</td><td class="hide-sm">${dup.count>1?esc(dup.count+' captures'+(dup.is_best?' | best':' | duplicate')):'-'}</td><td class="hide-sm">${esc(i.attempts||0)}</td><td class="hide-sm">${esc(i.note||'-')}<div class="muted">${esc((q.reasons||[]).join('; '))}</div></td><td><button class="btn" onclick="requeue('${String(i.path||'').replace(/'/g,"\\'")}')">Requeue</button></td></tr>`}).join('')}catch(e){document.getElementById('rows').innerHTML='<tr><td colspan="9" class="empty">Could not load capture library.</td></tr>';console.error(e)}}loadCaptures();
</script></body></html>
"""


class BruteForce(plugins.Plugin):
    __author__ = 'SKY'
    __version__ = '3.3.0'
    __license__ = 'GPL3'
    __description__ = 'Pwnagotchi BruteForcer command center for authorized WPA/WPA2 recovery testing with aircrack-ng.'

    def __init__(self):
        # Status and progress
        self.status = "IDLE"
        self.progress = "0%"
        self.result = ""
        self.ui = None
        self.lock = threading.Lock()
        self.stop_event = threading.Event()

        # Handshake/file tracking
        self.processed_files = 0
        self.total_files = 0
        self.processed_files_set: Set[str] = set()

        # Cracking counters
        self.cracked_count = 0
        self.failed_count = 0
        self.retry_limit = 3

        # Wordlist attempts (for internal stats)
        self.wordlist_attempts = 0

        # Words processed (approximate integration of WPS over time)
        self.words_processed = 0
        self.words_processed_abbr = ""
        self.last_wps_update_time: Optional[float] = None
        # Candidate-rate telemetry. The dashboard treats Aircrack's printed
        # k/s as a diagnostic only. The displayed rate is measured from the
        # tested-key counter divided by elapsed time.
        self.current_wps = 0.0
        self.current_wps_source = "waiting"
        self.current_wps_confidence = "waiting"
        self.current_aircrack_reported_wps = 0.0
        self.current_wps_difference_pct = None
        self.current_wordlist_started_monotonic: Optional[float] = None
        self.current_wordlist_aircrack_seconds: Optional[float] = None
        self.current_wordlist_keys_tested = 0
        self.current_wordlist_accounted_keys = 0
        self.last_keys_tested: Optional[int] = None
        self.last_keys_tested_time: Optional[float] = None
        self.last_completed_wps = 0.0
        self.last_completed_keys_tested = 0
        self.last_completed_duration = 0.0

        # Graph data
        self.wps_data = []
        self.progress_data = []
        self.elapsed_time_data = []
        self.max_data_points = 500

        # Status
        self.status_message = ""
        self.current_task: Optional[subprocess.Popen] = None

        # Per-SSID and wordlist stats
        self.ssid_stats = {}
        self.wordlist_stats = {}

        # Env favorites (per-environment mini wordlist)
        self.env_favorites = {}            # password -> score
        self.env_favorites_max = 1000
        self.env_favorites_path = "/tmp/bruteforce_env_favorites.txt"

        # Last cracked info
        self.last_cracked_ssid = ""
        self.last_cracked_key = ""

        # Current handshake info
        self.current_pcap = None
        self.current_ssid = None

        # Plugin config defaults
        self.handshake_dir = "/home/pi/handshakes"
        self.wordlist_folder = "/home/pi/wordlists"
        self.delay_between_attempts = 5
        self.progress_file = "/root/bruteforce_progress.json"
        self.wordlist_profiles = None  # optional list of {path, mode}

        # Mutator config
        self.mutator_enabled = True
        self.mutator_max_words = 50000
        self.mutator_paths = {}   # ssid -> set(paths)
        self.mutator_include_base64 = True
        self.mutator_include_years = True
        self.mutator_leet_mode = "light"  # off / light / heavy

        # New mutator tuning options
        self.mutator_include_rot13 = True
        self.mutator_include_hex = False
        self.mutator_include_separators = True
        self.mutator_include_reversed = True
        self.mutator_include_case_swaps = True
        self.mutator_use_env_favorites = True
        self.mutator_ssid_splits = True

        # Track SSIDs where mutator has errored; skip them in future
        self.mutator_error_ssids: Set[str] = set()

        # Optional custom seed words & profile
        self.mutator_custom_words = []
        # fast / balanced / heavy - only affects defaults,
        # explicit per-flag config still wins.
        self.mutator_profile = "balanced"
        # v3.3 Mutator Lab controls. Defaults keep a modest, Pi-friendly pass.
        self.mutator_strategy = "smart"  # smart / compatibility / thorough
        self.mutator_min_length = 8
        self.mutator_max_length = 63
        self.mutator_include_token_pairs = False
        self.mutator_token_pair_limit = 6
        self.mutator_include_numeric_suffixes = True
        self.mutator_year_start = 2020
        self.mutator_year_end = 0  # 0 means current year
        self.mutator_custom_prefixes = []
        self.mutator_custom_suffixes = []
        self.mutator_preview_count = 12
        self.mutator_last_generation = {}
        self.mutator_generation_history = []
        self.max_mutator_generation_history = 60
        self.mutator_feature_totals = {}

        # Ring buffer for logs
        self.log_buffer = []
        self.max_log_buffer_size = 100

        # Job history / current job tracking
        self.job_history = []
        self.max_job_history = 50
        self.current_job_start: Optional[float] = None
        self.current_job_attempt = 0

        # Flask app
        self.app = Flask(__name__)
        self.dashboard_thread = threading.Thread(target=self.start_dashboard, daemon=True)

        # Dashboard port (can be overridden in config)
        self.dashboard_port = DASHBOARD_PORT_DEFAULT

        # Runtime control: these defaults preserve the prior behavior until
        # the matching options are enabled in config.toml.
        self.manual_paused = False
        self.pause_detail = ""
        self.skip_current_requested = False
        self.defer_current_requested = False
        self.requeue_current_requested = False
        self.mark_bad_current_requested = False
        self.deferred_files = {}
        self.manual_priority_files = set()
        self.defer_seconds = 900
        self.skip_cooldown_seconds = 300

        # Resource governor. It only pauses between wordlists, never kills a
        # healthy in-progress run.
        self.governor_enabled = False
        self.governor_max_temp_c = 70.0
        self.governor_min_available_mem_mb = 75
        self.governor_max_swap_used_mb = 600
        self.governor_max_load_1m = 0.0
        self.governor_poll_seconds = 10
        self.governor_detail = "Governor disabled"
        self.governor_blocked = False
        self.last_resource_snapshot = {}

        # Capture preflight and metadata. Preflight detects clearly bad captures
        # before wordlists are run; unknown results proceed normally.
        self.preflight_enabled = False
        self.preflight_timeout = 15
        self.capture_health = {}
        self.ssid_overrides = {}

        # Better wordlist telemetry, used only for ranking/reporting.
        self.wordlist_line_count_enabled = False
        self.wordlist_line_counts = {}
        self.wordlist_min_runs_for_ranking = 3
        self.current_wordlist_key = ""
        self.current_wordlist_progress = 0.0

        # Intelligence Pack v3.2: passive analytics are on by default. The
        # scheduling / skip behavior remains opt-in so existing workloads keep
        # their current behavior until you enable the new controls.
        self.event_timeline = []
        self.max_event_timeline = 250
        self.resource_history = []
        self.max_resource_history = 240
        self._last_resource_history_at = 0.0
        self.capture_fingerprints = {}
        self.duplicate_groups = {}
        self._last_dedupe_scan_at = 0.0
        self.dedupe_scan_seconds = 45
        self.dedupe_auto_skip = False
        self.adaptive_queue_enabled = False
        self.adaptive_queue_max_bonus = 100
        self.journal_path = "/root/bruteforcer_job_journal.json"
        self.active_job_journal = {}
        self.recovery_note = ""
        self.epaper_status_mode = False
        self.epaper_status_max_chars = 34
        self.report_cache = {}

        # Fan telemetry comes from the fan_control plugin via a tiny status
        # file. This avoids tight coupling to the Pwnagotchi plugin loader
        # and works even when dashboard/fan reload at different times.
        self.fan_status_path = "/var/tmp/pwnagotchi/fan_status.json"
        self.fan_status_stale_seconds = 20
        self.last_fan_snapshot = {}

    # ------------------------------------------------------------------
    # Logging helpers
    # ------------------------------------------------------------------
    def _log_console(self, message, level='info'):
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        line = f"{timestamp} - {message}"
        self.log_buffer.append(line)

        if len(self.log_buffer) > self.max_log_buffer_size:
            self.log_buffer.pop(0)

        level_lower = level.lower()
        if hasattr(self, "event_timeline"):
            low = str(message).lower()
            if level_lower == "error" or any(token in low for token in ("[bruteforce]", "[preflight]", "[mutator]", "governor", "journal", "requeue", "crack")):
                self._record_event("engine", str(message), level_lower)
        if level_lower == 'info':
            logging.info(message)
        elif level_lower == 'error':
            logging.error(message)
        else:
            logging.debug(message)

    def _log_ssid(self, ssid, message, level='info'):
        tagged = f"[SSID:{ssid}] {message}"
        self._log_console(tagged, level)

    def _append_limited(self, data_list, value):
        data_list.append(value)
        if len(data_list) > self.max_data_points:
            data_list.pop(0)


    # ------------------------------------------------------------------
    # Intelligence Pack v3.2: event journal, quality scoring, dedupe,
    # adaptive queueing, reports, and compact e-paper status.
    # ------------------------------------------------------------------
    def _record_event(self, kind, message, severity="info", ssid="", extra=None):
        event = {
            "ts": time.time(),
            "time": time.strftime("%H:%M:%S"),
            "kind": str(kind or "event"),
            "severity": str(severity or "info"),
            "message": str(message or "")[:500],
            "ssid": str(ssid or ""),
        }
        if isinstance(extra, dict):
            event["extra"] = extra
        self.event_timeline.append(event)
        if len(self.event_timeline) > self.max_event_timeline:
            del self.event_timeline[:len(self.event_timeline) - self.max_event_timeline]

    def _record_resource_history(self, snapshot):
        now = time.time()
        if self.resource_history and now - self._last_resource_history_at < 5:
            return
        point = {
            "ts": now,
            "temp_f": snapshot.get("temp_f"),
            "available_mem_mb": int(snapshot.get("available_mem_mb", 0) or 0),
            "swap_used_mb": int(snapshot.get("swap_used_mb", 0) or 0),
            "load_1m": float(snapshot.get("load_1m", 0.0) or 0.0),
            "wps": float(getattr(self, "current_wps", 0.0) or 0.0),
            "fan_percent": (snapshot.get("fan") or {}).get("fan_percent"),
            "fan_rpm": (snapshot.get("fan") or {}).get("fan_rpm"),
        }
        self.resource_history.append(point)
        self._last_resource_history_at = now
        if len(self.resource_history) > self.max_resource_history:
            del self.resource_history[:len(self.resource_history) - self.max_resource_history]

    def _quick_capture_fingerprint(self, path):
        """Fast duplicate fingerprint: size plus a hash of the first/last 32 KiB."""
        try:
            st = os.stat(path)
            cache = self.capture_fingerprints.get(path, {})
            if (cache.get("mtime_ns") == st.st_mtime_ns and
                    cache.get("size") == st.st_size and cache.get("fingerprint")):
                return cache["fingerprint"]
            digest = hashlib.sha256()
            digest.update(str(st.st_size).encode("ascii"))
            with open(path, "rb") as handle:
                head = handle.read(32768)
                digest.update(head)
                if st.st_size > 65536:
                    handle.seek(max(0, st.st_size - 32768))
                    digest.update(handle.read(32768))
            fp = "%s:%s" % (st.st_size, digest.hexdigest()[:24])
            self.capture_fingerprints[path] = {"mtime_ns": st.st_mtime_ns, "size": st.st_size, "fingerprint": fp}
            return fp
        except Exception:
            return ""

    def _refresh_duplicate_index(self, force=False):
        now = time.time()
        if not force and self.duplicate_groups and now - self._last_dedupe_scan_at < self.dedupe_scan_seconds:
            return
        groups = {}
        try:
            for root, _dirs, files in os.walk(self.handshake_dir):
                for name in files:
                    if not name.endswith(".pcap"):
                        continue
                    path = os.path.join(root, name)
                    fp = self._quick_capture_fingerprint(path)
                    if fp:
                        groups.setdefault(fp, []).append(path)
        except Exception:
            pass
        indexed = {}
        for fp, paths in groups.items():
            if len(paths) < 2:
                continue
            ranked = []
            for path in paths:
                try:
                    st = os.stat(path)
                    ranked.append((st.st_size, st.st_mtime, path))
                except Exception:
                    ranked.append((0, 0, path))
            ranked.sort(reverse=True)
            best = ranked[0][2]
            indexed[fp] = {"paths": [r[2] for r in ranked], "best": best}
        self.duplicate_groups = indexed
        self._last_dedupe_scan_at = now

    def _duplicate_info(self, path):
        self._refresh_duplicate_index()
        fp = self._quick_capture_fingerprint(path)
        group = self.duplicate_groups.get(fp) if fp else None
        if not group:
            return {"count": 1, "is_best": True, "best": path, "group": ""}
        return {
            "count": len(group.get("paths", [])),
            "is_best": path == group.get("best"),
            "best": group.get("best", ""),
            "group": fp,
        }

    def _capture_quality(self, pcap_file, ssid=""):
        """Return a non-destructive A/B/C/D/X quality grade with reasons."""
        health = (self.capture_health or {}).get(pcap_file, {}) or {}
        status = str(health.get("status", "unknown") or "unknown").lower()
        try:
            size_kb = float(os.path.getsize(pcap_file)) / 1024.0
        except Exception:
            size_kb = 0.0
        score = 45.0
        reasons = []
        if status == "valid":
            score += 32; reasons.append("preflight valid")
        elif status in ("bad", "no_handshake", "marked_bad"):
            return {"grade": "X", "score": 0, "reasons": [health.get("detail") or status]}
        elif status == "needs_review":
            score -= 20; reasons.append("needs review")
        else:
            reasons.append("not preflighted")
        if size_kb >= 250:
            score += 15; reasons.append("substantial capture")
        elif size_kb >= 75:
            score += 8; reasons.append("usable file size")
        elif size_kb < 10:
            score -= 25; reasons.append("very small file")
        stats = (self.ssid_stats or {}).get(ssid, {}) or {}
        attempts = int(stats.get("attempts", 0) or 0)
        if attempts:
            score -= min(20, attempts * 4); reasons.append("%d prior attempt(s)" % attempts)
        dup = self._duplicate_info(pcap_file)
        if dup.get("count", 1) > 1:
            if dup.get("is_best"):
                reasons.append("best of %d duplicates" % dup["count"])
            else:
                score -= 18; reasons.append("duplicate of stronger capture")
        score = int(max(0, min(100, round(score))))
        grade = "A" if score >= 82 else "B" if score >= 68 else "C" if score >= 48 else "D"
        return {"grade": grade, "score": score, "reasons": reasons[:4]}

    def _adaptive_priority_details(self, pcap_file, ssid):
        stats = (self.ssid_stats or {}).get(ssid, {}) or {}
        attempts = int(stats.get("attempts", 0) or 0)
        last_result = str(stats.get("last_result", "") or "")
        quality = self._capture_quality(pcap_file, ssid)
        duplicate = self._duplicate_info(pcap_file)
        score = float(quality.get("score", 0))
        reasons = ["quality %s" % quality.get("grade", "?")]
        if attempts == 0:
            score += 22; reasons.append("new SSID")
        else:
            score -= min(30, attempts * 7)
        if last_result in ("Failed", "Timeout"):
            score -= 10; reasons.append("prior %s" % last_result.lower())
        if duplicate.get("count", 1) > 1 and not duplicate.get("is_best"):
            score -= 30; reasons.append("duplicate penalty")
        if pcap_file in self.manual_priority_files:
            score += 1000; reasons.append("manual requeue")
        try:
            mtime = os.path.getmtime(pcap_file)
        except Exception:
            mtime = 0.0
        return {"score": int(round(score)), "grade": quality.get("grade", "?"), "reasons": reasons, "mtime": mtime}

    def _write_atomic_json(self, path, payload):
        directory = os.path.dirname(path) or "."
        os.makedirs(directory, exist_ok=True)
        temp = path + ".tmp"
        with open(temp, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)

    def _journal_write(self, stage, pcap_file=None, ssid=None, wordlist="", attempt=None, detail=""):
        payload = {
            "active": True,
            "updated_at": time.time(),
            "stage": str(stage or "working"),
            "pcap": pcap_file or self.current_pcap or "",
            "ssid": ssid or self.current_ssid or "",
            "wordlist": wordlist or self.current_wordlist_key or "",
            "attempt": int(attempt if attempt is not None else self.current_job_attempt or 0),
            "progress": self.current_wordlist_progress or 0.0,
            "detail": str(detail or "")[:400],
        }
        self.active_job_journal = payload
        try:
            self._write_atomic_json(self.journal_path, payload)
        except Exception as exc:
            self._log_console("[journal] write failed: %s" % exc, "error")

    def _journal_clear(self, result=""):
        self.active_job_journal = {}
        try:
            if os.path.exists(self.journal_path):
                os.remove(self.journal_path)
        except Exception as exc:
            self._log_console("[journal] clear failed: %s" % exc, "error")
        if result:
            self._record_event("job", "Journal closed: %s" % result, "info")

    def _recover_interrupted_journal(self):
        if not os.path.exists(self.journal_path):
            return
        try:
            with open(self.journal_path, "r") as handle:
                info = json.load(handle)
            if not info.get("active"):
                return
            pcap = str(info.get("pcap") or "")
            ssid = str(info.get("ssid") or "?")
            if pcap and os.path.exists(pcap):
                self.recovery_note = "Interrupted job requeued: %s" % os.path.basename(pcap)
                self._record_event("recovery", self.recovery_note, "warn", ssid, info)
                # Capture was never finalized, so the normal queue will resume it.
            else:
                self.recovery_note = "Interrupted journal found; capture no longer present"
                self._record_event("recovery", self.recovery_note, "warn", ssid, info)
        except Exception as exc:
            self._log_console("[journal] recovery read failed: %s" % exc, "error")

    def _mutator_lab_snapshot(self):
        last = dict(self.mutator_last_generation or {})
        count = int(last.get("count", 0) or 0)
        cap = max(1, int(self.mutator_max_words or 1))
        categories = last.get("categories", {}) if isinstance(last.get("categories", {}), dict) else {}
        rows = []
        for name, value in categories.items():
            value = int(value or 0)
            rows.append({
                "name": str(name).replace("_", " ").title(),
                "count": value,
                "percent": round((value * 100.0 / count), 2) if count else 0.0,
            })
        rows.sort(key=lambda item: (-item["count"], item["name"]))
        rate = float(self.current_wps or self.last_completed_wps or 0.0)
        if rate > 0 and count > 0:
            estimate_seconds = count / rate
            if estimate_seconds < 60:
                estimate_text = "about %.1f s at %.0f WPS" % (estimate_seconds, rate)
            else:
                estimate_text = "about %.1f min at %.0f WPS" % (estimate_seconds / 60.0, rate)
        else:
            estimate_seconds = 0.0
            estimate_text = "waiting for measured WPS"
        history = []
        for item in (self.mutator_generation_history or [])[-20:]:
            if not isinstance(item, dict):
                continue
            copy = dict(item)
            ts = float(copy.get("created_at", 0) or 0)
            copy["created_text"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "-"
            history.append(copy)
        if last:
            ts = float(last.get("created_at", 0) or 0)
            last["created_text"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "-"
            last["budget_pct"] = round(min(100.0, count * 100.0 / cap), 1)
        config = {
            "min_length": int(self.mutator_min_length),
            "max_length": int(self.mutator_max_length),
            "token_pairs": bool(self.mutator_include_token_pairs),
            "token_pair_limit": int(self.mutator_token_pair_limit),
            "numeric_suffixes": bool(self.mutator_include_numeric_suffixes),
            "year_start": int(self.mutator_year_start),
            "year_end": int(self.mutator_year_end or time.localtime().tm_year),
            "custom_words_count": len(self.mutator_custom_words or []),
            "custom_prefixes_count": len(self.mutator_custom_prefixes or []),
            "custom_suffixes_count": len(self.mutator_custom_suffixes or []),
            "env_favorites": bool(self.mutator_use_env_favorites),
        }
        return {
            "enabled": bool(self.mutator_enabled),
            "strategy": self.mutator_strategy,
            "max_words": int(self.mutator_max_words),
            "total_runs": int(sum(int((s.get("mutator", {}) or {}).get("runs", 0) or 0) for s in (self.ssid_stats or {}).values() if isinstance(s, dict))),
            "total_candidates": int(sum(int((s.get("mutator", {}) or {}).get("total_words", 0) or 0) for s in (self.ssid_stats or {}).values() if isinstance(s, dict))),
            "estimated_seconds": round(estimate_seconds, 2),
            "estimated_seconds_text": estimate_text,
            "last_generation": last,
            "category_rows": rows,
            "history": history,
            "config": config,
            "feature_totals": dict(self.mutator_feature_totals or {}),
        }

    def _mutator_breakdown(self):
        return [
            {"name": "Strategy", "enabled": True, "detail": self.mutator_strategy},
            {"name": "SSID core + token splits", "enabled": True, "detail": "base forms and SSID tokens"},
            {"name": "Token pairs", "enabled": bool(self.mutator_include_token_pairs), "detail": "up to %d joined pairs" % int(self.mutator_token_pair_limit)},
            {"name": "Separators", "enabled": bool(self.mutator_include_separators), "detail": "space, dash, underscore, dot"},
            {"name": "Years + common suffixes", "enabled": bool(self.mutator_include_years), "detail": "%d-%d" % (int(self.mutator_year_start), int(self.mutator_year_end or time.localtime().tm_year))},
            {"name": "Numeric SSID suffixes", "enabled": bool(self.mutator_include_numeric_suffixes), "detail": "numbers present in SSID"},
            {"name": "Light leet", "enabled": self.mutator_leet_mode != "off", "detail": self.mutator_leet_mode},
            {"name": "Reversed forms", "enabled": bool(self.mutator_include_reversed), "detail": "reverse candidate strings"},
            {"name": "Case swaps", "enabled": bool(self.mutator_include_case_swaps), "detail": "swapcase variants"},
            {"name": "Base64 / ROT13 / hex", "enabled": bool(self.mutator_include_base64 or self.mutator_include_rot13 or self.mutator_include_hex), "detail": "b64=%s rot13=%s hex=%s" % (self.mutator_include_base64, self.mutator_include_rot13, self.mutator_include_hex)},
            {"name": "Custom seed inputs", "enabled": bool(self.mutator_custom_words or self.mutator_custom_prefixes or self.mutator_custom_suffixes), "detail": "%d words | %d prefixes | %d suffixes" % (len(self.mutator_custom_words or []), len(self.mutator_custom_prefixes or []), len(self.mutator_custom_suffixes or []))},
            {"name": "Environment favorites", "enabled": bool(self.mutator_use_env_favorites), "detail": "%d stored entries" % len(self.env_favorites or {})},
        ]

    def _wordlist_lab(self):
        rows = []
        for key, stats in (self.wordlist_stats or {}).items():
            if not isinstance(stats, dict):
                continue
            eff = self._wordlist_effectiveness(key, stats)
            name = stats.get("name") or key.split(":", 1)[0]
            mode = stats.get("mode", "plain")
            est = int(eff.get("estimated_words", 0) or 0)
            cracks = int(eff.get("cracks", 0) or 0)
            per_million = (cracks * 1_000_000.0 / est) if est else 0.0
            if not eff.get("eligible"):
                verdict = "Need more samples"
            elif cracks > 0 and eff.get("confidence", 0) >= 10:
                verdict = "Promising"
            elif cracks == 0 and int(eff.get("runs", 0) or 0) >= self.wordlist_min_runs_for_ranking:
                verdict = "Low value so far"
            else:
                verdict = "Watch"
            rows.append({
                "key": key, "label": "%s (%s)" % (name, mode) if mode else name,
                "runs": eff.get("runs", 0), "cracks": cracks,
                "success_rate": round(float(eff.get("success_rate", 0.0)), 2),
                "confidence": round(float(eff.get("confidence", 0.0)), 2),
                "estimated_words": est, "estimated_words_abbr": self.abbreviate_number(est) if est else "0",
                "avg_duration": round(float(eff.get("avg_duration", 0.0)), 1),
                "cracks_per_million": round(per_million, 3), "verdict": verdict,
            })
        rows.sort(key=lambda r: (r["verdict"] == "Need more samples", -r["confidence"], -r["cracks"], -r["runs"]))
        recommendation = "Collect more data before changing list order."
        eligible = [r for r in rows if r["runs"] >= self.wordlist_min_runs_for_ranking]
        if eligible:
            best = eligible[0]
            recommendation = "%s is currently the strongest measured early-pass candidate." % best["label"]
        return {"rows": rows, "recommendation": recommendation}

    def _report_window(self, seconds, label):
        now = time.time(); start = now - seconds
        jobs = [j for j in (self.job_history or []) if float(j.get("finished_at", j.get("started_at", 0)) or 0) >= start]
        result_counts = {"Cracked": 0, "Failed": 0, "Timeout": 0, "Other": 0}
        total_duration = 0.0
        for j in jobs:
            result = str(j.get("result", "") or "")
            result_counts[result if result in result_counts else "Other"] += 1
            total_duration += float(j.get("duration", 0.0) or 0.0)
        points = [p for p in (self.resource_history or []) if float(p.get("ts", 0) or 0) >= start]
        peak_temp = max([float(p.get("temp_f")) for p in points if isinstance(p.get("temp_f"), (int, float))] or [0.0])
        peak_load = max([float(p.get("load_1m", 0.0) or 0.0) for p in points] or [0.0])
        peak_swap = max([int(p.get("swap_used_mb", 0) or 0) for p in points] or [0])
        avg_wps = sum(float(p.get("wps", 0.0) or 0.0) for p in points) / float(len(points) or 1)
        return {"label": label, "from": start, "to": now, "jobs": len(jobs), "results": result_counts,
                "total_duration": round(total_duration, 1), "avg_duration": round(total_duration / len(jobs), 1) if jobs else 0.0,
                "peak_temp_f": round(peak_temp, 1), "peak_load": round(peak_load, 2), "peak_swap_mb": peak_swap,
                "avg_wps": avg_wps, "avg_wps_abbr": self.abbreviate_number(int(avg_wps)) if avg_wps else "0"}

    def _reports_payload(self):
        return {"today": self._report_window(24 * 3600, "Last 24 hours"), "week": self._report_window(7 * 24 * 3600, "Last 7 days"),
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")}

    def _epaper_summary(self):
        snap = self.last_resource_snapshot or self._resource_snapshot()
        ssid = (self.current_ssid or "IDLE")[:10]
        wl = (os.path.basename(self.current_wordlist_key or "wait").split(":")[0])[:8]
        speed = self.abbreviate_number(int(self.current_wps or 0)) + "/s" if self.current_wps else "--/s"
        temp = snap.get("temp_f")
        temp_text = "%dF" % round(temp) if isinstance(temp, (int, float)) else "?F"
        queue_depth = len(self.get_queue_snapshot(max_items=30))
        text = "BF %s %s %s %s Q%d" % (ssid, wl, speed, temp_text, queue_depth)
        return text[:max(12, int(self.epaper_status_max_chars or 34))]

    # ------------------------------------------------------------------
    # Runtime control, resource governor, capture health and telemetry
    # ------------------------------------------------------------------
    @staticmethod
    def _option_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on", "enabled")
        return bool(value)

    def _parse_ssid_from_filename(self, pcap_file: str) -> str:
        """Use the full prefix before a BSSID when possible; preserve old fallback."""
        base = os.path.basename(pcap_file)
        if base in self.ssid_overrides:
            return str(self.ssid_overrides[base]).strip()
        stem, _ext = os.path.splitext(base)
        mac_match = re.search(
            r"[_-](?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}(?:[_-]|$)", stem
        )
        if mac_match:
            ssid = stem[:mac_match.start()].strip("_-")
            if ssid:
                return ssid
        # Legacy behavior is preserved for unexpected filename formats.
        return stem.split("_", 1)[0].strip() if "_" in stem else stem.strip()

    def _fan_snapshot(self):
        """
        Read the last fan telemetry record written by fan_control.py.
        The dashboard stays fully functional when fan_control is disabled or
        still on an older version; it simply shows telemetry unavailable.
        """
        empty = {
            "available": False,
            "stale": True,
            "age_seconds": None,
            "fan_percent": None,
            "fan_rpm": None,
            "cpu_temp_f": None,
            "updated": "",
            "detail": "Fan telemetry unavailable",
        }
        path = str(getattr(self, "fan_status_path", "") or "")
        if not path:
            return empty
        try:
            with open(path, "r", encoding="utf-8") as handle:
                raw = json.load(handle)
            if not isinstance(raw, dict):
                return empty
            try:
                updated_ts = float(raw.get("timestamp", 0) or 0)
            except Exception:
                updated_ts = 0.0
            age = max(0.0, time.time() - updated_ts) if updated_ts else None
            stale_limit = max(5, int(getattr(self, "fan_status_stale_seconds", 20) or 20))
            stale = age is None or age > stale_limit
            try:
                percent = float(raw.get("fan_percent"))
            except Exception:
                percent = None
            try:
                rpm = float(raw.get("fan_rpm"))
            except Exception:
                rpm = None
            try:
                source_temp = float(raw.get("cpu_temp_f"))
            except Exception:
                source_temp = None
            detail = "Fan telemetry stale" if stale else "Fan telemetry live"
            data = {
                "available": True,
                "stale": stale,
                "age_seconds": age,
                "fan_percent": percent,
                "fan_rpm": rpm,
                "cpu_temp_f": source_temp,
                "updated": str(raw.get("updated", "") or ""),
                "detail": detail,
            }
            self.last_fan_snapshot = data
            return data
        except FileNotFoundError:
            return empty
        except Exception as exc:
            logging.debug("BruteForcer: fan telemetry read failed: %s", exc)
            return empty

    def _resource_snapshot(self):
        mem = {}
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2 and parts[0].endswith(":"):
                        mem[parts[0][:-1]] = int(parts[1]) // 1024
        except Exception:
            pass
        available = int(mem.get("MemAvailable", mem.get("MemFree", 0)) or 0)
        swap_total = int(mem.get("SwapTotal", 0) or 0)
        swap_free = int(mem.get("SwapFree", 0) or 0)
        swap_used = max(0, swap_total - swap_free)
        temp_c = None
        try:
            raw = subprocess.check_output(
                ["vcgencmd", "measure_temp"], text=True, stderr=subprocess.DEVNULL, timeout=3
            )
            match = re.search(r"([0-9.]+)", raw)
            if match:
                temp_c = float(match.group(1))
        except Exception:
            pass
        try:
            load_1m = float(os.getloadavg()[0])
        except Exception:
            load_1m = 0.0
        temp_f = ((temp_c * 9.0 / 5.0) + 32.0) if temp_c is not None else None
        fan = self._fan_snapshot()
        return {
            "available_mem_mb": available,
            "swap_used_mb": swap_used,
            "temp_c": temp_c,
            "temp_f": temp_f,
            "load_1m": load_1m,
            "fan": fan,
        }

    def _governor_reason(self, snapshot):
        if not self.governor_enabled:
            return ""
        available = snapshot.get("available_mem_mb", 0)
        swap_used = snapshot.get("swap_used_mb", 0)
        temp_c = snapshot.get("temp_c")
        load_1m = snapshot.get("load_1m", 0.0)
        if self.governor_min_available_mem_mb > 0 and available < self.governor_min_available_mem_mb:
            return f"low memory ({available} MB available)"
        if self.governor_max_swap_used_mb > 0 and swap_used > self.governor_max_swap_used_mb:
            return f"swap pressure ({swap_used} MB used)"
        if temp_c is not None and self.governor_max_temp_c > 0 and temp_c >= self.governor_max_temp_c:
            return f"high temperature ({(temp_c * 9.0 / 5.0) + 32.0:.1f} F)"
        if self.governor_max_load_1m > 0 and load_1m >= self.governor_max_load_1m:
            return f"high load ({load_1m:.2f})"
        return ""

    def _update_runtime_health(self):
        snapshot = self._resource_snapshot()
        reason = self._governor_reason(snapshot)
        self.last_resource_snapshot = snapshot
        self._record_resource_history(snapshot)
        self.governor_blocked = bool(reason)
        if self.governor_enabled:
            self.governor_detail = reason or "Resources within configured limits"
        else:
            self.governor_detail = "Governor disabled"
        return reason

    def _wait_for_run_permission(self, context="queue"):
        """Pause safely between wordlists/captures until manual or governor holds clear."""
        while not self.stop_event.is_set():
            if self.manual_paused:
                self.pause_detail = "Manual pause; active work will not start another wordlist."
                self.update_step_status("BF: Paused")
                time.sleep(1)
                continue
            reason = self._update_runtime_health()
            if reason:
                self.pause_detail = f"Governor hold: {reason}"
                self.update_step_status("BF: Governor hold")
                time.sleep(max(1, int(self.governor_poll_seconds)))
                continue
            self.pause_detail = "Queue is ready."
            return True
        return False

    def _capture_health_counts(self):
        counts = {"valid": 0, "bad": 0, "review": 0, "unknown": 0, "deferred": 0}
        now = time.time()
        for _path, info in (self.capture_health or {}).items():
            status = str((info or {}).get("status", "unknown"))
            if status in ("bad", "no_handshake", "marked_bad"):
                counts["bad"] += 1
            elif status in ("needs_review",):
                counts["review"] += 1
            elif status == "valid":
                counts["valid"] += 1
            else:
                counts["unknown"] += 1
        counts["deferred"] = sum(1 for _p, until in (self.deferred_files or {}).items() if float(until or 0) > now)
        return counts

    def _record_capture_health(self, pcap_file, ssid, status, detail=""):
        self.capture_health[pcap_file] = {
            "ssid": ssid or "",
            "status": status or "unknown",
            "detail": str(detail or "")[-400:],
            "checked_at": time.time(),
        }

    def preflight_capture(self, pcap_file, ssid):
        """Classify only clear failures; anything uncertain is allowed to continue."""
        existing = self.capture_health.get(pcap_file)
        if existing and existing.get("status") in ("valid", "bad", "no_handshake", "needs_review", "marked_bad"):
            return existing
        if not self.preflight_enabled:
            info = {"ssid": ssid, "status": "unknown", "detail": "Preflight disabled", "checked_at": time.time()}
            self.capture_health[pcap_file] = info
            return info
        if not os.path.isfile(pcap_file) or os.path.getsize(pcap_file) <= 24:
            info = {"ssid": ssid, "status": "bad", "detail": "Missing, empty, or too small", "checked_at": time.time()}
            self.capture_health[pcap_file] = info
            return info
        try:
            proc = subprocess.run(
                ["aircrack-ng", "-a", "2", "-e", ssid, pcap_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=max(3, int(self.preflight_timeout)),
            )
            output = (proc.stdout or "").strip()
        except subprocess.TimeoutExpired:
            info = {"ssid": ssid, "status": "unknown", "detail": "Preflight timed out; allowing normal run", "checked_at": time.time()}
            self.capture_health[pcap_file] = info
            return info
        except Exception as exc:
            info = {"ssid": ssid, "status": "unknown", "detail": f"Preflight unavailable: {exc}", "checked_at": time.time()}
            self.capture_health[pcap_file] = info
            return info

        low = output.lower()
        if "no matching network found" in low or "0 potential targets" in low:
            status, detail = "bad", "No matching target in capture"
        elif "invalid packet capture length 0" in low or "corrupted file" in low:
            status, detail = "bad", "Capture appears corrupted"
        elif "no valid wpa handshakes found" in low:
            status, detail = "no_handshake", "Target found but no usable WPA handshake"
        elif "index number of target network" in low:
            status, detail = "needs_review", "Multiple/ambiguous target selection"
        else:
            status, detail = "valid", "Target preflight passed or was inconclusive"
        info = {"ssid": ssid, "status": status, "detail": detail, "checked_at": time.time()}
        self.capture_health[pcap_file] = info
        self._log_ssid(ssid, f"[preflight] {status}: {detail}")
        return info

    def _wordlist_line_count(self, path):
        if not self.wordlist_line_count_enabled:
            return 0
        try:
            stat = os.stat(path)
            cache_key = f"{path}:{stat.st_mtime_ns}:{stat.st_size}"
            if cache_key in self.wordlist_line_counts:
                return int(self.wordlist_line_counts[cache_key])
            with open(path, "rb") as handle:
                count = sum(1 for _line in handle)
            # Drop stale entries for this same path and preserve only the current fingerprint.
            for key in list(self.wordlist_line_counts):
                if key.startswith(f"{path}:") and key != cache_key:
                    self.wordlist_line_counts.pop(key, None)
            self.wordlist_line_counts[cache_key] = count
            return count
        except Exception:
            return 0

    def _record_wordlist_run(
        self,
        stats_key,
        duration,
        candidate_count,
        progress_pct,
        result,
        tested_keys=0,
        measured_wps=0.0,
    ):
        stats = self.wordlist_stats.setdefault(stats_key, {"runs": 0, "cracks": 0})
        duration = max(0.0, float(duration or 0.0))
        candidate_count = max(0, int(candidate_count or 0))
        progress_pct = min(100.0, max(0.0, float(progress_pct or 0.0)))
        tested_keys = max(0, int(tested_keys or 0))

        # Tested-key counter is the preferred work total. Preserve the older
        # estimate only when a counter was unavailable.
        if tested_keys:
            estimate = tested_keys
        elif result in ("failed", "bad"):
            estimate = candidate_count
        elif candidate_count and progress_pct > 0:
            estimate = int(candidate_count * progress_pct / 100.0)
        else:
            estimate = 0

        stats["estimated_words"] = int(stats.get("estimated_words", 0) or 0) + estimate
        stats["duration_seconds"] = float(stats.get("duration_seconds", 0.0) or 0.0) + duration
        stats["completed_runs"] = int(stats.get("completed_runs", 0) or 0) + (
            1 if result in ("failed", "cracked", "bad") else 0
        )
        if tested_keys > 0 and duration > 0:
            stats["measured_keys"] = int(stats.get("measured_keys", 0) or 0) + tested_keys
            stats["measured_seconds"] = float(stats.get("measured_seconds", 0.0) or 0.0) + duration
        if measured_wps > 0:
            stats["last_measured_wps"] = float(measured_wps)
        if result == "timeout":
            stats["timeouts"] = int(stats.get("timeouts", 0) or 0) + 1
        if result == "skipped":
            stats["skips"] = int(stats.get("skips", 0) or 0) + 1

    @staticmethod
    def _wilson_lower_bound(successes, trials, z=1.96):
        if trials <= 0:
            return 0.0
        p = float(successes) / float(trials)
        denom = 1.0 + z * z / trials
        centre = p + z * z / (2.0 * trials)
        margin = z * (((p * (1.0 - p) + z * z / (4.0 * trials)) / trials) ** 0.5)
        return max(0.0, (centre - margin) / denom)

    def _wordlist_effectiveness(self, key, stats):
        runs = int(stats.get("runs", 0) or 0)
        cracks = int(stats.get("cracks", 0) or 0)
        duration = float(stats.get("duration_seconds", 0.0) or 0.0)
        estimated = int(stats.get("estimated_words", 0) or 0)
        confidence = self._wilson_lower_bound(cracks, runs) * 100.0
        avg_duration = duration / runs if runs else 0.0
        measured_keys = int(stats.get("measured_keys", 0) or 0)
        measured_seconds = float(stats.get("measured_seconds", 0.0) or 0.0)
        measured_wps = (measured_keys / measured_seconds) if measured_seconds > 0 else 0.0
        return {
            "runs": runs,
            "cracks": cracks,
            "success_rate": (cracks * 100.0 / runs) if runs else 0.0,
            "confidence": confidence,
            "estimated_words": estimated,
            "avg_duration": avg_duration,
            "measured_wps": measured_wps,
            "eligible": runs >= int(self.wordlist_min_runs_for_ranking),
        }

    def _defer_capture(self, pcap_file, seconds=None, reason="Deferred"):
        if not pcap_file:
            return
        seconds = self.defer_seconds if seconds is None else seconds
        until = time.time() + max(1, int(seconds or 1))
        self.deferred_files[pcap_file] = until
        self._log_console(f"[bruteforce] {reason}: {os.path.basename(pcap_file)} until {time.strftime('%H:%M:%S', time.localtime(until))}")

    def _mark_capture_bad(self, pcap_file, ssid, reason="Marked bad from dashboard"):
        if not pcap_file:
            return
        self._record_capture_health(pcap_file, ssid, "marked_bad", reason)
        self.processed_files_set.add(pcap_file)
        self.processed_files = len(self.processed_files_set)
        self.save_progress()

    def _requeue_capture(self, pcap_file):
        if not pcap_file:
            return False
        self.processed_files_set.discard(pcap_file)
        self.deferred_files.pop(pcap_file, None)
        self.capture_health.pop(pcap_file, None)
        self.manual_priority_files.add(pcap_file)
        self.processed_files = len(self.processed_files_set)
        self.save_progress()
        return True

    def _find_capture_by_basename(self, basename):
        if not basename:
            return None
        for pcap in self.processed_files_set:
            if os.path.basename(pcap) == basename:
                return pcap
        for root, _dirs, files in os.walk(self.handshake_dir):
            if basename in files:
                return os.path.join(root, basename)
        return None

    def _terminate_current_task(self):
        with self.lock:
            process = self.current_task
        if process is not None and process.poll() is None:
            try:
                process.terminate()
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Aircrack-ng telemetry helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _aircrack_rate_to_wps(rate_value, unit=""):
        """Convert Aircrack's printed rate into candidates/sec for diagnostics."""
        try:
            rate = float(str(rate_value).replace(",", "."))
        except Exception:
            return 0.0
        unit = (unit or "").strip().lower()
        multipliers = {"": 1.0, "k": 1_000.0, "m": 1_000_000.0, "g": 1_000_000_000.0}
        return max(0.0, rate * multipliers.get(unit, 1.0))

    @staticmethod
    def _parse_aircrack_elapsed_seconds(line):
        """Parse Aircrack's [HH:MM:SS] elapsed timestamp when present."""
        match = re.search(
            r"\[(?P<h>\d{1,3}):(?P<m>[0-5]\d):(?P<s>[0-5]\d)\]",
            str(line or ""),
        )
        if not match:
            return None
        try:
            return (
                int(match.group("h")) * 3600
                + int(match.group("m")) * 60
                + int(match.group("s"))
            )
        except Exception:
            return None

    def _reset_wps_for_wordlist(self):
        """Reset per-wordlist telemetry without touching historical totals."""
        self.current_wps = 0.0
        self.current_wps_source = "waiting"
        self.current_wps_confidence = "waiting"
        self.current_aircrack_reported_wps = 0.0
        self.current_wps_difference_pct = None
        self.current_wordlist_started_monotonic = time.monotonic()
        self.current_wordlist_aircrack_seconds = None
        self.current_wordlist_keys_tested = 0
        self.current_wordlist_accounted_keys = 0
        self.last_keys_tested = None
        self.last_keys_tested_time = None
        self.last_wps_update_time = None

    def _account_tested_keys(self, keys_tested):
        """Add only newly reported tested keys to the long-lived total."""
        try:
            keys = max(0, int(keys_tested))
        except Exception:
            return
        if keys >= self.current_wordlist_accounted_keys:
            added = keys - self.current_wordlist_accounted_keys
            self.current_wordlist_accounted_keys = keys
            if added:
                self.words_processed += added
                self.words_processed_abbr = self.abbreviate_number(self.words_processed)
        self.current_wordlist_keys_tested = max(self.current_wordlist_keys_tested, keys)

    def _record_measured_wps(self, wps_value, keys_tested=None, source="counter/time"):
        """Record a measured candidate rate; this is the dashboard source of truth."""
        try:
            wps = max(0.0, float(wps_value))
        except Exception:
            return
        if keys_tested is not None:
            self._account_tested_keys(keys_tested)

        if wps <= 0:
            return

        self.current_wps = wps
        self.current_wps_source = source or "counter/time"
        self.current_wps_confidence = "measured"
        self.last_wps_update_time = time.monotonic()
        self._append_limited(self.wps_data, wps)

    def _finalize_wordlist_wps(self, duration, candidate_count=0):
        """Finalize a reliable average for one wordlist after the process exits."""
        try:
            elapsed = max(0.0, float(duration or 0.0))
        except Exception:
            elapsed = 0.0

        tested = int(self.current_wordlist_keys_tested or 0)
        # Only use line count as a fallback after a complete failed pass.
        if tested <= 0:
            try:
                tested = max(0, int(candidate_count or 0))
            except Exception:
                tested = 0

        if tested > 0 and elapsed > 0.05:
            measured = tested / elapsed
            self.last_completed_wps = measured
            self.last_completed_keys_tested = tested
            self.last_completed_duration = elapsed
            self.current_wps = measured
            self.current_wps_source = "completed keys/time"
            self.current_wps_confidence = "measured"
            self._append_limited(self.wps_data, measured)

            if self.current_aircrack_reported_wps > 0:
                denom = max(measured, 1.0)
                self.current_wps_difference_pct = (
                    abs(self.current_aircrack_reported_wps - measured) / denom
                ) * 100.0
            return measured
        return 0.0

    def _parse_aircrack_telemetry(self, raw_line, ssid="", wl_name=""):
        """Parse counters and calculate WPS from tested keys divided by elapsed time.

        Aircrack's printed `(NN k/s)` is retained as a diagnostic. The dashboard
        deliberately does not use it as the primary rate because builds and
        buffered output can make that string misleading.
        """
        if not raw_line:
            return False
        line = str(raw_line).replace("\r", " ").strip()
        if not line:
            return False

        prog_match = re.search(r"(?<![\d.])(\d{1,3}(?:\.\d+)?)\s*%", line)
        if prog_match:
            try:
                cur_prog = min(100.0, max(0.0, float(prog_match.group(1))))
                self.progress = f"{int(cur_prog)}%"
                self.current_wordlist_progress = cur_prog
                self._append_limited(self.progress_data, int(cur_prog))
            except Exception:
                pass

        key_match = re.search(
            r"(?P<done>[\d,]+)(?:\s*/\s*(?P<total>[\d,]+))?\s+keys\s+tested",
            line,
            re.IGNORECASE,
        )
        keys_tested = None
        total_keys = None
        if key_match:
            try:
                keys_tested = int(key_match.group("done").replace(",", ""))
            except Exception:
                keys_tested = None
            try:
                raw_total = key_match.group("total")
                total_keys = int(raw_total.replace(",", "")) if raw_total else None
            except Exception:
                total_keys = None

        if keys_tested is not None and total_keys and total_keys > 0:
            pct = min(100.0, max(0.0, (keys_tested * 100.0) / total_keys))
            self.progress = f"{int(pct)}%"
            self.current_wordlist_progress = pct
            self._append_limited(self.progress_data, int(pct))

        rate_match = re.search(
            r"\(\s*(?P<rate>[\d.,]+)\s*(?P<unit>[kKmMgG]?)\s*/\s*s\s*\)",
            line,
            re.IGNORECASE,
        )
        if not rate_match:
            rate_match = re.search(
                r"(?P<rate>[\d.,]+)\s*(?P<unit>[kKmMgG]?)\s*(?:words?|keys?)\s*(?:per\s*(?:second|sec)|/\s*s)",
                line,
                re.IGNORECASE,
            )
        if rate_match:
            self.current_aircrack_reported_wps = self._aircrack_rate_to_wps(
                rate_match.group("rate"), rate_match.group("unit")
            )

        if keys_tested is None:
            # A terminal-status redraw can contain a raw k/s-looking value but
            # no tested-key counter. Do not let that redraw overwrite a real
            # counter/time measurement captured from an earlier line.
            if self.current_aircrack_reported_wps > 0:
                if self.current_wps_confidence != "measured" or self.current_wps <= 0:
                    self.current_wps_source = "aircrack reported (unverified)"
                    self.current_wps_confidence = "unverified"
                self.on_ui_update(self.ui)
                return True
            return False

        self._account_tested_keys(keys_tested)
        elapsed_from_aircrack = self._parse_aircrack_elapsed_seconds(line)
        if elapsed_from_aircrack is not None and elapsed_from_aircrack > 0:
            self.current_wordlist_aircrack_seconds = elapsed_from_aircrack
            measured = keys_tested / float(elapsed_from_aircrack)
            source = "aircrack counter/time"
        else:
            start = self.current_wordlist_started_monotonic
            wall_elapsed = (time.monotonic() - start) if start else 0.0
            if wall_elapsed <= 0.25:
                # Too little elapsed time for a meaningful rate. Wait for the
                # next progress line or the completed-job calculation.
                self.last_keys_tested = keys_tested
                self.last_keys_tested_time = time.monotonic()
                return True
            measured = keys_tested / wall_elapsed
            source = "counter/wall time"

        self._record_measured_wps(measured, keys_tested=keys_tested, source=source)

        if self.current_aircrack_reported_wps > 0:
            denom = max(measured, 1.0)
            self.current_wps_difference_pct = (
                abs(self.current_aircrack_reported_wps - measured) / denom
            ) * 100.0

        if ssid or wl_name:
            self.status_message = f"{ssid[:4]} {wl_name[:4]} {int(round(measured))}W/s"
        self.on_ui_update(self.ui)
        return True

    # ------------------------------------------------------------------
    # Mutator helpers
    # ------------------------------------------------------------------
    def _apply_mutator_profile(self, profile: str):
        """
        High-level presets for how aggressive the mutator should be.

        This only adjusts internal defaults. Any explicit mutator_*
        flags in the config will override these values later.
        """
        p = (profile or "").lower()
        if p == "fast":
            # Small, cheap wordlist - good for low-power or quick passes.
            self.mutator_max_words = min(self.mutator_max_words, 300)
            self.mutator_include_base64 = False
            self.mutator_include_rot13 = False
            self.mutator_include_hex = False
            self.mutator_include_reversed = False
            self.mutator_include_case_swaps = False
            self.mutator_leet_mode = "off"
        elif p == "heavy":
            # Throw the kitchen sink at it.
            self.mutator_max_words = max(self.mutator_max_words, 2000)
            self.mutator_include_base64 = True
            self.mutator_include_rot13 = True
            self.mutator_include_hex = True
            self.mutator_include_separators = True
            self.mutator_include_reversed = True
            self.mutator_include_case_swaps = True
            self.mutator_leet_mode = "heavy"
        else:
            # Balanced default
            self.mutator_max_words = max(self.mutator_max_words, 800)
            self.mutator_include_base64 = True
            self.mutator_include_rot13 = True
            # hex stays optional by default
            self.mutator_include_separators = True
            self.mutator_include_reversed = True
            self.mutator_include_case_swaps = True
            if self.mutator_leet_mode not in ("off", "light", "heavy"):
                self.mutator_leet_mode = "light"

    def register_mutator_file(self, ssid: str, path: str):
        paths = self.mutator_paths.setdefault(ssid, set())
        paths.add(path)

    def cleanup_mutator_files(self, ssid: str):
        paths = self.mutator_paths.pop(ssid, set())
        for p in paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
                    self._log_ssid(ssid, f"[mutator] Removed temporary wordlist {p}")
            except Exception as e:
                self._log_ssid(ssid, f"[mutator] Failed to remove {p}: {e}", "error")

    def leetify(self, s: str) -> str:
        trans = str.maketrans({
            'a': '@', 'A': '@',
            'i': '1', 'I': '1',
            'e': '3', 'E': '3',
            'o': '0', 'O': '0',
            's': '$', 'S': '$',
        })
        return s.translate(trans)

    def _update_mutator_profile(self, ssid: str, words_count: int):
        stats = self.ssid_stats.setdefault(ssid, {})
        m = stats.setdefault("mutator", {"runs": 0, "total_words": 0, "time_seconds": 0.0, "cracks": 0})
        m["runs"] += 1
        m["total_words"] += int(words_count or 0)

    def _record_mutator_generation(self, ssid, candidates, categories):
        count = int(len(candidates or []))
        summary = {
            "ssid": str(ssid or "?"),
            "count": count,
            "categories": dict(categories or {}),
            "created_at": time.time(),
            "strategy": self.mutator_strategy,
            "cap": int(self.mutator_max_words or 0),
        }
        self.mutator_last_generation = summary
        self.mutator_generation_history.append(dict(summary))
        if len(self.mutator_generation_history) > self.max_mutator_generation_history:
            self.mutator_generation_history.pop(0)
        for name, value in (categories or {}).items():
            self.mutator_feature_totals[name] = int(self.mutator_feature_totals.get(name, 0) or 0) + int(value or 0)
        self._record_event("mutator", "Generated %d ordered candidates (%s)" % (count, self.mutator_strategy), "info", ssid, {"categories": categories})
        return candidates

    def generate_mutation_candidates(self, ssid: str):
        """Generate a bounded, ordered, SSID-aware candidate list.

        v3.3 keeps the original feature flags but orders low-noise forms first so
        a small Pi spends its limited candidate budget on the most relevant forms.
        """
        if not ssid:
            return []
        try:
            limit = int(self.mutator_max_words or 0)
        except Exception:
            limit = 0
        limit = max(10, min(limit or 10, 20000))
        min_length = max(8, min(int(self.mutator_min_length or 8), 63))
        max_length = max(min_length, min(int(self.mutator_max_length or 63), 63))
        strategy = str(self.mutator_strategy or "smart").lower()
        if strategy not in ("smart", "compatibility", "thorough"):
            strategy = "smart"

        base = re.sub(r"\s+", " ", str(ssid).strip())
        if not base:
            return []
        tokens = [t for t in re.split(r"[\s\-_]+", base) if t]
        digit_chunks = list(dict.fromkeys(re.findall(r"\d+", base)))
        ordered, seen, categories = [], set(), {}

        def at_limit():
            return len(ordered) >= limit

        def add(word, category):
            if at_limit() or word is None:
                return False
            word = str(word).strip()
            if len(word) < min_length or len(word) > max_length or word in seen:
                return False
            seen.add(word)
            ordered.append(word)
            categories[category] = int(categories.get(category, 0) or 0) + 1
            return True

        def add_variants(word, category, allow_leet=False):
            if at_limit():
                return
            add(word, category)
            if allow_leet and self.mutator_leet_mode != "off" and not at_limit():
                candidate = self.leetify(word)
                if candidate != word:
                    add(candidate, "leet")

        # Core base forms, in practical order. Preserve original signal while
        # avoiding alphabetical sorting that used to discard candidate priority.
        raw_forms = [
            base, base.lower(), base.title(), base.upper(),
            base.replace(" ", ""), base.replace("-", ""), base.replace("_", ""),
        ]
        core_forms = []
        form_seen = set()
        for form in raw_forms:
            if form and form not in form_seen:
                form_seen.add(form)
                core_forms.append(form)

        custom_words = [str(w).strip() for w in (self.mutator_custom_words or []) if str(w).strip()]
        for word in custom_words:
            if word not in form_seen:
                form_seen.add(word)
                core_forms.append(word)

        # Direct forms first: cheapest and easiest to inspect in the dashboard.
        for form in core_forms:
            add(form, "core")
            if at_limit():
                return self._record_mutator_generation(ssid, ordered, categories)

        # Token forms and selected token pairs. Pairing is off until explicitly enabled.
        token_forms = []
        if self.mutator_ssid_splits:
            token_forms.extend(tokens)
            if len(tokens) > 1:
                token_forms.extend([tokens[0] + tokens[-1], tokens[-1] + tokens[0]])
        if self.mutator_include_token_pairs and len(tokens) > 1:
            pair_limit = max(1, min(int(self.mutator_token_pair_limit or 6), 24))
            pairs = []
            for idx, left in enumerate(tokens):
                for right in tokens[idx + 1:]:
                    pairs.extend([left + right, right + left])
                    if len(pairs) >= pair_limit:
                        break
                if len(pairs) >= pair_limit:
                    break
            token_forms.extend(pairs)
        for form in token_forms:
            if form and form not in form_seen:
                form_seen.add(form)
                add(form, "token_pair" if form not in tokens else "token")
                if at_limit():
                    return self._record_mutator_generation(ssid, ordered, categories)

        # Separator combinations are useful for multi-word SSIDs but remain bounded.
        if self.mutator_include_separators and len(tokens) > 1:
            for sep in ("", "-", "_", ".", " "):
                form = sep.join(tokens)
                if form not in form_seen:
                    form_seen.add(form)
                    add(form, "separator")
                    if at_limit():
                        return self._record_mutator_generation(ssid, ordered, categories)

        # Build suffix sets. Years are intentionally bounded to avoid chewing the whole cap.
        suffixes = ["1", "12", "123", "1234", "!", "!!", "?", "123456", "12345678"]
        if self.mutator_include_numeric_suffixes:
            suffixes.extend(digit_chunks)
        if self.mutator_include_years:
            current_year = time.localtime().tm_year
            start_year = int(self.mutator_year_start or current_year - 5)
            end_year = int(self.mutator_year_end or current_year)
            start_year = max(1990, min(start_year, 2100))
            end_year = max(start_year, min(end_year, 2100))
            if end_year - start_year > 20:
                start_year = end_year - 20
            suffixes.extend(str(year) for year in range(end_year, start_year - 1, -1))
        suffixes.extend([str(v).strip() for v in (self.mutator_custom_suffixes or []) if str(v).strip()])
        suffixes = list(dict.fromkeys(suffixes))
        prefixes = [""] + [str(v).strip() for v in (self.mutator_custom_prefixes or []) if str(v).strip()]
        if strategy in ("compatibility", "thorough"):
            prefixes = list(dict.fromkeys(prefixes + ["!", "@", "#"]))

        # Smart ordering: plain base+suffix first. That is the most likely use of
        # a limited 800-candidate budget and does not increase the cap.
        seed_forms = list(core_forms) + [f for f in token_forms if f]
        for form in seed_forms:
            for suffix in suffixes:
                add_variants(form + suffix, "year_suffix" if suffix.isdigit() and len(suffix) == 4 else "suffix", allow_leet=(self.mutator_leet_mode != "off"))
                if at_limit():
                    return self._record_mutator_generation(ssid, ordered, categories)

        # Configured prefixes are a deliberate opt-in. Thorough mode retains the
        # old broad prefix behaviour.
        for prefix in prefixes:
            if not prefix:
                continue
            for form in seed_forms[:max(1, min(len(seed_forms), 24))]:
                add_variants(prefix + form, "prefix", allow_leet=(strategy == "thorough" and self.mutator_leet_mode != "off"))
                if at_limit():
                    return self._record_mutator_generation(ssid, ordered, categories)
                for suffix in suffixes[:16]:
                    add_variants(prefix + form + suffix, "prefix_suffix", allow_leet=(strategy == "thorough" and self.mutator_leet_mode != "off"))
                    if at_limit():
                        return self._record_mutator_generation(ssid, ordered, categories)

        # Optional broad transforms are intentionally later in the list.
        transform_seeds = list(ordered[:min(len(ordered), 180)])
        if self.mutator_include_reversed:
            for word in transform_seeds:
                add(word[::-1], "reversed")
                if at_limit():
                    return self._record_mutator_generation(ssid, ordered, categories)
        if self.mutator_include_case_swaps:
            for word in transform_seeds:
                add(word.swapcase(), "case_swap")
                if at_limit():
                    return self._record_mutator_generation(ssid, ordered, categories)

        # Legacy encodings remain available but are purposely last because they
        # are rarely useful on a small candidate budget.
        encoding_seeds = list(ordered[:min(len(ordered), 120)])
        for word in encoding_seeds:
            if self.mutator_include_base64:
                try: add(base64.b64encode(word.encode("utf-8")).decode("ascii"), "base64")
                except Exception: pass
            if self.mutator_include_rot13:
                try: add(codecs.decode(word, "rot_13"), "rot13")
                except Exception: pass
            if self.mutator_include_hex:
                try: add(word.encode("utf-8").hex(), "hex")
                except Exception: pass
            if at_limit():
                return self._record_mutator_generation(ssid, ordered, categories)

        # Optional local environment favorites, last so they never crowd out SSID-specific forms.
        if self.mutator_use_env_favorites and self.env_favorites and not at_limit():
            top_favorites = sorted(self.env_favorites.items(), key=lambda item: item[1], reverse=True)[:10]
            for form in core_forms[:3]:
                for favorite, _score in top_favorites:
                    add(form + favorite, "favorite")
                    add(favorite + form, "favorite")
                    if at_limit():
                        return self._record_mutator_generation(ssid, ordered, categories)

        return self._record_mutator_generation(ssid, ordered, categories)

    def build_mutation_wordlist(self, ssid: str) -> Optional[str]:
        """
        Build a temporary wordlist file for a given SSID using the mutator.
        Any errors in candidate generation or file writing will:
        - be logged
        - disable mutator for this SSID
        - return None so the main loop can skip mutator cleanly.
        """
        if not self.mutator_enabled:
            return None
        if not ssid:
            return None

        # If we've already had a hard error for this SSID, just skip.
        if ssid in self.mutator_error_ssids:
            self._log_ssid(
                ssid,
                "[mutator] Previously errored for this SSID; skipping mutator for this run.",
                "error",
            )
            return None

        # Generate candidates safely
        try:
            words = self.generate_mutation_candidates(ssid)
        except Exception as e:
            self._log_ssid(
                ssid,
                f"[mutator] Error during candidate generation: {e}. Disabling mutator for this SSID.",
                "error",
            )
            self.mutator_error_ssids.add(ssid)
            return None

        if not words:
            return None

        safe_ssid = re.sub(r"[^A-Za-z0-9]+", "_", ssid) or "ssid"
        path = f"/tmp/bruteforce_mut_{safe_ssid}.txt"
        try:
            # Write file with robust encoding handling
            with open(path, "w", encoding="utf-8", errors="ignore") as f:
                for w in words:
                    try:
                        f.write(w + "\n")
                    except Exception:
                        # Skip any individual bad line, keep going
                        continue

            self.register_mutator_file(ssid, path)
            self._update_mutator_profile(ssid, len(words))
            self._log_ssid(ssid, f"[mutator] Generated {len(words)} candidates at {path}")
            return path
        except Exception as e:
            self._log_ssid(
                ssid,
                f"[mutator] Failed to write wordlist: {e}. Disabling mutator for this SSID.",
                "error",
            )
            self.mutator_error_ssids.add(ssid)
            return None

    # ------------------------------------------------------------------
    # Env favorites helpers
    # ------------------------------------------------------------------
    def _update_env_favorites(self, key: Optional[str]):
        if not key:
            return
        if len(key) < 8 or len(key) > 63:
            return
        score = self.env_favorites.get(key, 0) + 1
        self.env_favorites[key] = score
        if len(self.env_favorites) > self.env_favorites_max:
            sorted_items = sorted(self.env_favorites.items(), key=lambda kv: kv[1], reverse=True)
            self.env_favorites = dict(sorted_items[: self.env_favorites_max])
        self._write_env_favorites_file()

    def _write_env_favorites_file(self):
        if not self.env_favorites:
            try:
                if os.path.exists(self.env_favorites_path):
                    os.remove(self.env_favorites_path)
            except Exception:
                pass
            return
        try:
            with open(self.env_favorites_path, "w") as f:
                for word, _score in sorted(self.env_favorites.items(), key=lambda kv: kv[1], reverse=True):
                    f.write(word + "\n")
            self._log_console(f"[bruteforce] Updated env favorites file with {len(self.env_favorites)} entries.")
        except Exception as e:
            self._log_console(f"[bruteforce] Failed to write env favorites file: {e}", "error")

    # ------------------------------------------------------------------
    # Wordlist ordering
    # ------------------------------------------------------------------
    def _get_wordlist_order(self, wordlist_items):
        def sort_key(item):
            path = item.get("path", "")
            mode = item.get("mode", "plain")
            name = os.path.basename(path)
            key = f"{name}:{mode}"
            stats = self.wordlist_stats.get(key, {})
            eff = self._wordlist_effectiveness(key, stats)
            # Keep untested lists in deterministic order; after enough samples,
            # rank by Wilson lower-bound confidence rather than one lucky run.
            eligible_bucket = 0 if eff.get("eligible") else 1
            confidence = float(eff.get("confidence", 0.0))
            runs = int(eff.get("runs", 0))
            return (eligible_bucket, -confidence, runs, name, mode)

        return sorted(wordlist_items, key=sort_key)

    def _finalize_handshake(self, pcap_file: str, ssid: str, result: str):
        self.update_status("DONE", "100%", result)

        if pcap_file not in self.processed_files_set:
            self.processed_files_set.add(pcap_file)

        self.processed_files = len(self.processed_files_set)

        self.current_pcap = None
        self.current_ssid = None
        self.current_job_start = None
        self.current_job_attempt = 0

        self._journal_clear(result)
        self.save_progress()
        self.update_total_files()
        self._record_event("job", "Finished %s: %s" % (ssid, result), "info", ssid)
        self.update_step_status(f"BF: Wait {ssid}")
        self.on_ui_update(self.ui)
        self._log_ssid(ssid, f"[bruteforce] Finished processing handshake with result: {result}")

    # ------------------------------------------------------------------
    # Stats & achievements
    # ------------------------------------------------------------------
    def _update_stats_for_handshake(
        self,
        ssid,
        result,
        cracked_key,
        cracked_wordlist_key,
        total_elapsed,
        words_delta,
    ):
        stats = self.ssid_stats.get(ssid)
        if not stats:
            stats = {}
            self.ssid_stats[ssid] = stats

        attempts = stats.get("attempts", 0) + 1
        stats["attempts"] = attempts
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        stats["last_result"] = result
        stats["last_seen"] = timestamp
        stats["last_duration"] = float(total_elapsed or 0)
        stats["total_words"] = stats.get("total_words", 0) + max(0, int(words_delta or 0))

        wl_label = None
        if cracked_wordlist_key:
            wl_stats = self.wordlist_stats.setdefault(
                cracked_wordlist_key,
                {"runs": 0, "cracks": 0},
            )
            name_part, mode_part = (
                cracked_wordlist_key.split(":", 1)
                if ":" in cracked_wordlist_key
                else (cracked_wordlist_key, "plain")
            )
            wl_stats.setdefault("name", name_part)
            wl_stats.setdefault("mode", mode_part)
            wl_stats["cracks"] = wl_stats.get("cracks", 0) + 1

            name_val = wl_stats.get("name", name_part)
            mode_val = wl_stats.get("mode", mode_part)
            if mode_val:
                wl_label = f"{name_val} ({mode_val})"
            else:
                wl_label = name_val

            if cracked_wordlist_key.startswith("MutatorGlobal:mutator"):
                m = stats.setdefault(
                    "mutator", {"runs": 0, "total_words": 0, "time_seconds": 0.0, "cracks": 0}
                )
                m["cracks"] = m.get("cracks", 0) + 1

        history = stats.setdefault("history", [])
        avg_wps = 0.0
        if total_elapsed and total_elapsed > 0 and words_delta and words_delta > 0:
            avg_wps = float(words_delta) / float(total_elapsed)

        history.append(
            {
                "attempt": attempts,
                "timestamp": timestamp,
                "result": result,
                "wordlist": wl_label
                or ("-" if result != "Cracked" else "unknown"),
                "duration": float(total_elapsed or 0),
                "avg_wps": avg_wps,
            }
        )
        if len(history) > 50:
            history.pop(0)

        if result == "Cracked":
            stats["cracked"] = True
            if cracked_key:
                stats["last_key"] = cracked_key
            if wl_label:
                stats["success_wordlist"] = wl_label
            self.last_cracked_ssid = ssid
            if cracked_key:
                self.last_cracked_key = cracked_key
            self._update_env_favorites(cracked_key)
        else:
            stats.setdefault("cracked", False)
            if wl_label and "success_wordlist" not in stats:
                stats["success_wordlist"] = wl_label

    def get_queue_snapshot(self, max_items=5):
        try:
            new_files = self.get_new_handshakes()
        except Exception:
            return []
        scored = []
        for pcap in new_files:
            ssid = self._parse_ssid_from_filename(pcap) or "?"
            pri = self._compute_handshake_priority(pcap, ssid)
            scored.append((pri, pcap, ssid))
        scored.sort(key=lambda x: x[0])
        queue = []
        for _pri, pcap, ssid in scored[:max_items]:
            details = self._adaptive_priority_details(pcap, ssid)
            queue.append({"ssid": ssid, "file": os.path.basename(pcap),
                          "priority": details.get("score", 0), "grade": details.get("grade", "?")})
        return queue

    def _compute_handshake_priority(self, pcap_file: str, ssid: str):
        """Preserve legacy order unless adaptive_queue_enabled is explicitly on."""
        details = self._adaptive_priority_details(pcap_file, ssid)
        if self.adaptive_queue_enabled:
            # Higher intelligence score should run first; newer capture breaks ties.
            return (-details["score"], -details["mtime"], pcap_file)

        stats = self.ssid_stats.get(ssid, {})
        attempts = int(stats.get("attempts", 0) or 0)
        last_result = stats.get("last_result", "") or ""
        freshness_rank = -details["mtime"]
        seen_before = attempts > 0
        penalty = 1 if last_result in ("Failed", "Timeout") else 0
        manual_priority = pcap_file in self.manual_priority_files
        return (not manual_priority, seen_before, penalty, attempts, freshness_rank, pcap_file)


    def compute_leaderboard(self):
        fastest_ssid = ""
        fastest_duration = None
        fastest_wordlist = ""
        for ssid, stats in self.ssid_stats.items():
            history = stats.get("history") or []
            for h in history:
                if h.get("result") != "Cracked":
                    continue
                dur = h.get("duration")
                if isinstance(dur, (int, float)):
                    dur = float(dur)
                    if fastest_duration is None or dur < fastest_duration:
                        fastest_duration = dur
                        fastest_ssid = ssid
                        fastest_wordlist = h.get("wordlist") or ""

        best_label = ""
        best_rate = None
        best_cracks = 0
        best_runs = 0
        best_confidence = -1.0
        for key, wstats in self.wordlist_stats.items():
            eff = self._wordlist_effectiveness(key, wstats)
            runs = eff["runs"]
            cracks = eff["cracks"]
            if runs <= 0:
                continue
            rate = eff["success_rate"]
            confidence = eff["confidence"]
            name = wstats.get("name") or key
            mode = wstats.get("mode", "plain")
            label = f"{name} ({mode})" if mode else name
            # Prefer stable, repeatable results. Before minimum sample size,
            # retain the old raw-rate fallback so the dashboard still has data.
            score = confidence if eff.get("eligible") else (rate / 1000.0)
            if score > best_confidence:
                best_confidence = score
                best_rate = rate
                best_label = label
                best_cracks = cracks
                best_runs = runs

        stubborn_ssid = ""
        stubborn_attempts = 0
        stubborn_status = ""
        for ssid, stats in self.ssid_stats.items():
            attempts = int(stats.get("attempts", 0) or 0)
            if attempts > stubborn_attempts:
                stubborn_attempts = attempts
                stubborn_ssid = ssid
                last_result = stats.get("last_result") or ""
                cracked_flag = stats.get("cracked", False)
                if cracked_flag and last_result != "Cracked":
                    last_result = "Cracked"
                stubborn_status = last_result or (
                    "Cracked" if cracked_flag else "Unknown"
                )

        return {
            "fast_ssid": fastest_ssid,
            "fast_duration": fastest_duration,
            "fast_wordlist": fastest_wordlist,
            "best_label": best_label,
            "best_rate": best_rate,
            "best_cracks": best_cracks,
            "best_runs": best_runs,
            "stubborn_ssid": stubborn_ssid,
            "stubborn_attempts": stubborn_attempts,
            "stubborn_status": stubborn_status,
        }

    def compute_achievements(self):
        ach = []
        cracked = self.cracked_count
        processed = self.processed_files
        total_words = self.words_processed

        marathon = False
        speed_demon = False
        stubborn_hunter = False

        for ssid, stats in self.ssid_stats.items():
            if stats.get("total_words", 0) >= 1_000_000:
                marathon = True
            attempts = stats.get("attempts", 0) or 0
            cracked_flag = stats.get("cracked", False)
            if attempts >= 5 and cracked_flag:
                stubborn_hunter = True
            history = stats.get("history") or []
            for h in history:
                if h.get("result") != "Cracked":
                    continue
                dur = h.get("duration") or 0
                try:
                    dur = float(dur)
                except Exception:
                    dur = 0
                if dur > 0 and dur < 10.0:
                    speed_demon = True

        best_wordlist_rate = 0.0
        best_wordlist_runs = 0
        for _, wstats in self.wordlist_stats.items():
            runs = int(wstats.get("runs", 0) or 0)
            cracks_w = int(wstats.get("cracks", 0) or 0)
            if runs <= 0:
                continue
            rate = (cracks_w * 100.0) / float(runs)
            if rate > best_wordlist_rate:
                best_wordlist_rate = rate
                best_wordlist_runs = runs

        def add_ach(id_, name, desc, icon, unlocked):
            ach.append(
                {
                    "id": id_,
                    "name": name,
                    "desc": desc,
                    "icon": icon,
                    "unlocked": bool(unlocked),
                }
            )

        add_ach(
            "first_blood",
            "First Blood",
            "Crack your first network.",
            "[KEY]",
            cracked >= 1,
        )
        add_ach(
            "ten_cracks",
            "Serial Cracker",
            "Crack 10 or more networks.",
            "[TARGET]",
            cracked >= 10,
        )
        add_ach(
            "marathoner",
            "Marathoner",
            "Spend over 1M words on a single SSID.",
            "[CARD]",
            marathon,
        )
        add_ach(
            "speed_demon",
            "Speed Demon",
            "Crack a network in under 10 seconds.",
            "[FAST]",
            speed_demon,
        )
        add_ach(
            "stubborn_hunter",
            "Stubborn Hunter",
            "Crack a network after 5+ attempts.",
            "[FOX]",
            stubborn_hunter,
        )
        add_ach(
            "long_runner",
            "Long Runner",
            "Process at least 10M words or 50 handshakes.",
            "[SIGNAL]",
            (total_words >= 10_000_000) or (processed >= 50),
        )
        add_ach(
            "strategist",
            "Strategist",
            "Use a wordlist with >50% success over at least 5 runs.",
            "[STRATEGY]",
            (best_wordlist_runs >= 5 and best_wordlist_rate > 50.0),
        )

        return ach

    def _record_job_history(
        self,
        pcap_file: Optional[str],
        ssid: Optional[str],
        result: str,
        started_at: Optional[float],
        finished_at: Optional[float],
        attempts: int,
        duration: float,
    ):
        """
        Track a compact timeline of completed jobs (one entry per pcap processed).
        """
        try:
            entry = {
                "ssid": ssid or "",
                "pcap": os.path.basename(pcap_file) if pcap_file else "",
                "result": result or "",
                "started_at": float(started_at or 0.0),
                "finished_at": float(finished_at or 0.0),
                "duration": float(duration or 0.0),
                "attempts": int(attempts or 0),
            }
        except Exception:
            return

        self.job_history.append(entry)
        if len(self.job_history) > self.max_job_history:
            self.job_history.pop(0)

    # ------------------------------------------------------------------
    # Pwnagotchi hooks
    # ------------------------------------------------------------------
    @staticmethod
    def _compat_parse_toml_value(raw_value):
        """Parse the small scalar/list subset used by this plugin without depending on toml."""
        value = str(raw_value or "").strip()
        lower = value.lower()
        if lower == "true":
            return True
        if lower == "false":
            return False
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            try:
                return ast.literal_eval(value)
            except Exception:
                return value[1:-1]
        try:
            if re.fullmatch(r"[-+]?\d+", value):
                return int(value)
            if re.fullmatch(r"[-+]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][-+]?\d+)?", value):
                return float(value)
        except Exception:
            pass
        if value.startswith("[") and value.endswith("]"):
            try:
                # This is enough for string-only lists such as mutator_custom_words.
                return ast.literal_eval(value)
            except Exception:
                return value
        return value

    def _effective_plugin_options(self, options):
        """
        Get plugin settings from both Pwnagotchi and config.toml.

        Important: the explicit config.toml block wins. Some Pwnagotchi builds
        supply stale/default options for a plugin when its filename/class naming
        differs in case, which previously overrode a valid
        main.plugins.Bruteforcer.* block and left the mutator at 50000.
        """
        merged = {}
        try:
            if isinstance(options, dict):
                merged.update(options)
            else:
                merged.update(dict(options or {}))
        except Exception:
            pass

        config_path = "/etc/pwnagotchi/config.toml"
        raw_text = ""
        toml_blocks = {}
        try:
            with open(config_path, "r", encoding="utf-8", errors="ignore") as handle:
                raw_text = handle.read()
        except Exception as exc:
            self._log_console(
                f"[bruteforce] Could not read config compatibility block: {exc}",
                "error",
            )
            return merged

        # First use a TOML parser when installed, then always run the lightweight
        # dotted-key reader below. The latter is deliberate: it makes the plugin
        # work even on images that do not expose a Python toml module to plugins.
        try:
            import toml
            cfg = toml.loads(raw_text)
            plugins_cfg = (cfg.get("main") or {}).get("plugins") or {}
            for key in ("bruteforce", "bruteforcer", "Bruteforcer"):
                block = plugins_cfg.get(key)
                if isinstance(block, dict):
                    toml_blocks[key] = dict(block)
        except Exception:
            pass

        direct_blocks = {"bruteforce": {}, "bruteforcer": {}, "Bruteforcer": {}}
        pattern = re.compile(
            r"^\s*main\.plugins\.(bruteforce|bruteforcer|Bruteforcer)\.([A-Za-z0-9_-]+)\s*=\s*(.*?)\s*$"
        )
        for raw_line in raw_text.splitlines():
            match = pattern.match(raw_line)
            if not match:
                continue
            plugin_name, option_name, raw_value = match.groups()
            direct_blocks[plugin_name][option_name] = self._compat_parse_toml_value(raw_value)

        # Compatibility order: legacy names first, current spelling last.
        # Explicit config always wins over framework-supplied defaults.
        for key in ("bruteforce", "bruteforcer", "Bruteforcer"):
            block = toml_blocks.get(key)
            if isinstance(block, dict):
                merged.update(block)
            merged.update(direct_blocks.get(key, {}))

        return merged

    def on_configure(self, options):
        self.options = self._effective_plugin_options(options)

        # Generic paths / global settings
        self.wordlist_folder = self.options.get("wordlist_folder", self.wordlist_folder)
        self.handshake_dir = self.options.get("handshake_dir", self.handshake_dir)
        self.delay_between_attempts = self.options.get(
            "delay_between_attempts", self.delay_between_attempts
        )
        self.wordlist_profiles = self.options.get("wordlist_profiles", self.wordlist_profiles)

        self.env_favorites_path = self.options.get(
            "env_favorites_path", self.env_favorites_path
        )
        self.progress_file = self.options.get("progress_file", self.progress_file)

        try:
            self.env_favorites_max = int(
                self.options.get("env_favorites_max", self.env_favorites_max)
            )
        except Exception:
            pass

        try:
            self.retry_limit = int(
                self.options.get("retry_limit", self.retry_limit)
            )
        except Exception:
            pass

        # Dashboard port override
        try:
            self.dashboard_port = int(self.options.get("dashboard_port", self.dashboard_port))
        except Exception:
            pass

        # Fan dashboard telemetry (written by fan_control.py). Defaults work
        # with the companion fan telemetry version; no config change needed.
        self.fan_status_path = str(
            self.options.get("fan_status_path", self.fan_status_path) or self.fan_status_path
        )
        try:
            self.fan_status_stale_seconds = max(
                5, int(self.options.get("fan_status_stale_seconds", self.fan_status_stale_seconds))
            )
        except Exception:
            pass

        # High-level mutator profile (fast / balanced / heavy)
        profile_opt = self.options.get("mutator_profile", self.mutator_profile)
        if isinstance(profile_opt, str):
            profile = profile_opt.lower()
        else:
            profile = str(profile_opt).lower()
        if profile not in ("fast", "balanced", "heavy"):
            profile = self.mutator_profile
        self.mutator_profile = profile
        self._apply_mutator_profile(self.mutator_profile)

        # Mutator options
        self.mutator_enabled = bool(
            self.options.get("mutator_enabled", self.mutator_enabled)
        )
        try:
            self.mutator_max_words = int(
                self.options.get("mutator_max_words", self.mutator_max_words)
            )
        except Exception:
            pass
        self.mutator_include_base64 = bool(
            self.options.get(
                "mutator_include_base64", self.mutator_include_base64
            )
        )
        self.mutator_include_years = bool(
            self.options.get("mutator_include_years", self.mutator_include_years)
        )
        leet_mode = self.options.get("mutator_leet_mode", self.mutator_leet_mode)
        if leet_mode in ("off", "light", "heavy"):
            self.mutator_leet_mode = leet_mode

        # New mutator options (all optional in config)
        self.mutator_include_rot13 = bool(
            self.options.get("mutator_include_rot13", self.mutator_include_rot13)
        )
        self.mutator_include_hex = bool(
            self.options.get("mutator_include_hex", self.mutator_include_hex)
        )
        self.mutator_include_separators = bool(
            self.options.get("mutator_include_separators", self.mutator_include_separators)
        )
        self.mutator_include_reversed = bool(
            self.options.get("mutator_include_reversed", self.mutator_include_reversed)
        )
        self.mutator_include_case_swaps = bool(
            self.options.get("mutator_include_case_swaps", self.mutator_include_case_swaps)
        )
        self.mutator_use_env_favorites = bool(
            self.options.get("mutator_use_env_favorites", self.mutator_use_env_favorites)
        )
        self.mutator_ssid_splits = bool(
            self.options.get("mutator_ssid_splits", self.mutator_ssid_splits)
        )

        # Custom seed words for the mutator
        custom_words = self.options.get("mutator_custom_words", self.mutator_custom_words)
        if isinstance(custom_words, list):
            self.mutator_custom_words = [str(w).strip() for w in custom_words if str(w).strip()]
        elif isinstance(custom_words, str):
            self.mutator_custom_words = [w.strip() for w in custom_words.split(",") if w.strip()]
        else:
            self.mutator_custom_words = []

        # v3.3 Mutator Lab controls. They are optional and preserve prior settings
        # if absent from config.toml.
        strategy = str(self.options.get("mutator_strategy", self.mutator_strategy) or self.mutator_strategy).lower()
        self.mutator_strategy = strategy if strategy in ("smart", "compatibility", "thorough") else "smart"
        try:
            self.mutator_min_length = max(8, min(int(self.options.get("mutator_min_length", self.mutator_min_length)), 63))
            self.mutator_max_length = max(self.mutator_min_length, min(int(self.options.get("mutator_max_length", self.mutator_max_length)), 63))
            self.mutator_token_pair_limit = max(1, min(int(self.options.get("mutator_token_pair_limit", self.mutator_token_pair_limit)), 24))
            self.mutator_year_start = max(1990, min(int(self.options.get("mutator_year_start", self.mutator_year_start)), 2100))
            self.mutator_year_end = max(0, min(int(self.options.get("mutator_year_end", self.mutator_year_end)), 2100))
            self.mutator_preview_count = max(0, min(int(self.options.get("mutator_preview_count", self.mutator_preview_count)), 40))
        except Exception:
            pass
        self.mutator_include_token_pairs = self._option_bool(self.options.get("mutator_include_token_pairs", self.mutator_include_token_pairs), self.mutator_include_token_pairs)
        self.mutator_include_numeric_suffixes = self._option_bool(self.options.get("mutator_include_numeric_suffixes", self.mutator_include_numeric_suffixes), self.mutator_include_numeric_suffixes)
        def _mutator_list_option(value):
            if isinstance(value, (list, tuple, set)):
                return [str(v).strip() for v in value if str(v).strip()]
            if isinstance(value, str):
                return [v.strip() for v in value.split(",") if v.strip()]
            return []
        self.mutator_custom_prefixes = _mutator_list_option(self.options.get("mutator_custom_prefixes", self.mutator_custom_prefixes))
        self.mutator_custom_suffixes = _mutator_list_option(self.options.get("mutator_custom_suffixes", self.mutator_custom_suffixes))

        # Queue control / runtime governor / preflight options.
        self.defer_seconds = int(self.options.get("defer_seconds", self.defer_seconds) or self.defer_seconds)
        self.skip_cooldown_seconds = int(self.options.get("skip_cooldown_seconds", self.skip_cooldown_seconds) or self.skip_cooldown_seconds)
        self.governor_enabled = self._option_bool(self.options.get("governor_enabled", self.governor_enabled), self.governor_enabled)
        try:
            self.governor_max_temp_c = float(self.options.get("governor_max_temp_c", self.governor_max_temp_c))
            self.governor_min_available_mem_mb = int(self.options.get("governor_min_available_mem_mb", self.governor_min_available_mem_mb))
            self.governor_max_swap_used_mb = int(self.options.get("governor_max_swap_used_mb", self.governor_max_swap_used_mb))
            self.governor_max_load_1m = float(self.options.get("governor_max_load_1m", self.governor_max_load_1m))
            self.governor_poll_seconds = int(self.options.get("governor_poll_seconds", self.governor_poll_seconds))
        except Exception:
            pass
        self.preflight_enabled = self._option_bool(self.options.get("preflight_enabled", self.preflight_enabled), self.preflight_enabled)
        try:
            self.preflight_timeout = int(self.options.get("preflight_timeout", self.preflight_timeout))
            self.wordlist_min_runs_for_ranking = int(self.options.get("wordlist_min_runs_for_ranking", self.wordlist_min_runs_for_ranking))
        except Exception:
            pass
        self.wordlist_line_count_enabled = self._option_bool(
            self.options.get("wordlist_line_count_enabled", self.wordlist_line_count_enabled),
            self.wordlist_line_count_enabled,
        )
        overrides = self.options.get("ssid_overrides", self.ssid_overrides)
        self.ssid_overrides = dict(overrides) if isinstance(overrides, dict) else {}

        # Intelligence Pack controls. Analytics are safe to leave on; active
        # scheduling changes are opt-in so v3.1 behavior remains preserved.
        self.adaptive_queue_enabled = self._option_bool(self.options.get("adaptive_queue_enabled", self.adaptive_queue_enabled), self.adaptive_queue_enabled)
        self.dedupe_auto_skip = self._option_bool(self.options.get("dedupe_auto_skip", self.dedupe_auto_skip), self.dedupe_auto_skip)
        self.epaper_status_mode = self._option_bool(self.options.get("epaper_status_mode", self.epaper_status_mode), self.epaper_status_mode)
        self.journal_path = self.options.get("journal_path", self.journal_path)
        try:
            self.dedupe_scan_seconds = max(10, int(self.options.get("dedupe_scan_seconds", self.dedupe_scan_seconds)))
            self.epaper_status_max_chars = max(16, int(self.options.get("epaper_status_max_chars", self.epaper_status_max_chars)))
            self.adaptive_queue_max_bonus = max(1, int(self.options.get("adaptive_queue_max_bonus", self.adaptive_queue_max_bonus)))
        except Exception:
            pass

        self._log_console(
            f"[bruteforce] Configured mutator: profile={self.mutator_profile}, "
            f"enabled={self.mutator_enabled}, max_words={self.mutator_max_words}"
        )


    def _capture_dashboard_inventory(self):
        """Build a capture view with passive quality / duplicate intelligence."""
        self._refresh_duplicate_index()
        items = []
        now = time.time()
        try:
            files = []
            for root, _dirs, names in os.walk(self.handshake_dir):
                for name in names:
                    if name.endswith(".pcap"):
                        files.append(os.path.join(root, name))
        except Exception:
            files = []
        for path in files:
            try:
                stat = os.stat(path)
                modified_ts = stat.st_mtime
                size_kb = round(stat.st_size / 1024.0, 1)
            except Exception:
                modified_ts = 0.0
                size_kb = 0.0
            ssid = self._parse_ssid_from_filename(path) or "?"
            stats = self.ssid_stats.get(ssid, {}) if isinstance(self.ssid_stats, dict) else {}
            health = (self.capture_health or {}).get(path, {}) or {}
            health_status = str(health.get("status", "") or "").lower()
            deferred_until = float((self.deferred_files or {}).get(path, 0) or 0)
            if path == self.current_pcap:
                state, note = "running", self.status or "Running"
            elif deferred_until > now:
                state, note = "deferred", "Deferred until " + time.strftime("%H:%M:%S", time.localtime(deferred_until))
            elif health_status in ("bad", "no_handshake", "marked_bad"):
                state, note = "bad", health.get("detail", "Bad capture")
            elif health_status == "needs_review":
                state, note = "review", health.get("detail", "Needs review")
            elif path in self.processed_files_set:
                last = str(stats.get("last_result", "") or "")
                if stats.get("cracked"):
                    state = "cracked"
                elif "timeout" in last.lower():
                    state = "timeout"
                elif "preflight" in last.lower():
                    state = "bad"
                else:
                    state = "failed"
                note = health.get("detail", "Processed") or "Processed"
            else:
                state, note = "pending", health.get("detail", "Waiting in queue") or "Waiting in queue"
            quality = self._capture_quality(path, ssid)
            priority = self._adaptive_priority_details(path, ssid)
            duplicate = self._duplicate_info(path)
            items.append({
                "path": path,
                "file": os.path.basename(path),
                "ssid": ssid,
                "state": state,
                "note": str(note)[:220],
                "attempts": int(stats.get("attempts", 0) or 0),
                "last_result": str(stats.get("last_result", "") or "-"),
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(modified_ts)) if modified_ts else "-",
                "modified_ts": modified_ts,
                "size_kb": size_kb,
                "quality": quality,
                "priority": priority.get("score", 0),
                "priority_reasons": priority.get("reasons", []),
                "duplicate": duplicate,
            })
        return sorted(items, key=lambda item: item.get("modified_ts", 0), reverse=True)

    def on_loaded(self):
        self.load_progress()
        self._recover_interrupted_journal()
        self._log_console("[bruteforce] Plugin loaded.")
        self.update_total_files()
        self._write_env_favorites_file()
        self.dashboard_thread.start()
        self.start_monitoring()

    def on_unloaded(self):
        self._log_console("[bruteforce] Plugin unloaded.")
        self.stop_event.set()

    # ------------------------------------------------------------------
    # Flask dashboard
    # ------------------------------------------------------------------
    def start_dashboard(self):
        @self.app.route("/")
        def dashboard():
            last_ssid = self.last_cracked_ssid or "-"
            last_key_masked = self.mask_key(self.last_cracked_key)
            return render_template_string(
                DASHBOARD_HTML,
                status=self.status,
                progress=self.progress,
                processed_files=f"{self.processed_files}/{self.total_files}",
                words_processed=self.words_processed_abbr,
                cracked_count=self.cracked_count,
                failed_count=self.failed_count,
                last_cracked_ssid=last_ssid,
                last_cracked_key=last_key_masked,
                logs=self.log_buffer,
            )

        @self.app.route("/mutator")
        def mutator_lab():
            return render_template_string(MUTATOR_LAB_HTML)

        @self.app.route("/api/mutator")
        def api_mutator():
            return jsonify(self._mutator_lab_snapshot())

        @self.app.route("/networks")
        def networks():
            wl_stats_with_label = {}
            for key, val in self.wordlist_stats.items():
                if not isinstance(val, dict):
                    continue
                name = val.get("name") or key
                mode = val.get("mode", "plain")
                label = f"{name} ({mode})" if mode else name
                s = dict(val)
                s["label"] = label
                s.update(self._wordlist_effectiveness(key, s))
                wl_stats_with_label[key] = s

            return render_template_string(
                NETWORKS_HTML,
                ssid_stats=self.ssid_stats,
                wordlist_stats=wl_stats_with_label,
            )

        @self.app.route("/ssid/<path:ssid>")
        def ssid_detail(ssid):
            stats = self.ssid_stats.get(ssid)
            tag = f"[SSID:{ssid}]"
            logs = [line for line in self.log_buffer if tag in line]
            masked_key = ""
            mutator = {}
            history = []
            if stats and isinstance(stats, dict):
                last_key = stats.get("last_key")
                if last_key:
                    masked_key = self.mask_key(last_key)
                mutator = stats.get("mutator", {})
                history = stats.get("history", []) or []
            history_json = json.dumps(history)
            return render_template_string(
                SSID_DETAIL_HTML,
                ssid=ssid,
                stats=stats or {},
                logs=logs,
                masked_key=masked_key,
                mutator=mutator,
                history_json=history_json,
            )


        @self.app.route("/captures")
        def captures():
            return render_template_string(CAPTURES_HTML)

        @self.app.route("/api/captures")
        def api_captures():
            state_filter = (request.args.get("status", "all") or "all").strip().lower()
            search = (request.args.get("q", "") or "").strip().lower()
            try:
                limit = int(request.args.get("limit", 400) or 400)
            except Exception:
                limit = 400
            limit = max(25, min(limit, 1000))
            items = self._capture_dashboard_inventory()
            if state_filter != "all":
                items = [item for item in items if item.get("state") == state_filter]
            if search:
                items = [item for item in items if search in (item.get("ssid", "") + " " + item.get("file", "")).lower()]
            return jsonify({
                "items": items[:limit],
                "total": len(items),
                "generated_at": time.strftime("%H:%M:%S"),
            })

        @self.app.route("/intelligence")
        def intelligence():
            return render_template_string(INTELLIGENCE_HTML)

        @self.app.route("/reports")
        def reports():
            return render_template_string(REPORTS_HTML)

        @self.app.route("/api/intelligence")
        def api_intelligence():
            inventory = self._capture_dashboard_inventory()
            grades = {"A": 0, "B": 0, "C": 0, "D": 0, "X": 0}
            for item in inventory:
                grade = str((item.get("quality") or {}).get("grade", "D"))
                grades[grade] = grades.get(grade, 0) + 1
            self._update_runtime_health()
            return jsonify({
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "quality_counts": grades,
                "capture_total": len(inventory),
                "top_queue": sorted([x for x in inventory if x.get("state") in ("pending", "running")], key=lambda x: -int(x.get("priority", 0) or 0))[:15],
                "events": self.event_timeline[-80:],
                "resource_history": self.resource_history[-180:],
                "resources": self.last_resource_snapshot,
                "mutator": self._mutator_breakdown(),
                "wordlist_lab": self._wordlist_lab(),
                "duplicates": [
                    {"best": os.path.basename(g.get("best", "")), "count": len(g.get("paths", [])), "files": [os.path.basename(x) for x in g.get("paths", [])]}
                    for g in self.duplicate_groups.values()
                ],
                "journal": self.active_job_journal,
                "recovery_note": self.recovery_note,
                "adaptive_queue_enabled": self.adaptive_queue_enabled,
                "dedupe_auto_skip": self.dedupe_auto_skip,
                "epaper_preview": self._epaper_summary(),
            })

        @self.app.route("/api/reports")
        def api_reports():
            return jsonify(self._reports_payload())

        @self.app.route("/api/lab")
        def api_lab():
            return jsonify(self._wordlist_lab())

        @self.app.route("/api/metrics")
        def api_metrics():
            processed = self.processed_files
            crack_rate = (
                self.cracked_count / float(processed) * 100.0 if processed else 0.0
            )
            # Prefer the last completed tested-keys/time calculation. Fall back
            # to a short measured sample history; never average unverified text rates.
            recent_measured = [float(v) for v in self.wps_data[-20:] if float(v or 0) > 0]
            avg_wps = (
                float(self.last_completed_wps)
                if float(self.last_completed_wps or 0) > 0
                else (float(sum(recent_measured) / len(recent_measured)) if recent_measured else 0.0)
            )
            avg_elapsed = (
                float(sum(self.elapsed_time_data) / len(self.elapsed_time_data))
                if self.elapsed_time_data
                else 0.0
            )
            queue = self.get_queue_snapshot()
            lb = self.compute_leaderboard()
            achievements = self.compute_achievements()

            # Mutator global stats
            mut_runs = 0
            mut_words = 0
            mut_cracks = 0
            mut_time = 0.0
            for _ssid, s in self.ssid_stats.items():
                if not isinstance(s, dict):
                    continue
                m = s.get("mutator") or {}
                try:
                    mut_runs += int(m.get("runs") or 0)
                    mut_words += int(m.get("total_words") or 0)
                    mut_cracks += int(m.get("cracks") or 0)
                    mut_time += float(m.get("time_seconds") or 0.0)
                except Exception:
                    continue
            if self.cracked_count:
                mut_share = (mut_cracks * 100.0) / float(self.cracked_count)
            else:
                mut_share = 0.0
            mut_words_abbr = self.abbreviate_number(mut_words) if mut_words else "0"
            env_count = len(self.env_favorites or {})

            features = []
            if getattr(self, "mutator_include_base64", False):
                features.append("b64")
            if getattr(self, "mutator_include_rot13", False):
                features.append("rot13")
            if getattr(self, "mutator_include_hex", False):
                features.append("hex")
            if getattr(self, "mutator_include_reversed", False):
                features.append("rev")
            if getattr(self, "mutator_include_case_swaps", False):
                features.append("swap")
            if getattr(self, "mutator_include_separators", False):
                features.append("seps")
            if getattr(self, "mutator_include_years", False):
                features.append("years")
            if getattr(self, "mutator_use_env_favorites", False):
                features.append("favorites")
            if getattr(self, "mutator_ssid_splits", False):
                features.append("ssid-splits")
            mut_features_str = ", ".join(features) if features else "none"

            # Status distribution for the result-mix bar
            status_counts = {"cracked": 0, "failed": 0, "timeout": 0, "pending": 0}
            for ssid, stats in self.ssid_stats.items():
                if stats.get("cracked"):
                    status_counts["cracked"] += 1
                else:
                    last = (stats.get("last_result") or "").strip()
                    if last == "Timeout":
                        status_counts["timeout"] += 1
                    elif last == "Failed":
                        status_counts["failed"] += 1
                    else:
                        status_counts["pending"] += 1
            total_status = sum(status_counts.values()) or 1
            pct_cracked = (status_counts["cracked"] * 100.0) / total_status
            pct_failed = (status_counts["failed"] * 100.0) / total_status
            pct_timeout = (status_counts["timeout"] * 100.0) / total_status
            pct_pending = (status_counts["pending"] * 100.0) / total_status

            timeline_values = []
            timeline_labels = []
            for ssid, stats in self.ssid_stats.items():
                history = stats.get("history") or []
                for h in history:
                    result = h.get("result") or ""
                    if result == "Cracked":
                        val = 3
                    elif result == "Timeout":
                        val = 2
                    elif result == "Failed":
                        val = 1
                    else:
                        val = 0
                    timeline_values.append(val)
                    attempt_no = h.get("attempt")
                    label = f"{ssid} #{attempt_no} {result}"
                    timeline_labels.append(label)

            now_ts = time.time()
            if self.current_job_start:
                current_elapsed = max(0.0, now_ts - self.current_job_start)
            else:
                current_elapsed = 0.0

            current_job = {
                "ssid": self.current_ssid or "",
                "pcap": os.path.basename(self.current_pcap)
                if self.current_pcap
                else "",
                "status": self.status,
                "attempt": self.current_job_attempt,
                "retry_limit": self.retry_limit,
                "started_at": self.current_job_start or 0.0,
                "elapsed": current_elapsed,
            }

            history_slice = self.job_history[-20:] if self.job_history else []

            self._update_runtime_health()
            snapshot = self.last_resource_snapshot or {}
            temp = snapshot.get("temp_c")
            temp_f = snapshot.get("temp_f")
            temp_text = f"{temp_f:.1f} F" if isinstance(temp_f, (int, float)) else "n/a"
            fan_snapshot = snapshot.get("fan") or {}
            if fan_snapshot.get("available") and not fan_snapshot.get("stale"):
                fan_pct = fan_snapshot.get("fan_percent")
                fan_rpm = fan_snapshot.get("fan_rpm")
                pct_text = f"{fan_pct:.0f}%" if isinstance(fan_pct, (int, float)) else "?"
                rpm_text = f"{fan_rpm:.0f} RPM" if isinstance(fan_rpm, (int, float)) else "? RPM"
                fan_text = f"Fan {pct_text} | {rpm_text}"
            elif fan_snapshot.get("available"):
                fan_text = "Fan telemetry stale"
            else:
                fan_text = "Fan telemetry unavailable"
            resource_summary = (
                f"RAM {snapshot.get('available_mem_mb', 0)} MB avail  |  "
                f"Swap {snapshot.get('swap_used_mb', 0)} MB  |  "
                f"Temp {temp_text}  |  {fan_text}  |  "
                f"Load {snapshot.get('load_1m', 0.0):.2f}"
            )
            capture_counts = self._capture_health_counts()
            wordlist_summary = []
            for key, stats in (self.wordlist_stats or {}).items():
                if not isinstance(stats, dict):
                    continue
                eff = self._wordlist_effectiveness(key, stats)
                name = stats.get("name") or key.split(":", 1)[0]
                mode = stats.get("mode", "plain")
                label = f"{name} ({mode})" if mode else name
                wordlist_summary.append({
                    "label": label,
                    "runs": eff.get("runs", 0),
                    "cracks": eff.get("cracks", 0),
                    "confidence": eff.get("confidence", 0.0),
                    "eligible": eff.get("eligible", False),
                    "estimated_words": eff.get("estimated_words", 0),
                    "estimated_words_abbr": self.abbreviate_number(eff.get("estimated_words", 0)) if eff.get("estimated_words", 0) else "0",
                    "avg_duration": eff.get("avg_duration", 0.0),
                    "measured_wps": eff.get("measured_wps", 0.0),
                })
            wordlist_summary.sort(key=lambda item: (not item.get("eligible"), -float(item.get("confidence", 0.0)), -int(item.get("cracks", 0)), -int(item.get("runs", 0))))
            self._refresh_duplicate_index()
            intelligence_summary = {
                "events": self.event_timeline[-30:],
                "resource_history": self.resource_history[-120:],
                "mutator_breakdown": self._mutator_breakdown(),
                "recovery_note": self.recovery_note,
                "duplicate_groups": [
                    {"best": os.path.basename(g.get("best", "")), "count": len(g.get("paths", []))}
                    for g in self.duplicate_groups.values()
                ][:20],
                "adaptive_queue_enabled": self.adaptive_queue_enabled,
                "dedupe_auto_skip": self.dedupe_auto_skip,
                "epaper_preview": self._epaper_summary(),
            }

            return jsonify(
                {
                    "status": self.status,
                    "progress": self.progress,
                    "processed_display": f"{self.processed_files}/{self.total_files}",
                    "words_processed": self.words_processed_abbr,
                    "cracked_count": self.cracked_count,
                    "failed_count": self.failed_count,
                    "wps_data": self.wps_data,
                    "progress_data": self.progress_data,
                    "elapsed_time_data": self.elapsed_time_data,
                    "last_cracked_ssid": self.last_cracked_ssid or "",
                    "last_cracked_key_masked": self.mask_key(self.last_cracked_key),
                    "crack_rate": crack_rate,
                    "avg_wps": avg_wps,
                    "current_wps": self.current_wps,
                    "current_wps_source": self.current_wps_source,
                    "current_wps_confidence": self.current_wps_confidence,
                    "current_aircrack_reported_wps": self.current_aircrack_reported_wps,
                    "current_wps_difference_pct": self.current_wps_difference_pct,
                    "last_completed_wps": self.last_completed_wps,
                    "last_completed_keys_tested": self.last_completed_keys_tested,
                    "last_completed_duration": self.last_completed_duration,
                    "avg_elapsed": avg_elapsed,
                    "processed_count": processed,
                    "current_ssid": self.current_ssid or "",
                    "current_pcap": os.path.basename(self.current_pcap)
                    if self.current_pcap
                    else "",
                    "current_job": current_job,
                    "queue": queue,
                    "leader_fast_ssid": lb.get("fast_ssid") or "",
                    "leader_fast_duration": lb.get("fast_duration"),
                    "leader_fast_wordlist": lb.get("fast_wordlist") or "",
                    "leader_best_wordlist_label": lb.get("best_label") or "",
                    "leader_best_wordlist_rate": lb.get("best_rate"),
                    "leader_best_wordlist_cracks": lb.get("best_cracks") or 0,
                    "leader_best_wordlist_runs": lb.get("best_runs") or 0,
                    "leader_stubborn_ssid": lb.get("stubborn_ssid") or "",
                    "leader_stubborn_attempts": lb.get("stubborn_attempts") or 0,
                    "leader_stubborn_status": lb.get("stubborn_status") or "",
                    "achievements": achievements,
                    "timeline_values": timeline_values,
                    "timeline_labels": timeline_labels,
                    "status_counts": status_counts,
                    "pct_cracked": pct_cracked,
                    "pct_failed": pct_failed,
                    "pct_timeout": pct_timeout,
                    "pct_pending": pct_pending,
                    "job_history": history_slice,
                    "mutator_enabled": self.mutator_enabled,
                    "mutator_profile": self.mutator_profile,
                    "mutator_max_words": self.mutator_max_words,
                    "mutator_runs": mut_runs,
                    "mutator_words": mut_words,
                    "mutator_words_abbr": mut_words_abbr,
                    "mutator_cracks": mut_cracks,
                    "mutator_share": mut_share,
                    "mutator_env_count": env_count,
                    "mutator_features": mut_features_str,
                    "mutator_lab": self._mutator_lab_snapshot(),
                    "manual_paused": self.manual_paused,
                    "pause_detail": self.pause_detail,
                    "governor_enabled": self.governor_enabled,
                    "governor_blocked": self.governor_blocked,
                    "governor_detail": self.governor_detail,
                    "resource_summary": resource_summary,
                    "capture_health_counts": capture_counts,
                    "preflight_enabled": self.preflight_enabled,
                    "resources": snapshot,
                    "queue_depth": len(queue),
                    "current_wordlist_key": self.current_wordlist_key or "",
                    "current_wordlist_label": self.current_wordlist_key or "Waiting",
                    "current_wordlist_progress": self.current_wordlist_progress or 0.0,
                    "wordlist_summary": wordlist_summary[:6],
                    "log_tail": self.log_buffer[-40:],
                    "intelligence": intelligence_summary,
                }
            )

        @self.app.route("/api/control/<action>", methods=["POST"])
        def api_control(action):
            current = self.current_pcap
            if action == "pause":
                self.manual_paused = True
                self.pause_detail = "Manual pause requested. Current wordlist may finish first."
            elif action == "resume":
                self.manual_paused = False
                self.pause_detail = "Queue is ready."
            elif action == "skip":
                if not current:
                    return jsonify({"error": "No active capture to skip"}), 409
                self.skip_current_requested = True
                self._defer_capture(current, self.skip_cooldown_seconds, "Skipped")
                self._terminate_current_task()
            elif action == "defer":
                if not current:
                    return jsonify({"error": "No active capture to defer"}), 409
                self.defer_current_requested = True
                self.skip_current_requested = True
                self._defer_capture(current, self.defer_seconds, "Deferred")
                self._terminate_current_task()
            elif action == "requeue-current":
                if not current:
                    return jsonify({"error": "No active capture to requeue"}), 409
                self.requeue_current_requested = True
                self.skip_current_requested = True
                self._requeue_capture(current)
                self._terminate_current_task()
            elif action == "requeue-latest":
                latest = self.job_history[-1] if self.job_history else {}
                pcap = self._find_capture_by_basename(latest.get("pcap", ""))
                if not pcap:
                    return jsonify({"error": "No completed capture found to requeue"}), 409
                self._requeue_capture(pcap)
            elif action == "mark-bad":
                if not current:
                    return jsonify({"error": "No active capture to mark bad"}), 409
                self.mark_bad_current_requested = True
                self.skip_current_requested = True
                self._terminate_current_task()
            else:
                return jsonify({"error": "Unknown action"}), 404
            self.save_progress()
            return jsonify({"ok": True, "action": action})

        @self.app.route("/api/requeue", methods=["POST"])
        def api_requeue():
            requested = request.args.get("path", "").strip()
            if not requested:
                return jsonify({"error": "Provide ?path=/full/path/to/capture.pcap or a capture filename"}), 400
            candidate = requested if os.path.isabs(requested) else self._find_capture_by_basename(requested)
            if candidate and self._requeue_capture(candidate):
                return jsonify({"ok": True, "path": candidate})
            return jsonify({"error": "Could not requeue capture"}), 400

        @self.app.route("/api/export/json")
        def api_export_json():
            payload = {
                "exported_at": time.time(),
                "ssid_stats": self.ssid_stats,
                "wordlist_stats": self.wordlist_stats,
                "capture_health": self.capture_health,
                "job_history": self.job_history,
                "processed_files": list(self.processed_files_set),
                "event_timeline": self.event_timeline,
                "resource_history": self.resource_history,
                "duplicate_groups": self.duplicate_groups,
                "recovery_note": self.recovery_note,
            }
            response = Response(json.dumps(payload, indent=2, sort_keys=True), mimetype="application/json")
            response.headers["Content-Disposition"] = "attachment; filename=bruteforcer-stats.json"
            return response

        @self.app.route("/api/export/csv")
        def api_export_csv():
            stream = io.StringIO()
            writer = csv.writer(stream)
            writer.writerow([
                "ssid", "attempts", "cracked", "last_result", "success_wordlist",
                "total_words", "last_duration_s", "mutator_runs", "mutator_words", "mutator_cracks"
            ])
            for ssid, stats in sorted(self.ssid_stats.items()):
                m = stats.get("mutator") or {}
                writer.writerow([
                    ssid,
                    stats.get("attempts", 0),
                    stats.get("cracked", False),
                    stats.get("last_result", ""),
                    stats.get("success_wordlist", ""),
                    stats.get("total_words", 0),
                    stats.get("last_duration", 0),
                    m.get("runs", 0),
                    m.get("total_words", 0),
                    m.get("cracks", 0),
                ])
            response = Response(stream.getvalue(), mimetype="text/csv")
            response.headers["Content-Disposition"] = "attachment; filename=bruteforcer-stats.csv"
            return response

        @self.app.route("/reset", methods=["POST"])
        def reset():
            self.reset_progress()
            return redirect(url_for("dashboard"))

        try:
            port = getattr(self, "dashboard_port", DASHBOARD_PORT_DEFAULT)
            self.app.run(host=DASHBOARD_HOST, port=port, debug=False, use_reloader=False)
        except Exception as e:
            self._log_console(f"[bruteforce] Dashboard failed to start: {e}", "error")

    # ------------------------------------------------------------------
    # UI management
    # ------------------------------------------------------------------
    def on_ui_setup(self, ui):
        self.ui = ui
        ui_elements = {
            "bruteforce_status": ("BF:", self.status, (128, 60)),
            "bruteforce_progress": ("PR:", self.progress, (188, 60)),
            "bruteforce_result": ("RE:", self.result, (128, 68)),
            "bruteforce_total": (
                "TO:",
                f"{self.processed_files}/{self.total_files}",
                (188, 68),
            ),
            "bruteforce_cracked": (
                "CR:",
                f"{self.cracked_count}/{self.processed_files}",
                (133, 1),
            ),
            "bruteforce_step": ("", "Idle", (1, 13)),
        }
        for key, (label, value, position) in ui_elements.items():
            ui.add_element(
                key,
                LabeledValue(
                    color=BLACK,
                    label=label,
                    value=value,
                    position=position,
                    label_font=fonts.Bold,
                    text_font=fonts.Small,
                ),
            )

    def on_ui_update(self, ui):
        if self.ui:
            with ui._lock:
                ui.set("bruteforce_status", self.status)
                ui.set("bruteforce_progress", self.progress)
                ui.set("bruteforce_result", self.result)
                ui.set(
                    "bruteforce_total",
                    f"{self.processed_files}/{self.total_files}",
                )
                ui.set(
                    "bruteforce_cracked",
                    f"{self.cracked_count}/{self.processed_files or 1}",
                )
                ui.set("bruteforce_step", self._epaper_summary() if self.epaper_status_mode else self.status_message)

    # ------------------------------------------------------------------
    # Monitoring for new handshakes
    # ------------------------------------------------------------------
    def start_monitoring(self):
        self._log_console("[bruteforce] Starting handshake monitoring thread.")
        t = threading.Thread(target=self.monitor_handshakes, daemon=True)
        t.start()

    def monitor_handshakes(self):
        while not self.stop_event.is_set():
            if not self._wait_for_run_permission("queue"):
                break
            new_files = self.get_new_handshakes()
            scored = []
            for pcap_file in new_files:
                ssid = self._parse_ssid_from_filename(pcap_file) or "?"
                pri = self._compute_handshake_priority(pcap_file, ssid)
                scored.append((pri, pcap_file))
            scored.sort(key=lambda x: x[0])
            for _pri, pcap_file in scored:
                if not self._wait_for_run_permission("capture"):
                    break
                self.run_bruteforce(pcap_file)
                time.sleep(self.delay_between_attempts)
            time.sleep(10)

    def get_new_handshakes(self) -> Set[str]:
        all_pcap_files = {
            os.path.join(root, file)
            for root, _, files in os.walk(self.handshake_dir)
            for file in files
            if file.endswith(".pcap")
        }
        now = time.time()
        self.deferred_files = {p: until for p, until in self.deferred_files.items() if float(until or 0) > now}
        blocked_statuses = {"bad", "no_handshake", "needs_review", "marked_bad", "duplicate"}
        if self.dedupe_auto_skip:
            self._refresh_duplicate_index()
        runnable = set()
        for pcap in all_pcap_files - self.processed_files_set:
            if float(self.deferred_files.get(pcap, 0) or 0) > now:
                continue
            if self.dedupe_auto_skip:
                dup = self._duplicate_info(pcap)
                if dup.get("count", 1) > 1 and not dup.get("is_best"):
                    self._record_capture_health(pcap, self._parse_ssid_from_filename(pcap), "duplicate", "Auto-held duplicate; best capture is %s" % os.path.basename(dup.get("best", "")))
                    continue
            health = self.capture_health.get(pcap, {})
            if health.get("status") in blocked_statuses:
                continue
            runnable.add(pcap)
        return runnable

    # ------------------------------------------------------------------
    # Core cracking logic (with bad-capture + mutator error handling)
    # ------------------------------------------------------------------
    def run_bruteforce(self, pcap_file: str):
        if self.stop_event.is_set():
            return
        if not self._wait_for_run_permission("capture start"):
            return

        ssid = self._parse_ssid_from_filename(pcap_file)
        if not ssid:
            self._log_console(f"[bruteforce] Could not identify SSID for {pcap_file}", "error")
            self._record_capture_health(pcap_file, "", "needs_review", "Could not determine SSID from filename")
            return

        preflight = self.preflight_capture(pcap_file, ssid)
        if preflight.get("status") in ("bad", "no_handshake", "needs_review", "marked_bad"):
            result = f"Preflight: {preflight.get('status')}"
            self._record_job_history(pcap_file, ssid, result, time.time(), time.time(), 0, 0.0)
            self.processed_files_set.add(pcap_file)
            self.processed_files = len(self.processed_files_set)
            self.save_progress()
            self._log_ssid(ssid, f"[preflight] Skipping capture: {preflight.get('detail', '')}", "error")
            return

        cracked_keys_file = "/home/pi/cracked_keys.txt"

        self.current_pcap = pcap_file
        self.current_ssid = ssid
        self.manual_priority_files.discard(pcap_file)
        self._journal_write("capture_started", pcap_file, ssid, detail="Capture entered BruteForcer")
        self._record_event("queue", "Started capture %s" % os.path.basename(pcap_file), "info", ssid)

        words_before = self.words_processed
        cracked_key = None
        cracked_wordlist_key = None

        try:
            overall_start = time.time()
            self.current_job_start = overall_start
            self.current_job_attempt = 0

            for attempt in range(1, self.retry_limit + 1):
                if self.stop_event.is_set():
                    return

                self.current_job_attempt = attempt

                try:
                    wordlist_items = []
                    if self.wordlist_profiles:
                        for entry in self.wordlist_profiles:
                            if not isinstance(entry, dict):
                                continue
                            path = entry.get("path")
                            if not path:
                                continue
                            mode = entry.get("mode", "plain")
                            if os.path.isfile(path):
                                wordlist_items.append({"path": path, "mode": mode})
                    else:
                        for f in os.listdir(self.wordlist_folder):
                            full = os.path.join(self.wordlist_folder, f)
                            if os.path.isfile(full):
                                wordlist_items.append({"path": full, "mode": "plain"})
                    self._log_ssid(
                        ssid,
                        f"[bruteforce] {len(wordlist_items)} base wordlists found",
                    )
                except Exception as e:
                    self._log_ssid(
                        ssid, f"[bruteforce] Unable to list wordlists: {e}", "error"
                    )
                    return

                if not wordlist_items and not self.mutator_enabled:
                    self._log_ssid(
                        ssid, "[bruteforce] No wordlists available.", "error"
                    )
                    return

                mut_item = None
                if self.mutator_enabled:
                    mut_path = None
                    try:
                        mut_path = self.build_mutation_wordlist(ssid)
                    except Exception as e:
                        self._log_ssid(
                            ssid,
                            f"[mutator] Unexpected error building wordlist: {e}. Disabling mutator for this SSID.",
                            "error",
                        )
                        self.mutator_error_ssids.add(ssid)
                        mut_path = None
                    if mut_path:
                        mut_item = {"path": mut_path, "mode": "mutator"}

                env_item = None
                if os.path.isfile(self.env_favorites_path):
                    try:
                        if os.path.getsize(self.env_favorites_path) > 0:
                            env_item = {
                                "path": self.env_favorites_path,
                                "mode": "favorites",
                            }
                    except Exception:
                        pass

                ordered_real = (
                    self._get_wordlist_order(wordlist_items) if wordlist_items else []
                )

                combined = []
                if env_item:
                    combined.append(env_item)
                if mut_item:
                    combined.append(mut_item)
                combined.extend(ordered_real)
                wordlist_items = combined

                handshake_cracked = False
                timed_out = False
                bad_capture = False
                skipped_by_control = False
                self.last_wps_update_time = None
                start_time = time.time()

                self.update_step_status(
                    f"BF: Start {ssid} ({attempt}/{self.retry_limit})"
                )
                self._log_ssid(
                    ssid,
                    f"[bruteforce] Starting brute force (attempt {attempt}/{self.retry_limit})",
                )

                for item in wordlist_items:
                    if self.stop_event.is_set():
                        break
                    if handshake_cracked or timed_out or bad_capture:
                        break

                    path = item.get("path")
                    mode = item.get("mode", "plain")

                    base_wl_name = os.path.basename(path)
                    if mode == "mutator":
                        wl_name = "Mutator"
                        stats_key = "MutatorGlobal:mutator"
                    elif mode == "favorites":
                        wl_name = "EnvFavorites"
                        stats_key = "EnvFavorites:favorites"
                    else:
                        wl_name = base_wl_name
                        stats_key = f"{wl_name}:{mode}"

                    wl_stats = self.wordlist_stats.setdefault(
                        stats_key,
                        {"runs": 0, "cracks": 0, "name": wl_name, "mode": mode},
                    )
                    wl_stats["runs"] = wl_stats.get("runs", 0) + 1

                    if mode == "mutator":
                        label = "Mutator for {ssid}".format(ssid=ssid)
                    elif mode == "favorites":
                        label = "Env Favorites"
                    else:
                        label = (
                            f"{wl_name} ({mode})"
                            if mode != "plain"
                            else wl_name
                        )

                    if not self._wait_for_run_permission(f"wordlist {label}"):
                        return
                    if self.skip_current_requested:
                        skipped_by_control = True
                        break

                    self.update_step_status(f"WL: {label} {ssid}")
                    self.update_status("BRUTE", "0%", "")
                    self._log_ssid(ssid, f"[bruteforce] Running: {label}")
                    self.current_wordlist_key = stats_key
                    self.current_wordlist_progress = 0.0
                    self._reset_wps_for_wordlist()
                    candidate_count = self._wordlist_line_count(path)

                    command = ["aircrack-ng", "-w", path, "-e", ssid, pcap_file]
                    self._journal_write("wordlist_started", pcap_file, ssid, stats_key, attempt, label)
                    self._record_event("wordlist", "Starting %s" % label, "info", ssid)

                    wordlist_start = time.time()
                    try:
                        process = subprocess.Popen(
                            command,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            bufsize=1,
                            universal_newlines=True,
                        )

                        with self.lock:
                            self.current_task = process
                            self.wordlist_attempts += 1

                        for line in iter(process.stdout.readline, ""):
                            if not line:
                                break
                            line = line.strip()
                            self._log_ssid(ssid, f"[aircrack-ng] {line}")

                            if self.skip_current_requested:
                                skipped_by_control = True
                                try:
                                    process.terminate()
                                except Exception:
                                    pass
                                break

                            # ---- detect bad/empty capture or interactive prompt ----
                            if (
                                "No matching network found" in line
                                or "0 potential targets" in line
                                or "Index number of target network" in line
                            ):
                                bad_capture = True
                                self._log_ssid(
                                    ssid,
                                    "[bruteforce] Capture has no valid target or requires interactive selection; skipping this file.",
                                    "error",
                                )
                                try:
                                    process.terminate()
                                except Exception:
                                    pass
                                break

                            if (
                                "Invalid packet capture length 0" in line
                                or "corrupted file?" in line
                            ):
                                bad_capture = True
                                self._log_ssid(
                                    ssid,
                                    "[bruteforce] Capture appears corrupted (invalid packet length); skipping this file.",
                                    "error",
                                )
                                try:
                                    process.terminate()
                                except Exception:
                                    pass
                                break

                            # ---- normal parsing continues ----
                            # Aircrack normally emits "keys tested (NN.NN k/s)", not
                            # the old plugin's literal "words per second" phrase.
                            self._parse_aircrack_telemetry(line, ssid, wl_name)

                            if "KEY FOUND!" in line:
                                handshake_cracked = True
                                self.result = "Cracked"

                                key_match = re.search(
                                    r"KEY FOUND!\s*\[\s*(.+?)\s*\]", line
                                )
                                cracked_key = (
                                    key_match.group(1).strip() if key_match else None
                                )
                                cracked_wordlist_key = stats_key

                                if cracked_key:
                                    try:
                                        with open(cracked_keys_file, "a") as f:
                                            f.write(
                                                f"SSID: {ssid}, Key: {cracked_key}\n"
                                            )
                                        self._log_ssid(
                                            ssid,
                                            f"[bruteforce] Cracked key: {cracked_key}",
                                        )
                                    except Exception as e:
                                        self._log_ssid(
                                            ssid,
                                            f"[bruteforce] Unable to save key: {e}",
                                            "error",
                                        )
                                break

                        try:
                            # Shorter wait if we already know the capture is bad
                            timeout = 5 if bad_capture else 600
                            stdout, stderr = process.communicate(timeout=timeout)
                        except subprocess.TimeoutExpired:
                            timed_out = True
                            process.kill()
                            stdout, stderr = process.communicate()
                            self._log_ssid(
                                ssid, "[bruteforce] aircrack-ng timed out.", "error"
                            )

                        if stderr:
                            self._log_ssid(
                                ssid,
                                f"[bruteforce] aircrack-ng error:\n{stderr}",
                                "error",
                            )
                            # Also scan stderr for bad-capture hints if we haven't yet
                            if not bad_capture and (
                                "Invalid packet capture length 0" in stderr
                                or "corrupted file?" in stderr
                                or "0 potential targets" in stderr
                                or "No matching network found" in stderr
                                or "Index number of target network" in stderr
                            ):
                                bad_capture = True
                                self._log_ssid(
                                    ssid,
                                    "[bruteforce] Detected bad/empty capture from stderr; marking as failed.",
                                    "error",
                                )

                    except Exception as ex:
                        self._log_ssid(
                            ssid,
                            f"[bruteforce] Unexpected error with {label}: {ex}",
                            "error",
                        )
                    finally:
                        wl_elapsed = time.time() - wordlist_start
                        if mode == "mutator":
                            stats = self.ssid_stats.setdefault(ssid, {})
                            m = stats.setdefault(
                                "mutator",
                                {
                                    "runs": 0,
                                    "total_words": 0,
                                    "time_seconds": 0.0,
                                    "cracks": 0,
                                },
                            )
                            m["time_seconds"] = m.get("time_seconds", 0.0) + float(
                                wl_elapsed
                            )
                        if self.skip_current_requested:
                            skipped_by_control = True
                        if bad_capture:
                            wl_result = "bad"
                        elif handshake_cracked:
                            wl_result = "cracked"
                        elif timed_out:
                            wl_result = "timeout"
                        elif skipped_by_control:
                            wl_result = "skipped"
                        else:
                            wl_result = "failed"
                        measured_wps = self._finalize_wordlist_wps(
                            wl_elapsed, candidate_count
                        )
                        self._record_wordlist_run(
                            stats_key, wl_elapsed, candidate_count,
                            self.current_wordlist_progress, wl_result,
                            tested_keys=self.current_wordlist_keys_tested,
                            measured_wps=measured_wps,
                        )
                        with self.lock:
                            self.current_task = None

                    if skipped_by_control or handshake_cracked or timed_out or bad_capture:
                        break

                if skipped_by_control:
                    finished_at = time.time()
                    if self.mark_bad_current_requested:
                        self._mark_capture_bad(pcap_file, ssid, "Marked bad from dashboard")
                        self._record_job_history(pcap_file, ssid, "Marked Bad", overall_start, finished_at, attempt, finished_at - overall_start)
                    elif self.defer_current_requested:
                        self._defer_capture(pcap_file, self.defer_seconds, "Deferred from dashboard")
                        self._record_job_history(pcap_file, ssid, "Deferred", overall_start, finished_at, attempt, finished_at - overall_start)
                    elif self.requeue_current_requested:
                        self._requeue_capture(pcap_file)
                        self._record_job_history(pcap_file, ssid, "Requeued", overall_start, finished_at, attempt, finished_at - overall_start)
                    else:
                        self._defer_capture(pcap_file, self.skip_cooldown_seconds, "Skipped from dashboard")
                        self._record_job_history(pcap_file, ssid, "Skipped", overall_start, finished_at, attempt, finished_at - overall_start)
                    self.status = "IDLE"
                    self.progress = "0%"
                    self.result = ""
                    self.save_progress()
                    return

                elapsed_time = time.time() - start_time
                self._append_limited(self.elapsed_time_data, elapsed_time)

                if handshake_cracked:
                    total_elapsed = time.time() - overall_start
                    words_delta = self.words_processed - words_before
                    self._update_stats_for_handshake(
                        ssid,
                        "Cracked",
                        cracked_key,
                        cracked_wordlist_key,
                        total_elapsed,
                        words_delta,
                    )
                    finished_at = time.time()
                    self._record_job_history(
                        pcap_file,
                        ssid,
                        "Cracked",
                        overall_start,
                        finished_at,
                        attempt,
                        total_elapsed,
                    )
                    with self.lock:
                        self.cracked_count += 1
                        self._finalize_handshake(pcap_file, ssid, "Cracked")
                    time.sleep(5)
                    return

                # Only retry on pure timeouts, not on bad captures
                if timed_out and not bad_capture and attempt < self.retry_limit:
                    self._log_ssid(
                        ssid,
                        f"[bruteforce] Retrying (attempt {attempt + 1}/{self.retry_limit})",
                    )
                    self.update_step_status(f"BF: Retry {ssid}")
                    time.sleep(5)
                    continue

                total_elapsed = time.time() - overall_start
                words_delta = self.words_processed - words_before
                result_str = "Timeout" if (timed_out and not bad_capture) else "Failed"
                if not timed_out or bad_capture:
                    with self.lock:
                        self.failed_count += 1
                self.result = result_str
                if bad_capture:
                    self._record_capture_health(pcap_file, ssid, "bad", "aircrack-ng reported invalid or unusable capture")
                self._update_stats_for_handshake(
                    ssid,
                    result_str,
                    cracked_key,
                    cracked_wordlist_key,
                    total_elapsed,
                    words_delta,
                )
                finished_at = time.time()
                self._record_job_history(
                    pcap_file,
                    ssid,
                    result_str,
                    overall_start,
                    finished_at,
                    attempt,
                    total_elapsed,
                )

                with self.lock:
                    self._finalize_handshake(pcap_file, ssid, self.result)
                time.sleep(5)
                return
        finally:
            self.cleanup_mutator_files(ssid)
            self.current_job_start = None
            self.current_job_attempt = 0
            self.current_wordlist_key = ""
            self.current_wordlist_progress = 0.0
            self.current_pcap = None
            self.current_ssid = None
            self.skip_current_requested = False
            self.defer_current_requested = False
            self.requeue_current_requested = False
            self.mark_bad_current_requested = False

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    def update_step_status(self, message: str):
        self.status_message = message
        if self.ui:
            with self.ui._lock:
                self.ui.set("bruteforce_step", message)
        self.on_ui_update(self.ui)

    def update_status(self, status: str, progress: str, result: str):
        self.status = status
        self.progress = progress
        self.result = result

    def update_total_files(self):
        self.total_files = sum(
            len([f for f in files if f.endswith(".pcap")])
            for _, _, files in os.walk(self.handshake_dir)
        )
        self._log_console(f"[bruteforce] Total handshake files: {self.total_files}")

    def abbreviate_number(self, number: int) -> str:
        if number >= 1_000_000_000:
            return f"{number / 1_000_000_000:.2f}B"
        elif number >= 1_000_000:
            return f"{number / 1_000_000:.2f}M"
        elif number >= 1_000:
            return f"{number / 1_000:.2f}K"
        return str(number)

    def mask_key(self, key: Optional[str]) -> str:
        if not key:
            return ""
        length = len(key)
        if length <= 4:
            return "*" * length
        return key[:2] + "*" * (length - 4) + key[-2:]

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def save_progress(self):
        data = {
            "processed_files": self.processed_files,
            "cracked_count": self.cracked_count,
            "failed_count": self.failed_count,
            "processed_files_list": list(self.processed_files_set),
            "words_processed": self.words_processed,
            "wordlist_attempts": self.wordlist_attempts,
            "ssid_stats": self.ssid_stats,
            "wordlist_stats": self.wordlist_stats,
            "last_cracked_ssid": self.last_cracked_ssid,
            "last_cracked_key": self.last_cracked_key,
            "env_favorites": self.env_favorites,
            "job_history": self.job_history,
            "capture_health": self.capture_health,
            "deferred_files": self.deferred_files,
            "wordlist_line_counts": self.wordlist_line_counts,
            "event_timeline": self.event_timeline,
            "resource_history": self.resource_history,
            "capture_fingerprints": self.capture_fingerprints,
            "duplicate_groups": self.duplicate_groups,
            "recovery_note": self.recovery_note,
            "last_completed_wps": self.last_completed_wps,
            "last_completed_keys_tested": self.last_completed_keys_tested,
            "last_completed_duration": self.last_completed_duration,
            "mutator_last_generation": self.mutator_last_generation,
            "mutator_generation_history": self.mutator_generation_history,
            "mutator_feature_totals": self.mutator_feature_totals,
        }
        try:
            os.makedirs(os.path.dirname(self.progress_file), exist_ok=True)
            with open(self.progress_file, "w") as f:
                json.dump(data, f)
            self._log_console("[bruteforce] Progress saved.")
        except Exception as e:
            self._log_console(
                f"[bruteforce] Failed to save progress: {e}", "error"
            )

    def load_progress(self):
        if os.path.exists(self.progress_file):
            try:
                with open(self.progress_file, "r") as f:
                    data = json.load(f)
                self.processed_files = data.get("processed_files", 0)
                self.cracked_count = data.get("cracked_count", 0)
                self.failed_count = data.get("failed_count", 0)
                self.words_processed = data.get("words_processed", 0)
                self.wordlist_attempts = data.get("wordlist_attempts", 0)
                self.words_processed_abbr = self.abbreviate_number(
                    self.words_processed
                )
                files_list = data.get("processed_files_list", [])
                self.processed_files_set = set(files_list)
                self.ssid_stats = data.get("ssid_stats", {})
                self.wordlist_stats = data.get("wordlist_stats", {})
                self.last_cracked_ssid = data.get("last_cracked_ssid", "")
                self.last_cracked_key = data.get("last_cracked_key", "")
                self.env_favorites = data.get("env_favorites", {})
                self.job_history = data.get("job_history", [])
                self.capture_health = data.get("capture_health", {}) or {}
                self.deferred_files = data.get("deferred_files", {}) or {}
                self.wordlist_line_counts = data.get("wordlist_line_counts", {}) or {}
                self.event_timeline = data.get("event_timeline", []) or []
                self.resource_history = data.get("resource_history", []) or []
                self.capture_fingerprints = data.get("capture_fingerprints", {}) or {}
                self.duplicate_groups = data.get("duplicate_groups", {}) or {}
                self.recovery_note = data.get("recovery_note", "") or ""
                self.last_completed_wps = float(data.get("last_completed_wps", 0.0) or 0.0)
                self.last_completed_keys_tested = int(data.get("last_completed_keys_tested", 0) or 0)
                self.last_completed_duration = float(data.get("last_completed_duration", 0.0) or 0.0)
                self.mutator_last_generation = data.get("mutator_last_generation", {}) or {}
                self.mutator_generation_history = data.get("mutator_generation_history", []) or []
                self.mutator_feature_totals = data.get("mutator_feature_totals", {}) or {}
                self._log_console("[bruteforce] Progress loaded.")
            except Exception as e:
                self._log_console(
                    f"[bruteforce] Failed to load progress: {e}", "error"
                )
        else:
            self._log_console("[bruteforce] No saved progress found.")

    def reset_progress(self):
        try:
            if os.path.exists(self.progress_file):
                os.remove(self.progress_file)
                self._log_console("[bruteforce] Progress file deleted.")

            self.processed_files = 0
            self.cracked_count = 0
            self.failed_count = 0
            self.words_processed = 0
            self.words_processed_abbr = ""
            self.wordlist_attempts = 0
            self.processed_files_set.clear()
            self.ssid_stats = {}
            self.wordlist_stats = {}
            self.wps_data = []
            self.progress_data = []
            self.elapsed_time_data = []
            self._reset_wps_for_wordlist()
            self.current_wordlist_started_monotonic = None
            self.last_completed_wps = 0.0
            self.last_completed_keys_tested = 0
            self.last_completed_duration = 0.0
            self.last_cracked_ssid = ""
            self.last_cracked_key = ""
            self.status = "IDLE"
            self.progress = "0%"
            self.result = ""
            self.status_message = ""
            self.current_pcap = None
            self.current_ssid = None
            self.mutator_paths = {}
            self.env_favorites = {}
            self.job_history = []
            self.current_job_start = None
            self.current_job_attempt = 0
            self.mutator_error_ssids = set()
            self.capture_health = {}
            self.deferred_files = {}
            self.manual_priority_files = set()
            self.wordlist_line_counts = {}
            self.event_timeline = []
            self.resource_history = []
            self.capture_fingerprints = {}
            self.duplicate_groups = {}
            self.recovery_note = ""
            self.mutator_last_generation = {}
            self.mutator_generation_history = []
            self.mutator_feature_totals = {}
            self._journal_clear("reset")
            self.manual_paused = False
            self.pause_detail = ""

            try:
                if os.path.exists(self.env_favorites_path):
                    os.remove(self.env_favorites_path)
            except Exception:
                pass

            self._log_console("[bruteforce] Progress reset.")
            self.on_ui_update(self.ui)
        except Exception as e:
            self._log_console(
                f"[bruteforce] Failed to reset progress: {e}", "error"
            )
