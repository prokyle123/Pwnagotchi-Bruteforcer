import os
import json
import time
import logging
import threading
import subprocess
import re
import base64
import codecs
from typing import Set, Optional

from flask import Flask, render_template_string, jsonify, redirect, url_for

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
  <title>BruteForcer Plugin Dashboard</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    body {
      background: #0b1020;
      color: #e4e7ef;
    }
    .card {
      margin: 10px;
      background: #151a2c;
      border: 1px solid #232a40;
      color: #e4e7ef;
    }
    .card-header {
      background: #1f2538;
      border-bottom: 1px solid #232a40;
      font-weight: 600;
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }
    .stat-value {
      font-size: 1.4rem;
      font-weight: 700;
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
    .badge {
      font-size: 0.7rem;
    }
    a {
      text-decoration: none;
    }
  </style>
</head>
<body class="container-fluid py-3">
  <div class="d-flex justify-content-between align-items-center mb-3">
    <div>
      <h2 class="mb-0">BruteForcer Dashboard</h2>
      <div class="sub-label">Real-time WPA handshake cracking monitor</div>
    </div>
    <div>
      <a href="/networks" class="btn btn-outline-info btn-sm me-2">SSID &amp; Wordlist Stats</a>
      <form method="POST" action="/reset" style="display:inline;"
            onsubmit="return confirm('Reset all BruteForcer stats and progress?');">
        <button type="submit" class="btn btn-outline-danger btn-sm">Reset Stats</button>
      </form>
    </div>
  </div>

  <!-- Row of cards showing summary stats -->
  <div class="row g-2 mb-2">
    <div class="col-md-2 col-6">
      <div class="card text-center">
        <div class="card-header">Status</div>
        <div class="card-body py-3">
          <div class="stat-value" id="statusText">{{ status }}</div>
          <div class="sub-label">Engine</div>
        </div>
      </div>
    </div>
    <div class="col-md-2 col-6">
      <div class="card text-center">
        <div class="card-header">Progress</div>
        <div class="card-body py-3">
          <div class="stat-value" id="progressText">{{ progress }}</div>
          <div class="sub-label">Current Run</div>
        </div>
      </div>
    </div>
    <div class="col-md-2 col-6">
      <div class="card text-center">
        <div class="card-header">Handshakes</div>
        <div class="card-body py-3">
          <div class="stat-value" id="processedText">{{ processed_files }}</div>
          <div class="sub-label">Processed / Total</div>
        </div>
      </div>
    </div>
    <div class="col-md-3 col-6">
      <div class="card text-center">
        <div class="card-header">Words Processed</div>
        <div class="card-body py-3">
          <div class="stat-value" id="wordsText">{{ words_processed }}</div>
          <div class="sub-label">Approx Total Tried</div>
        </div>
      </div>
    </div>
    <div class="col-md-3 col-12">
      <div class="card text-center">
        <div class="card-header">Results</div>
        <div class="card-body py-3 d-flex justify-content-around">
          <div>
            <div class="sub-label">Cracked</div>
            <div class="stat-value text-success" id="crackedText">{{ cracked_count }}</div>
          </div>
          <div>
            <div class="sub-label">Failed / Timeout</div>
            <div class="stat-value text-danger" id="failedText">{{ failed_count }}</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- Row for last cracked + health + leaderboard -->
  <div class="row g-2 mb-3">
    <div class="col-lg-4 col-md-6">
      <div class="card h-100">
        <div class="card-header">Last Cracked</div>
        <div class="card-body py-3">
          <div class="sub-label">SSID</div>
          <div class="stat-value" id="lastCrackedSsid">{{ last_cracked_ssid }}</div>
          <div class="sub-label mt-2">Key (masked)</div>
          <div id="lastCrackedKey">{{ last_cracked_key }}</div>
        </div>
      </div>
    </div>
    <div class="col-lg-4 col-md-6">
      <div class="card h-100">
        <div class="card-header">Cracking Health</div>
        <div class="card-body py-3">
          <div class="sub-label mb-1">Crack Rate</div>
          <div class="stat-value" id="healthRate">0.0%</div>
          <div class="sub-label mb-1 mt-2">Avg WPS (recent)</div>
          <div id="healthAvgWps">0</div>
          <div class="sub-label mb-1 mt-2">Avg Time / Handshake</div>
          <div id="healthAvgTime">0.0 s</div>
          <div class="mt-2">
            <span id="healthBadge" class="badge bg-secondary">Idle</span>
          </div>

          <hr class="my-2">

          <div class="sub-label mb-1">Mutator</div>
          <div class="small" id="mutatorSummaryLine">-</div>
          <div class="small" id="mutatorDetailLine">Runs: 0 Ã‚Â· Cracks: 0 Ã‚Â· Words: 0</div>
          <div class="small text-muted" id="mutatorEnvLine">Env favorites: 0 Ã‚Â· Mutator share: 0.0% of cracks</div>
        </div>
      </div>
    </div>
    <div class="col-lg-4 col-md-12">
      <div class="card h-100">
        <div class="card-header">Leaderboard &amp; Achievements</div>
        <div class="card-body py-3">
          <div class="sub-label mb-1">Fastest Crack</div>
          <div><span id="leaderFastSsid">-</span></div>
          <div class="small text-muted" id="leaderFastTime">-</div>
          <div class="small text-muted" id="leaderFastWordlist">-</div>

          <hr class="my-2">

          <div class="sub-label mb-1">Most Effective Wordlist</div>
          <div id="leaderBestWordlist">-</div>
          <div class="small text-muted" id="leaderBestRate">-</div>
          <div class="small text-muted" id="leaderBestCounts">-</div>

          <hr class="my-2">

          <div class="sub-label mb-1">Most Stubborn SSID</div>
          <div id="leaderStubbornSsid">-</div>
          <div class="small text-muted" id="leaderStubbornAttempts">-</div>
          <div class="small text-muted" id="leaderStubbornStatus">-</div>

          <hr class="my-2">

          <div class="sub-label mb-1">Achievements</div>
          <div id="achievementsList" class="small"></div>
        </div>
      </div>
    </div>
  </div>

  <!-- Charts + Queue + Logs -->
  <div class="row g-2 mt-1">
    <div class="col-lg-8">
      <div class="card mb-2">
        <div class="card-header">Performance Charts</div>
        <div class="card-body">
          <div class="mb-3">
            <div class="sub-label mb-1">Words / second</div>
            <canvas id="wpsChart" height="70"></canvas>
          </div>
          <div class="mb-3">
            <div class="sub-label mb-1">Progress %</div>
            <canvas id="progressChart" height="70"></canvas>
          </div>
          <div class="mb-3">
            <div class="sub-label mb-1">Handshake time (seconds)</div>
            <canvas id="elapsedChart" height="70"></canvas>
          </div>
          <div>
            <div class="sub-label mb-1">Attempts Timeline</div>
            <canvas id="timelineChart" height="60"></canvas>
          </div>
          <!-- Overall result mix bar -->
          <div class="mt-3">
            <div class="sub-label mb-1">Result mix</div>
            <div class="progress" style="height:8px;">
              <div id="barCracked" class="progress-bar bg-success" role="progressbar" style="width:0%"></div>
              <div id="barFailed" class="progress-bar bg-danger" role="progressbar" style="width:0%"></div>
              <div id="barTimeout" class="progress-bar bg-warning text-dark" role="progressbar" style="width:0%"></div>
              <div id="barPending" class="progress-bar bg-secondary" role="progressbar" style="width:0%"></div>
            </div>
            <div class="small mt-1 text-muted">
              <span id="barCrackedLabel">0 cracked</span> &middot;
              <span id="barFailedLabel">0 failed</span> &middot;
              <span id="barTimeoutLabel">0 timeout</span> &middot;
              <span id="barPendingLabel">0 pending</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    <div class="col-lg-4">
      <div class="card mb-2">
        <div class="card-header">Jobs Timeline</div>
        <div class="card-body">
          <div id="jobsTimeline" class="small"></div>
        </div>
      </div>
      <div class="card mb-2">
        <div class="card-header">Queue</div>
        <div class="card-body">
          <div class="sub-label">Current</div>
          <div id="queueCurrent" class="mb-2 text-light small">Idle</div>
          <div class="sub-label">Next up</div>
          <ul id="queueNext" class="list-unstyled mb-0 small"></ul>
        </div>
      </div>
      <div class="card h-100">
        <div class="card-header d-flex justify-content-between align-items-center">
          <span>BruteForcer Logs</span>
          <span class="sub-label">Newest at bottom</span>
        </div>
        <div class="card-body">
          <div class="log-console" id="logConsole">
            {% for line in logs %}
              {{ line }}<br>
            {% endfor %}
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    let wpsChart, progressChart, elapsedChart, timelineChart;

    function initCharts() {
      const wpsCtx = document.getElementById('wpsChart').getContext('2d');
      const progCtx = document.getElementById('progressChart').getContext('2d');
      const elapsedCtx = document.getElementById('elapsedChart').getContext('2d');
      const timelineCtx = document.getElementById('timelineChart').getContext('2d');

      wpsChart = new Chart(wpsCtx, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Words / second', data: [], tension: 0.3 }] },
        options: {
          responsive: true,
          animation: false,
          plugins: { legend: { display: false }},
          scales: { x: { display: false }, y: { beginAtZero: true } }
        }
      });

      progressChart = new Chart(progCtx, {
        type: 'line',
        data: { labels: [], datasets: [{ label: 'Progress %', data: [], tension: 0.3 }] },
        options: {
          responsive: true,
          animation: false,
          plugins: { legend: { display: false }},
          scales: { x: { display: false }, y: { beginAtZero: true, max: 100 } }
        }
      });

      elapsedChart = new Chart(elapsedCtx, {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Handshake time (s)', data: [] }] },
        options: {
          responsive: true,
          animation: false,
          plugins: { legend: { display: false }},
          scales: { x: { display: false }, y: { beginAtZero: true } }
        }
      });

      timelineChart = new Chart(timelineCtx, {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Attempts', data: [], backgroundColor: [] }] },
        options: {
          responsive: true,
          animation: false,
          plugins: { legend: { display: false }},
          scales: {
            x: { display: false },
            y: {
              beginAtZero: true,
              suggestedMax: 3,
              ticks: {
                callback: function(value) {
                  if (value === 3) return 'Cracked';
                  if (value === 2) return 'Timeout';
                  if (value === 1) return 'Failed';
                  return '';
                }
              }
            }
          }
        }
      });
    }

    async function refreshMetrics() {
      try {
        const resp = await fetch('/api/metrics');
        if (!resp.ok) return;
        const data = await resp.json();

        document.getElementById('statusText').innerText = data.status;
        document.getElementById('progressText').innerText = data.progress;
        document.getElementById('processedText').innerText = data.processed_display;
        document.getElementById('wordsText').innerText = data.words_processed;
        document.getElementById('crackedText').innerText = data.cracked_count;
        document.getElementById('failedText').innerText = data.failed_count;

        // Overall result mix bar
        const statusCounts = data.status_counts || {};
        const crackedCount = statusCounts.cracked || 0;
        const failedCount = statusCounts.failed || 0;
        const timeoutCount = statusCounts.timeout || 0;
        const pendingCount = statusCounts.pending || 0;

        const pctCracked = data.pct_cracked || 0;
        const pctFailed = data.pct_failed || 0;
        const pctTimeout = data.pct_timeout || 0;
        const pctPending = data.pct_pending || 0;

        const barCracked = document.getElementById('barCracked');
        const barFailed = document.getElementById('barFailed');
        const barTimeout = document.getElementById('barTimeout');
        const barPending = document.getElementById('barPending');

        if (barCracked && barFailed && barTimeout && barPending) {
          barCracked.style.width = pctCracked.toFixed(1) + '%';
          barFailed.style.width = pctFailed.toFixed(1) + '%';
          barTimeout.style.width = pctTimeout.toFixed(1) + '%';
          barPending.style.width = pctPending.toFixed(1) + '%';
        }

        const barCrackedLabel = document.getElementById('barCrackedLabel');
        const barFailedLabel = document.getElementById('barFailedLabel');
        const barTimeoutLabel = document.getElementById('barTimeoutLabel');
        const barPendingLabel = document.getElementById('barPendingLabel');

        if (barCrackedLabel) barCrackedLabel.innerText = crackedCount + ' cracked';
        if (barFailedLabel) barFailedLabel.innerText = failedCount + ' failed';
        if (barTimeoutLabel) barTimeoutLabel.innerText = timeoutCount + ' timeout';
        if (barPendingLabel) barPendingLabel.innerText = pendingCount + ' pending';

        document.getElementById('lastCrackedSsid').innerText = data.last_cracked_ssid || '-';
        document.getElementById('lastCrackedKey').innerText = data.last_cracked_key_masked || '';

        const crackRate = data.crack_rate || 0.0;
        const avgWps = data.avg_wps || 0.0;
        const avgElapsed = data.avg_elapsed || 0.0;
        const processedCount = data.processed_count || 0;

        const healthRateEl = document.getElementById('healthRate');
        const healthAvgWpsEl = document.getElementById('healthAvgWps');
        const healthAvgTimeEl = document.getElementById('healthAvgTime');
        const healthBadge = document.getElementById('healthBadge');

        healthRateEl.innerText = crackRate.toFixed(1) + '%';
        healthAvgWpsEl.innerText = Math.round(avgWps);
        healthAvgTimeEl.innerText = avgElapsed.toFixed(1) + ' s';

        healthBadge.className = 'badge';
        if (!processedCount) {
          healthBadge.classList.add('bg-secondary');
          healthBadge.textContent = 'Idle';
        } else if (crackRate >= 50.0) {
          healthBadge.classList.add('bg-success');
          healthBadge.textContent = 'Strong';
        } else if (crackRate >= 10.0) {
          healthBadge.classList.add('bg-warning', 'text-dark');
          healthBadge.textContent = 'Moderate';
        } else {
          healthBadge.classList.add('bg-danger');
          healthBadge.textContent = 'Weak';
        }

        const currentSsid = data.current_ssid || '';
        const currentPcap = data.current_pcap || '';
        const queue = data.queue || [];

        const queueCurrent = document.getElementById('queueCurrent');
        const queueNext = document.getElementById('queueNext');

        if (currentSsid || currentPcap) {
          queueCurrent.innerText = (currentSsid || '?') + ' (' + currentPcap + ')';
        } else {
          queueCurrent.innerText = 'Idle';
        }

        queueNext.innerHTML = '';
        queue.forEach(item => {
          const li = document.createElement('li');
          li.textContent = item.ssid + ' (' + item.file + ')';
          queueNext.appendChild(li);
        });

        // Jobs timeline (past, current, next up)
        const timelineContainer = document.getElementById('jobsTimeline');
        if (timelineContainer) {
          const currentJob = data.current_job || null;
          const jobHistory = data.job_history || [];
          let html = '';

          // Current job
          html += '<div class="mb-2">';
          html += '<div class="sub-label mb-0">Current</div>';
          if (currentJob && (currentJob.ssid || currentJob.pcap)) {
            const elapsed = currentJob.elapsed ? Math.round(currentJob.elapsed) : 0;
            const attempt = currentJob.attempt || 0;
            const retryLimit = currentJob.retry_limit || 0;
            html += '<div class="d-flex align-items-center mt-1">';
            html += '<span class="badge bg-info me-2">NOW</span>';
            html += '<div>';
            html += '<div><strong>' + (currentJob.ssid || '?') + '</strong>';
            if (currentJob.pcap) {
              html += ' (' + currentJob.pcap + ')';
            }
            html += '</div>';
            html += '<div class="text-muted small">';
            if (attempt && retryLimit) {
              html += 'Attempt ' + attempt + '/' + retryLimit + ' Ã‚Â· ';
            }
            html += (currentJob.status || 'Running');
            if (elapsed) {
              html += ' Ã‚Â· ' + elapsed + 's elapsed';
            }
            html += '</div>';
            html += '</div></div>';
          } else {
            html += '<div class="text-muted small mt-1">Idle</div>';
          }
          html += '</div>';

          // Recent jobs
          html += '<div class="sub-label mb-1">Recent Jobs</div>';
          if (!jobHistory.length) {
            html += '<div class="text-muted small mb-2">No jobs yet.</div>';
          } else {
            const recent = jobHistory.slice(-5).reverse();
            recent.forEach(j => {
              const res = (j.result || '').toLowerCase();
              let badgeClass = 'badge bg-secondary';
              if (res === 'cracked') badgeClass = 'badge bg-success';
              else if (res === 'failed') badgeClass = 'badge bg-danger';
              else if (res === 'timeout') badgeClass = 'badge bg-warning text-dark';
              const dur = j.duration ? Math.round(j.duration) : 0;
              const attempts = j.attempts || 0;
              html += '<div class="d-flex align-items-center mb-1">';
              html += '<span class="' + badgeClass + ' me-2 text-uppercase small">' +
                      (j.result || '-') + '</span>';
              html += '<div>';
              html += '<div><strong>' + (j.ssid || '?') + '</strong>';
              if (j.pcap) {
                html += ' (' + j.pcap + ')';
              }
              html += '</div>';
              html += '<div class="text-muted small">';
              if (dur) {
                html += dur + 's';
              }
              if (attempts) {
                html += (dur ? ' Ã‚Â· ' : '') + 'attempts ' + attempts;
              }
              html += '</div>';
              html += '</div></div>';
            });
          }

          // Next up preview
          html += '<div class="sub-label mb-1 mt-2">Next Up</div>';
          if (!queue.length) {
            html += '<div class="text-muted small">Queue empty.</div>';
          } else {
            const preview = queue.slice(0, 3);
            preview.forEach(item => {
              html += '<div class="d-flex align-items-center mb-1">';
              html += '<span class="badge bg-dark me-2">&rarr;</span>';
              html += '<div>';
              html += '<div><strong>' + (item.ssid || '?') + '</strong>';
              if (item.file) {
                html += ' (' + item.file + ')';
              }
              html += '</div>';
              html += '</div></div>';
            });
          }

          timelineContainer.innerHTML = html;
        }

        const wps = data.wps_data || [];
        const prog = data.progress_data || [];
        const elapsed = data.elapsed_time_data || [];
        const tVals = data.timeline_values || [];
        const tLabels = data.timeline_labels || [];

        wpsChart.data.labels = wps.map((_, i) => i + 1);
        wpsChart.data.datasets[0].data = wps;
        wpsChart.update('none');

        progressChart.data.labels = prog.map((_, i) => i + 1);
        progressChart.data.datasets[0].data = prog;
        progressChart.update('none');

        elapsedChart.data.labels = elapsed.map((_, i) => i + 1);
        elapsedChart.data.datasets[0].data = elapsed;
        elapsedChart.update('none');

        timelineChart.data.labels = tLabels;
        timelineChart.data.datasets[0].data = tVals.map(v => v || 0);
        timelineChart.data.datasets[0].backgroundColor = tVals.map(v => {
          if (v === 3) return 'rgba(76, 175, 80, 0.9)';      // Cracked
          if (v === 2) return 'rgba(255, 193, 7, 0.9)';      // Timeout
          if (v === 1) return 'rgba(244, 67, 54, 0.9)';      // Failed
          return 'rgba(158, 158, 158, 0.9)';                 // Other
        });
        timelineChart.update('none');

        const fastSsidEl = document.getElementById('leaderFastSsid');
        const fastTimeEl = document.getElementById('leaderFastTime');
        const fastWlEl = document.getElementById('leaderFastWordlist');
        const bestWlEl = document.getElementById('leaderBestWordlist');
        const bestRateEl = document.getElementById('leaderBestRate');
        const bestCountsEl = document.getElementById('leaderBestCounts');
        const stubSsidEl = document.getElementById('leaderStubbornSsid');
        const stubAttemptsEl = document.getElementById('leaderStubbornAttempts');
        const stubStatusEl = document.getElementById('leaderStubbornStatus');

        fastSsidEl.innerText = data.leader_fast_ssid || '-';
        const d = data.leader_fast_duration;
        fastTimeEl.innerText = (typeof d === 'number') ? d.toFixed(1) + ' s' : '-';
        fastWlEl.innerText = data.leader_fast_wordlist || '-';

        bestWlEl.innerText = data.leader_best_wordlist_label || '-';
        const r = data.leader_best_wordlist_rate;
        bestRateEl.innerText = (typeof r === 'number') ? r.toFixed(1) + '% success' : '-';
        const br = data.leader_best_wordlist_runs || 0;
        const bc = data.leader_best_wordlist_cracks || 0;
        bestCountsEl.innerText = br ? (bc + ' / ' + br + ' cracks') : '-';

        stubSsidEl.innerText = data.leader_stubborn_ssid || '-';
        const a = data.leader_stubborn_attempts || 0;
        stubAttemptsEl.innerText = a ? (a + ' attempt(s)') : '-';
        stubStatusEl.innerText = data.leader_stubborn_status || '-';

        const achListEl = document.getElementById('achievementsList');
        achListEl.innerHTML = '';
        const achievements = data.achievements || [];
        if (!achievements.length) {
          achListEl.innerText = 'No achievements yet.';
        } else {
          achievements.forEach(ac => {
            const row = document.createElement('div');
            row.className = 'mb-1';
            const icon = ac.icon || 'Ã¢Å“Â¦';
            if (ac.unlocked) {
              row.innerHTML = '<span class="badge bg-success me-1">' + icon + '</span>' +
                              '<strong>' + ac.name + '</strong> - ' + ac.desc;
            } else {
              row.innerHTML = '<span class="badge bg-secondary me-1">' + icon + '</span>' +
                              '<span class="text-muted">' + ac.name + '</span>';
            }
            achListEl.appendChild(row);
          });
        }

        // Mutator summary panel
        const mutSummaryLine = document.getElementById('mutatorSummaryLine');
        const mutDetailLine = document.getElementById('mutatorDetailLine');
        const mutEnvLine = document.getElementById('mutatorEnvLine');

        if (mutSummaryLine && mutDetailLine && mutEnvLine) {
          const mutEnabled = data.mutator_enabled;
          const mutProfile = data.mutator_profile || 'balanced';
          const mutRuns = data.mutator_runs || 0;
          const mutCracks = data.mutator_cracks || 0;
          const mutWords = data.mutator_words_abbr || (data.mutator_words || 0);
          const mutShare = data.mutator_share || 0;
          const mutEnv = data.mutator_env_count || 0;
          const mutMaxWords = data.mutator_max_words || 0;
          const mutFeatures = data.mutator_features || '';

          mutSummaryLine.innerText =
            (mutEnabled ? 'Enabled' : 'Disabled') +
            ' (' + mutProfile + ', max ' + mutMaxWords + ' words/SSID)';

          mutDetailLine.innerText =
            'Runs: ' + mutRuns + ' Ã‚Â· Cracks: ' + mutCracks +
            ' Ã‚Â· Words: ' + mutWords;

          let envLine = 'Env favorites: ' + mutEnv +
                        ' Ã‚Â· Mutator share: ' + mutShare.toFixed(1) + '% of cracks';
          if (mutFeatures) {
            envLine += ' Ã‚Â· Features: ' + mutFeatures;
          }
          mutEnvLine.innerText = envLine;
        }

      } catch (e) {
        console.error('Failed to refresh metrics', e);
      }
    }

    document.addEventListener('DOMContentLoaded', () => {
      initCharts();
      refreshMetrics();
      setInterval(refreshMetrics, 5000);
    });
  </script>
</body>
</html>
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
              </tr>
            {% else %}
              <tr>
                <td colspan="4" class="text-muted">No wordlist stats yet.</td>
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


class BruteForce(plugins.Plugin):
    __author__ = 'SKY'
    __version__ = '2.9.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin to brute force WPA handshakes using aircrack-ng.'

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
        # fast / balanced / heavy Ã¢â‚¬â€œ only affects defaults,
        # explicit per-flag config still wins.
        self.mutator_profile = "balanced"

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
            # Small, cheap wordlist Ã¢â‚¬â€œ good for low-power or quick passes.
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

    def generate_mutation_candidates(self, ssid: str):
        """
        Generate a small SSID-aware wordlist including optional base64 / ROT13 / hex
        variants and smart SSID pattern mutations.

        The size of the list is capped by mutator_max_words (with hard safety bounds).
        """
        words = set()
        if not ssid:
            return words

        try:
            limit = int(self.mutator_max_words or 0)
        except Exception:
            limit = 0
        # Hard safety bounds to keep the Pi responsive even in "heavy" mode.
        if limit <= 0:
            limit = 10
        limit = max(10, min(limit, 20000))

        base = ssid.strip()
        if not base:
            return words

        # Normalize spaces and split into tokens / numeric chunks
        base_clean = re.sub(r"\s+", " ", base)
        tokens = [t for t in re.split(r"[\s\-_]+", base_clean) if t]
        digit_chunks = [d for d in dict.fromkeys(re.findall(r"\d+", base_clean)) if d]

        # Core forms derived from SSID
        forms = [
            base_clean,
            base_clean.lower(),
            base_clean.upper(),
            base_clean.title(),
            base_clean.replace(" ", ""),
            base_clean.replace("-", ""),
            base_clean.replace("_", ""),
        ]

        # Include raw numeric fragments as seeds (they'll be combined later)
        forms.extend(digit_chunks)

        # Custom seed words from config
        if self.mutator_custom_words:
            for w in self.mutator_custom_words:
                if w:
                    forms.append(w)

        # Use SSID splits (first/last word, etc.)
        if self.mutator_ssid_splits and len(tokens) > 1:
            forms.extend(tokens)
            first = tokens[0]
            last = tokens[-1]
            if first and last and first != last:
                forms.append(first + last)
                forms.append(last + first)

        # Include separated/joined variants with common separators
        if self.mutator_include_separators and len(tokens) > 1:
            seps = ["", "-", "_", ".", " "]
            for sep in seps:
                joined = sep.join(tokens)
                forms.append(joined)

        # De-duplicate while preserving relative order
        seen = set()
        unique_forms = []
        for f in forms:
            if f and f not in seen:
                seen.add(f)
                unique_forms.append(f)

        # Expanded forms: reversed and case-swapped variants
        if self.mutator_include_reversed:
            for f in list(unique_forms):
                rf = f[::-1]
                if rf and rf not in seen:
                    seen.add(rf)
                    unique_forms.append(rf)

        if self.mutator_include_case_swaps:
            for f in list(unique_forms):
                sf = f.swapcase()
                if sf and sf not in seen:
                    seen.add(sf)
                    unique_forms.append(sf)

        current_year = time.localtime().tm_year
        suffixes = [
            "",
            "1", "12", "123", "1234",
            "01", "001", "007",
            "!", "!!", "?",
            "123456", "12345678",
        ]
        if self.mutator_include_years:
            suffixes.extend([
                str(current_year),
                str(current_year - 1),
                "2024", "2025",
            ])

        # Reuse any numeric fragments as suffixes as well (e.g. "24")
        suffixes.extend(digit_chunks)

        prefixes = ["", "!", "@", "#"]

        def maybe_add(word: str):
            # WPA key length constraints
            if len(word) < 8 or len(word) > 63:
                return
            if word not in words:
                words.add(word)

            # Encodings / transformations layered on top
            if self.mutator_include_base64:
                try:
                    b64 = base64.b64encode(word.encode("utf-8")).decode("ascii")
                except Exception:
                    b64 = None
                if b64 and 8 <= len(b64) <= 63 and b64 not in words:
                    words.add(b64)

            if self.mutator_include_rot13:
                try:
                    rot = codecs.decode(word, "rot_13")
                except Exception:
                    rot = None
                if rot and 8 <= len(rot) <= 63 and rot not in words:
                    words.add(rot)

            if self.mutator_include_hex:
                try:
                    hexw = word.encode("utf-8").hex()
                except Exception:
                    hexw = None
                if hexw and 8 <= len(hexw) <= 63 and hexw not in words:
                    words.add(hexw)

        # Core patterns: prefix + form + suffix (+ optional leet)
        for form in unique_forms:
            for suf in suffixes:
                for pre in prefixes:
                    w = f"{pre}{form}{suf}"
                    maybe_add(w)
                    if len(words) >= limit:
                        return words

                    if self.mutator_leet_mode != "off":
                        if self.mutator_leet_mode == "light":
                            # In light mode, avoid over-mutating prefixed variants
                            if pre == "":
                                lw = self.leetify(w)
                            else:
                                lw = w
                        else:
                            lw = self.leetify(w)
                        if lw != w:
                            maybe_add(lw)
                            if len(words) >= limit:
                                return words

        # Extra common patterns based on SSID
        extras = [
            "password123",
            f"{base_clean}wifi",
            f"{base_clean}net",
            f"{base_clean}home",
        ]
        for w in extras:
            maybe_add(w)
            if len(words) >= limit:
                break

        # Adaptive patterns using env favorites (things that have cracked before)
        if self.mutator_use_env_favorites and self.env_favorites and len(words) < limit:
            try:
                top_env = sorted(
                    self.env_favorites.items(),
                    key=lambda kv: kv[1],
                    reverse=True,
                )[:10]
            except Exception:
                top_env = []

            # Only mix a few base forms with favorites to avoid explosion
            for form in unique_forms[:3]:
                for fav, _score in top_env:
                    if len(words) >= limit:
                        break
                    maybe_add(f"{form}{fav}")
                    if len(words) >= limit:
                        break
                    maybe_add(f"{fav}{form}")
                if len(words) >= limit:
                    break

        return words

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
                for w in sorted(words):
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
            cracks = stats.get("cracks", 0)
            runs = stats.get("runs", 0)
            return (-cracks, runs, name, mode)

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

        self.save_progress()
        self.update_total_files()
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
            base = os.path.basename(pcap)
            ssid = base.split("_")[0] if "_" in base else "?"
            pri = self._compute_handshake_priority(pcap, ssid)
            scored.append((pri, pcap, ssid))
        scored.sort(key=lambda x: x[0])
        queue = []
        for _pri, pcap, ssid in scored[:max_items]:
            queue.append({"ssid": ssid, "file": os.path.basename(pcap)})
        return queue

    def _compute_handshake_priority(self, pcap_file: str, ssid: str):
        """
        Priority queue logic:
        - New SSIDs (0 attempts) > previously tried.
        - Within each bucket, prefer newest captures first.
        - Among previously tried, fewer attempts have slightly higher priority.
        - SSIDs with repeated Failed/Timeout are slightly penalized.
        """
        stats = self.ssid_stats.get(ssid, {})
        attempts = int(stats.get("attempts", 0) or 0)
        last_result = stats.get("last_result", "") or ""
        try:
            mtime = os.path.getmtime(pcap_file)
        except Exception:
            mtime = 0.0

        # primary: whether we have seen this SSID before (False < True)
        seen_before = attempts > 0

        # secondary: prefer newer captures (invert so newer -> smaller value)
        freshness_rank = -mtime

        # tertiary: lower attempts first
        attempt_rank = attempts

        # small tweak: deprioritize SSIDs that have already had hard failures
        penalty = 0
        if last_result in ("Failed", "Timeout"):
            penalty = 1

        return (seen_before, penalty, attempt_rank, freshness_rank, pcap_file)

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
        for key, wstats in self.wordlist_stats.items():
            runs = int(wstats.get("runs", 0) or 0)
            cracks = int(wstats.get("cracks", 0) or 0)
            if runs <= 0:
                continue
            rate = (cracks * 100.0) / float(runs)
            name = wstats.get("name") or key
            mode = wstats.get("mode", "plain")
            label = f"{name} ({mode})" if mode else name
            if best_rate is None or rate > best_rate:
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
            "Ã°Å¸â€Â°",
            cracked >= 1,
        )
        add_ach(
            "ten_cracks",
            "Serial Cracker",
            "Crack 10 or more networks.",
            "Ã°Å¸Å½Â¯",
            cracked >= 10,
        )
        add_ach(
            "marathoner",
            "Marathoner",
            "Spend over 1M words on a single SSID.",
            "Ã°Å¸Æ’",
            marathon,
        )
        add_ach(
            "speed_demon",
            "Speed Demon",
            "Crack a network in under 10 seconds.",
            "Ã¢Å¡Â¡",
            speed_demon,
        )
        add_ach(
            "stubborn_hunter",
            "Stubborn Hunter",
            "Crack a network after 5+ attempts.",
            "Ã°Å¸Â¦Å ",
            stubborn_hunter,
        )
        add_ach(
            "long_runner",
            "Long Runner",
            "Process at least 10M words or 50 handshakes.",
            "Ã°Å¸â€œÂ¡",
            (total_words >= 10_000_000) or (processed >= 50),
        )
        add_ach(
            "strategist",
            "Strategist",
            "Use a wordlist with >50% success over at least 5 runs.",
            "Ã¢â„¢Å¸",
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
    def on_configure(self, options):
        self.options = options

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

        self._log_console(
            f"[bruteforce] Configured mutator: profile={self.mutator_profile}, "
            f"enabled={self.mutator_enabled}, max_words={self.mutator_max_words}"
        )

    def on_loaded(self):
        self.load_progress()
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

        @self.app.route("/api/metrics")
        def api_metrics():
            processed = self.processed_files
            crack_rate = (
                self.cracked_count / float(processed) * 100.0 if processed else 0.0
            )
            avg_wps = (
                float(sum(self.wps_data) / len(self.wps_data))
                if self.wps_data
                else 0.0
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
                }
            )

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
                ui.set("bruteforce_step", self.status_message)

    # ------------------------------------------------------------------
    # Monitoring for new handshakes
    # ------------------------------------------------------------------
    def start_monitoring(self):
        self._log_console("[bruteforce] Starting handshake monitoring thread.")
        t = threading.Thread(target=self.monitor_handshakes, daemon=True)
        t.start()

    def monitor_handshakes(self):
        while not self.stop_event.is_set():
            new_files = self.get_new_handshakes()
            scored = []
            for pcap_file in new_files:
                base = os.path.basename(pcap_file)
                ssid = base.split("_")[0] if "_" in base else "?"
                pri = self._compute_handshake_priority(pcap_file, ssid)
                scored.append((pri, pcap_file))
            scored.sort(key=lambda x: x[0])
            for _pri, pcap_file in scored:
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
        return all_pcap_files - self.processed_files_set

    # ------------------------------------------------------------------
    # Core cracking logic (with bad-capture + mutator error handling)
    # ------------------------------------------------------------------
    def run_bruteforce(self, pcap_file: str):
        if self.stop_event.is_set():
            return

        base_name = os.path.basename(pcap_file)
        if "_" not in base_name:
            self._log_console(
                f"[bruteforce] Invalid filename format for {pcap_file}", "error"
            )
            return

        ssid = base_name.split("_")[0]
        cracked_keys_file = "/home/pi/cracked_keys.txt"

        self.current_pcap = pcap_file
        self.current_ssid = ssid

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

                    self.update_step_status(f"WL: {label} {ssid}")
                    self.update_status("BRUTE", "0%", "")
                    self._log_ssid(ssid, f"[bruteforce] Running: {label}")

                    command = ["aircrack-ng", "-w", path, "-e", ssid, pcap_file]

                    wordlist_start = time.time()
                    try:
                        process = subprocess.Popen(
                            command,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                        )

                        with self.lock:
                            self.current_task = process
                            self.wordlist_attempts += 1

                        for line in iter(process.stdout.readline, ""):
                            if not line:
                                break
                            line = line.strip()
                            self._log_ssid(ssid, f"[aircrack-ng] {line}")

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
                            prog_match = re.search(r"(\d+\.\d+)%", line)
                            if prog_match:
                                cur_prog = float(prog_match.group(1))
                                self.progress = f"{int(cur_prog)}%"
                                self._append_limited(
                                    self.progress_data, int(cur_prog)
                                )
                                self.on_ui_update(self.ui)

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

                            if "words per second" in line:
                                wps_match = re.search(
                                    r"(\d+)\swords per second", line
                                )
                                if wps_match:
                                    wps_value = int(wps_match.group(1))
                                    now = time.time()
                                    if self.last_wps_update_time is not None:
                                        delta = max(
                                            0.0, now - self.last_wps_update_time
                                        )
                                        self.words_processed += int(
                                            wps_value * delta
                                        )
                                    self.last_wps_update_time = now
                                    self.words_processed_abbr = (
                                        self.abbreviate_number(
                                            self.words_processed
                                        )
                                    )
                                    short_ssid = ssid[:4]
                                    short_wl = wl_name[:4]
                                    self.status_message = (
                                        f"{short_ssid} {short_wl} {wps_value}W/s"
                                    )
                                    self._append_limited(
                                        self.wps_data, wps_value
                                    )
                                    self.on_ui_update(self.ui)

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
                        with self.lock:
                            self.current_task = None

                    if handshake_cracked or timed_out or bad_capture:
                        break

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
