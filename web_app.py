"""Zero-Intelligence & TypeSafe AI Continuous Double Auction Web Interface.

Features:
1. Canonical Gode & Sunder (1993) Precision Analytics:
   - Market Price: Running Mean Trade Price, Quote Midpoint, and Last Clearing Price
   - Standard Deviation from Equilibrium (RMSE) and Price Dispersion (Sigma)
   - Allocative Efficiency: Realized Surplus / Maximum Theoretical Surplus (%)
   - Volume Precision: Realized Q vs Theoretical Q*
2. Responsive 90-degree Flipped Order Book Depth (Price on X, Accumulated Q on Y)
3. Equilibrium stopping condition (halts when all gains from trade are exhausted)
4. Running Mean Market Price & Dispersion Corridor in price convergence chart
"""

import http.server
import json
import math
import os
import socket
import socketserver
import urllib.parse
from agent_jev import JevBuyer, JevSeller, JevTrader
from model.agents import Buyer, Seller, Trader
from model.model import DoubleAuctionModel

HTML_CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Continuous Double Auction (ABM)</title>
<style>
  :root {
    --bg: #0b0f19;
    --card: #151d2e;
    --card-border: #26334d;
    --text: #f1f5f9;
    --text-muted: #94a3b8;
    --bid: #10b981;
    --ask: #ef4444;
    --primary: #3b82f6;
    --primary-hover: #2563eb;
    --accent: #f59e0b;
    --eq-color: #a855f7;
    --cyan: #06b6d4;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  body { background: var(--bg); color: var(--text); padding: 20px; font-size: 13px; line-height: 1.4; max-width: 1400px; margin: 0 auto; }
  
  header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 12px; }
  h1 { font-size: 1.35rem; font-weight: 700; color: #fff; }
  .subtitle { color: var(--text-muted); font-size: 0.82rem; }

  .controls { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  button {
    background: #1e293b; color: #fff; border: 1px solid var(--card-border);
    padding: 7px 15px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 13px;
    transition: all 0.15s ease;
  }
  button:hover { background: #334155; }
  button.primary { background: var(--primary); border-color: var(--primary); }
  button.primary:hover { background: var(--primary-hover); }
  button.danger { background: #b91c1c; border-color: #b91c1c; }
  button.danger:hover { background: #dc2626; }

  .config-bar {
    background: var(--card); border: 1px solid var(--card-border); border-radius: 8px;
    padding: 14px 18px; margin-bottom: 16px;
  }
  .config-title { font-size: 0.8rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }
  .config-grid {
    display: grid; grid-template-columns: 240px repeat(auto-fit, minmax(150px, 1fr)) 120px; gap: 16px; align-items: flex-end;
  }
  @media (max-width: 1020px) { .config-grid { grid-template-columns: 1fr 1fr; } }
  @media (max-width: 600px) { .config-grid { grid-template-columns: 1fr; } }

  .param-box { display: flex; flex-direction: column; gap: 4px; }
  .param-box label { font-size: 0.78rem; color: var(--text); display: flex; justify-content: space-between; }
  .param-box select, .param-box input[type="number"] {
    background: #0f172a; border: 1px solid var(--card-border); color: #fff; padding: 6px 10px; border-radius: 5px; font-size: 13px;
  }
  .param-box input[type="range"] { accent-color: var(--primary); cursor: pointer; margin-top: 4px; }

  .market-status-banner {
    display: none;
    background: rgba(168, 85, 247, 0.14);
    border: 1px solid var(--eq-color);
    color: #f3e8ff;
    border-radius: 8px;
    padding: 12px 18px;
    margin-bottom: 16px;
    font-weight: 600;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .grid-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 16px; }
  .stat-card { background: var(--card); border: 1px solid var(--card-border); border-radius: 8px; padding: 12px; }
  .stat-title { color: var(--text-muted); font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 4px; }
  .stat-value { font-size: 1.25rem; font-weight: 700; color: #fff; }
  .stat-sub { font-size: 0.76rem; color: var(--text-muted); margin-top: 3px; }

  .panel { background: var(--card); border: 1px solid var(--card-border); border-radius: 8px; padding: 14px; margin-bottom: 16px; }
  .panel-title { font-size: 0.85rem; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center; }

  .charts-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  @media (max-width: 900px) { .charts-row { grid-template-columns: 1fr; } }

  .canvas-container { width: 100%; position: relative; height: 230px; }
  .canvas-container-half { width: 100%; position: relative; height: 200px; }
  canvas { width: 100%; height: 100%; display: block; background: #0b0f19; border-radius: 6px; }

  .bottom-grid { display: grid; grid-template-columns: 1.2fr 1fr 1fr; gap: 16px; }
  @media (max-width: 960px) { .bottom-grid { grid-template-columns: 1fr; } }

  .list-box { background: #0b0f19; border-radius: 6px; padding: 10px; max-height: 220px; overflow-y: auto; }
  .list-title { font-size: 0.75rem; font-weight: 700; padding-bottom: 6px; margin-bottom: 6px; border-bottom: 1px solid var(--card-border); }
  .ob-row { display: flex; justify-content: space-between; font-size: 0.78rem; padding: 3px 6px; border-radius: 4px; margin-bottom: 2px; }
  .ob-bid { color: var(--bid); background: rgba(16, 185, 129, 0.08); }
  .ob-ask { color: var(--ask); background: rgba(239, 68, 68, 0.08); }
  .trade-item {
    display: flex; justify-content: space-between; align-items: center;
    font-size: 0.77rem; padding: 5px 8px; background: #151d2e; border-radius: 4px;
    border-left: 3px solid var(--accent); margin-bottom: 4px;
  }

  .badge { font-size: 0.72rem; padding: 2px 8px; border-radius: 4px; font-weight: 600; }
</style>
</head>
<body>

<header style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 12px;">
  <div>
    <h1>Continuous Double Auction (Gode & Sunder ABM)</h1>
    <div class="subtitle" id="modelSubtitle">Continuous Poisson-Arrival Market • Price Dispersion & Efficiency Analytics</div>
  </div>

  <!-- RIGHT CORNER: PLAYBACK CONTROLS -->
  <div class="controls" style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
    <button id="btnPlay" class="primary" onclick="togglePlay()">Play</button>
    <button id="btnStepMicro" onclick="stepModel(0.2)" title="Advance market by 0.2s (~8-10 arrivals)">Step (+0.2)</button>
    <button id="btnStep" onclick="stepModel(1.0)">Step (+1.0)</button>
    <button id="btnStepFast" onclick="stepModel(5.0)">Step (+5.0)</button>
    <button class="danger" onclick="resetModel()">Reset</button>
    <label style="margin-left: 6px; color: var(--text-muted); font-size: 12px; display: flex; align-items: center; gap: 4px;">Limit:
      <input type="number" id="quickMaxSteps" min="1" max="1000" value="50" style="width: 52px; background: var(--card); border: 1px solid var(--card-border); color: #fff; padding: 4px 6px; border-radius: 4px; font-size: 12px;" oninput="syncMaxSteps(this.value)" title="Max ticks before auto-pausing">
    </label>
    <label style="margin-left: 6px; color: var(--text-muted); font-size: 12px; display: flex; align-items: center; gap: 4px;">Speed:
      <select id="speedSelect" style="background: var(--card); color: #fff; border: 1px solid var(--card-border); border-radius: 4px; padding: 4px 6px;">
        <option value="400">0.5x</option>
        <option value="180" selected>1x</option>
        <option value="70">2.5x</option>
        <option value="25">5x</option>
      </select>
    </label>
  </div>
</header>

<!-- UNIFIED TYPESAFE AI TELEMETRY & API CONNECTION RIBBON -->
<div id="typesafeUnifiedBar" style="
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
  border: 1px solid rgba(56, 189, 248, 0.4);
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.4);
  border-radius: 8px;
  padding: 12px 18px;
  margin-bottom: 16px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
">
  <!-- Left: Token Counts, Spend & Cache Savings -->
  <div style="display: flex; align-items: center; gap: 18px; flex-wrap: wrap;">
    <div>
      <div style="display: flex; align-items: center; gap: 6px; font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8;">
        <span id="tsStatusDot" style="width: 8px; height: 8px; border-radius: 50%; background: #38bdf8; display: inline-block;"></span>
        <span id="tsModelTitle" style="font-weight: 700; color: #e2e8f0;">TypeSafe Spend</span>
      </div>
      <div id="tsTotalSpend" style="font-size: 1.35rem; font-weight: 800; color: #38bdf8; font-variant-numeric: tabular-nums; line-height: 1.1; margin-top: 2px;">$0.000000</div>
    </div>

    <div style="border-left: 1px solid rgba(255,255,255,0.12); padding-left: 16px;">
      <div style="font-size: 0.68rem; color: #94a3b8;">Tokens Used:</div>
      <div id="tsTokenCounts" style="font-size: 0.9rem; font-weight: 700; color: #f1f5f9; font-variant-numeric: tabular-nums;">0 in • 0 out</div>
      <div id="tsRateInfo" style="font-size: 0.64rem; color: #06b6d4;">$0.042/Mtok • Out free</div>
    </div>

    <div style="border-left: 1px solid rgba(255,255,255,0.12); padding-left: 16px;">
      <div style="font-size: 0.68rem; color: #94a3b8;">Cache Savings:</div>
      <div id="tsSavedTokens" style="font-size: 0.9rem; font-weight: 700; color: #10b981; font-variant-numeric: tabular-nums;">0 saved (0%)</div>
      <div id="tsSavedSpend" style="font-size: 0.64rem; color: #34d399;">Saved $0.000000</div>
    </div>
  </div>

  <!-- Right: API Key Input & Live Connection Indicator -->
  <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 8px;">
    <!-- Live Server Connection Status Indicator -->
    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
      <div id="serverLiveIndicator" style="display: flex; align-items: center; gap: 6px; font-size: 0.72rem; font-weight: 600; padding: 4px 10px; border-radius: 6px; background: rgba(148, 163, 184, 0.12); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.25);">
        <span id="serverDot" style="width: 7px; height: 7px; border-radius: 50%; background: #94a3b8; display: inline-block;"></span>
        <span id="serverStatusText">TypeSafe Cloud: Standby (Offline Simulation)</span>
        <button id="btnPing" onclick="testConnectionLive()" style="background: none; border: none; color: #38bdf8; cursor: pointer; padding: 0 4px; font-size: 11px; margin-left: 4px; text-decoration: underline;" title="Test live server connectivity">⚡ Ping</button>
      </div>
    </div>

    <!-- API Key Input Field -->
    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
      <span style="font-size: 0.76rem; font-weight: 700; color: #cbd5e1;">🔑 API Key:</span>
      <div style="position: relative; display: inline-flex; align-items: center;">
        <input type="password" id="inputApiKey" placeholder="Paste TYPESAFE_API_KEY (e.g. sk-typ_...)" 
               style="width: 290px; background: #0b0f19; border: 1px solid #334155; color: #fff; padding: 6px 30px 6px 10px; border-radius: 5px; font-size: 12px; font-family: monospace;">
        <button type="button" id="btnToggleKeyVis" onclick="toggleApiKeyVisibility()" 
                style="position: absolute; right: 5px; background: none; border: none; padding: 2px 4px; cursor: pointer; color: #94a3b8; font-size: 11px;" title="Show/Hide Key">👁️</button>
      </div>
      <button class="primary" style="padding: 6px 12px; font-size: 12px;" onclick="saveApiKey()">Save & Connect</button>
      <button id="btnClearKey" style="display: none; padding: 6px 10px; font-size: 12px; background: #334155;" onclick="clearApiKey()">Disconnect</button>
    </div>
  </div>
</div>

<!-- JEV AGENTS & ZI-C COGNITIVE / HEURISTIC DECISION MAKING CONSOLE -->
<div id="jevDecisionConsole" style="
  background: linear-gradient(180deg, #111827 0%, #0f172a 100%);
  border: 1px solid #1f293d;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 4px 18px rgba(0, 0, 0, 0.4);
  width: 100%;
  box-sizing: border-box;
  overflow: hidden;
">
  <!-- 1. Top Title Bar -->
  <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 10px; width: 100%;">
    <div style="display: flex; align-items: center; gap: 10px;">
      <span id="consoleIcon" style="font-size: 1.3rem;">🧠</span>
      <div>
        <div style="font-size: 0.92rem; font-weight: 700; color: #f8fafc; display: flex; align-items: center; gap: 8px;">
          <span id="consoleTitleText">TypeSafe Jev System One • Market Cognitive Overview</span>
          <span id="jevModeBadge" class="badge" style="background: rgba(6, 182, 212, 0.2); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.4);">Jev Active</span>
        </div>
        <div id="consoleSubtitle" style="font-size: 0.72rem; color: #94a3b8;">Autonomous agent cognitive reasoning, stochastic Choice primitives, and order book delta caching</div>
      </div>
    </div>

    <!-- Quick Telemetry Chips & Collapsible Inspector Toggle -->
    <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
      <div class="stat-pill" style="background: #1e293b; padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; border: 1px solid #334155;">
        <span id="chipLabel1" style="color: #94a3b8;">Primitive:</span> <b id="chipAvgScore" style="color: #38bdf8;">—</b>
      </div>
      <div class="stat-pill" style="background: #1e293b; padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; border: 1px solid #334155;">
        <span id="chipLabel2" style="color: #94a3b8;">Cache Hit Ratio:</span> <b id="chipCacheRatio" style="color: #34d399;">—</b>
      </div>
      <div class="stat-pill" style="background: #1e293b; padding: 4px 10px; border-radius: 6px; font-size: 0.72rem; border: 1px solid #334155;">
        <span style="color: #94a3b8;">Active Traders:</span> <b id="chipActiveTraders" style="color: #f1f5f9;">50</b>
      </div>
      <button id="btnToggleInspector" onclick="toggleInspectorCollapse()" style="
        background: #1e293b; border: 1px solid #38bdf8; color: #38bdf8; padding: 5px 12px; border-radius: 6px; font-size: 0.72rem; cursor: pointer; font-weight: 600; display: flex; align-items: center; gap: 5px;
      ">
        <span id="toggleInspectorIcon">🔍</span> <span id="toggleInspectorText">Expand Agent Inspector</span>
      </button>
    </div>
  </div>

  <!-- Active Decision Visualization Body (Always Visible For Both Jev and ZI-C) -->
  <div id="jevActiveBody" style="width: 100%; box-sizing: border-box;">
    <!-- 2. Spectrum / Tactic Distribution Bar (100% full width) -->
    <div style="margin-bottom: 14px; background: #0b0f19; border-radius: 6px; padding: 10px 14px; border: 1px solid #1e293b; width: 100%; box-sizing: border-box;">
      <div style="display: flex; justify-content: space-between; font-size: 0.72rem; color: #94a3b8; margin-bottom: 6px; font-weight: 600;">
        <span id="spectrumBarTitle">COGNITIVE TACTIC SPECTRUM (4 STOCHASTIC ARCHETYPES)</span>
        <span id="spectrumTotalsText">0 Total Recorded Decisions</span>
      </div>
      <div style="height: 12px; width: 100%; border-radius: 6px; background: #1e293b; display: flex; overflow: hidden; box-sizing: border-box;" id="spectrumBar">
        <div id="specUrgent" style="width: 20%; background: #c084fc; height: 100%; transition: width 0.3s ease;" title="Urgent Taker"></div>
        <div id="specCrosser" style="width: 20%; background: #38bdf8; height: 100%; transition: width 0.3s ease;" title="Spread Crosser"></div>
        <div id="specQueue" style="width: 20%; background: #10b981; height: 100%; transition: width 0.3s ease;" title="Queue Competitor"></div>
        <div id="specMaker" style="width: 20%; background: #f59e0b; height: 100%; transition: width 0.3s ease;" title="Patient Maker"></div>
        <div id="specDiscount" style="width: 20%; background: #64748b; height: 100%; transition: width 0.3s ease;" title="Deep Discount / Guard"></div>
      </div>
      <!-- Legend with responsive wrap -->
      <div id="spectrumLegend" style="display: flex; justify-content: space-between; margin-top: 6px; font-size: 0.68rem; color: #94a3b8; flex-wrap: wrap; gap: 8px;">
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #c084fc;"></span> Urgent Taker (3.8-4.0)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #38bdf8;"></span> Spread Crosser (3.0-3.8)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #10b981;"></span> Queue Competitor (2.0-3.0)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #f59e0b;"></span> Patient Maker (1.0-2.0)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #64748b;"></span> Discount / Guard (0-1.0)</span>
      </div>
    </div>

    <!-- 3. COLLAPSIBLE INDIVIDUAL AGENT INSPECTOR DRAWER -->
    <div id="collapsibleAgentInspector" style="
      display: none;
      margin-bottom: 14px;
      background: #0b0f19;
      border: 1px solid #38bdf8;
      border-radius: 6px;
      padding: 14px;
      width: 100%;
      box-sizing: border-box;
      overflow: hidden;
    ">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid #1e293b;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span id="inspectorTitle" style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; color: #38bdf8; letter-spacing: 0.04em;">Individual Agent Cognitive Deep Dive</span>
          <span id="selectedAgentBadge" class="badge" style="background: #1e293b; color: #38bdf8;">Select an Agent</span>
        </div>
        <button onclick="toggleInspectorCollapse(false)" style="background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 13px;" title="Hide Inspector">✕ Close</button>
      </div>

      <!-- Agent Selector Wrap (50 traders, wraps cleanly) -->
      <div style="margin-bottom: 12px;">
        <div style="font-size: 0.68rem; color: #94a3b8; margin-bottom: 5px;">Select Any Trader to Inspect (50 Total):</div>
        <div id="agentSelectorChips" style="display: flex; gap: 4px; flex-wrap: wrap; max-height: 85px; overflow-y: auto; width: 100%; box-sizing: border-box; padding: 2px;">
          <!-- Populated by JS -->
        </div>
      </div>

      <!-- Inspector Content Card -->
      <div id="agentInspectorCard" style="background: #151d2e; border: 1px solid #26334d; border-radius: 6px; padding: 12px; width: 100%; box-sizing: border-box; font-size: 0.74rem;">
        <!-- Populated by JS -->
      </div>
    </div>

    <!-- 4. LIVE DECISION STREAM (Total Market View - Responsive Full Width Grid) -->
    <div style="background: #0b0f19; border: 1px solid #1e293b; border-radius: 6px; padding: 12px; width: 100%; box-sizing: border-box; overflow: hidden;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid #1e293b; flex-wrap: wrap; gap: 6px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span id="streamTitle" style="font-size: 0.78rem; font-weight: 700; text-transform: uppercase; color: #cbd5e1; letter-spacing: 0.04em;">Live Jev Decision Stream</span>
          <span id="streamSubtitle" style="font-size: 0.7rem; color: #94a3b8;">(Continuous arrival events & order book interactions)</span>
        </div>
        <span style="font-size: 0.7rem; color: #38bdf8;">Tip: Click any decision card to open deep inspection</span>
      </div>
      <div id="jevDecisionFeed" style="
        max-height: 320px;
        overflow-y: auto;
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(310px, 1fr));
        gap: 8px;
        padding-right: 4px;
        width: 100%;
        box-sizing: border-box;
      ">
        <div style="color: #64748b; font-size: 0.74rem; text-align: center; padding: 30px; grid-column: 1 / -1;">No decisions logged yet. Step the CDA model to observe agent arrivals.</div>
      </div>
    </div>
  </div>
</div>

<!-- TOP CONFIGURATION BAR -->
<div class="config-bar">
  <div class="config-title">
    <span>Model Configuration & Strategy</span>
    <span style="font-weight: normal; color: #3b82f6;">Select strategy, set parameters, and press Apply & Reset</span>
  </div>
  <div class="config-grid">
    <div class="param-box">
      <label><b>Trader Intelligence / Strategy</b></label>
      <select id="paramTraderType" style="border: 1px solid #3b82f6; font-weight: 600;" onchange="onTraderTypeChange(this.value)">
        <option value="zi" selected>Zero-Intelligence Constrained (ZI-C)</option>
        <option value="jev">TypeSafe AI (Jev System One)</option>
      </select>
    </div>

    <div class="param-box">
      <label>Buyers: <b id="valBuyers">25</b></label>
      <input type="range" id="paramBuyers" min="5" max="100" value="25" oninput="valBuyers.innerText=this.value">
    </div>

    <div class="param-box">
      <label>Sellers: <b id="valSellers">25</b></label>
      <input type="range" id="paramSellers" min="5" max="100" value="25" oninput="valSellers.innerText=this.value">
    </div>

    <div class="param-box">
      <label>Max Valuation: <b id="valMaxVal">$100</b></label>
      <input type="range" id="paramMaxVal" min="20" max="500" step="10" value="100" oninput="valMaxVal.innerText='$'+this.value">
    </div>

    <div class="param-box">
      <label>Mean Interarrival: <b id="valArrival">1.0</b></label>
      <input type="range" id="paramArrival" min="0.2" max="3.0" step="0.1" value="1.0" oninput="valArrival.innerText=this.value">
    </div>

    <div class="param-box">
      <label>Max Steps Limit: <b id="valMaxSteps">50</b></label>
      <input type="number" id="paramMaxSteps" min="5" max="1000" step="5" value="50" oninput="syncMaxSteps(this.value)" style="background: #0f172a; border: 1px solid var(--card-border); color: #fff; padding: 6px 10px; border-radius: 5px; font-size: 13px;">
    </div>

    <div class="param-box">
      <button class="primary" style="width: 100%; padding: 8px 12px;" onclick="resetModel()">Apply & Reset</button>
    </div>
  </div>
</div>

<div id="marketBanner" class="market-status-banner" style="display: none;">
  <div>
    <span>🎯 Equilibrium Reached:</span> All mutually beneficial gains from trade are exhausted (Max Active Buyer Valuation &lt; Min Active Seller Cost).
  </div>
  <div id="bannerStats" style="font-size: 12px; color: #d8b4fe;"></div>
</div>

<!-- CANONICAL PRECISION METRICS -->
<div class="grid-stats">
  <!-- Metric 1: Time -->
  <div class="stat-card">
    <div class="stat-title">Continuous Time (t)</div>
    <div class="stat-value" id="statTime">0.00s</div>
    <div class="stat-sub" id="statTimeSub">Events fire on Poisson delays</div>
  </div>

  <!-- Metric 2: Market Price & Last Price -->
  <div class="stat-card">
    <div class="stat-title">Market Price (Mean P̄)</div>
    <div class="stat-value" id="statMarketPrice">—</div>
    <div class="stat-sub" id="statMarketPriceSub">Last Trade: — | Midpoint: —</div>
  </div>

  <!-- Metric 3: Dispersion & Distance from Equilibrium -->
  <div class="stat-card">
    <div class="stat-title">Price Dispersion (Std Dev)</div>
    <div class="stat-value" id="statDispersion">—</div>
    <div class="stat-sub" id="statEqDev">RMSE from Eq: —</div>
  </div>

  <!-- Metric 4: Allocative Efficiency -->
  <div class="stat-card">
    <div class="stat-title">Allocative Efficiency</div>
    <div class="stat-value" id="statEfficiency" style="color: #38bdf8;">—%</div>
    <div class="stat-sub" id="statSurplus">Surplus: $0.00 / $0.00 max</div>
  </div>

  <!-- Metric 5: Volume Precision -->
  <div class="stat-card">
    <div class="stat-title">Volume (Trades / Eq Q*)</div>
    <div class="stat-value" id="statVolume">0 / 0</div>
    <div class="stat-sub" id="statSpreadSub">Spread: —</div>
  </div>
</div>

<!-- ORDER BOOK FLIPPED 90 DEGREES -->
<div class="panel">
  <div class="panel-title">
    <span>Accumulated Order Book (Price on Horizontal X-Axis vs Cumulative Quantity on Vertical Y-Axis)</span>
    <span id="obSpreadBadge" class="badge" style="background: rgba(245, 158, 11, 0.2); color: var(--accent);">Spread: —</span>
  </div>
  <div class="canvas-container">
    <canvas id="obCanvas"></canvas>
  </div>
  <div style="display: flex; justify-content: space-between; margin-top: 8px; font-size: 11px; color: var(--text-muted);">
    <span>Horizontal: Price ($) • Vertical: Accumulated Units (Q) • Amber: Bid-Ask Spread • Purple: Theoretical Eq Price P*</span>
    <span id="obCountsText">Resting Bids: 0 | Resting Asks: 0</span>
  </div>
</div>

<!-- CHARTS ROW: THEORETICAL VALUATIONS & CONVERGENCE -->
<div class="charts-row">
  <div class="panel">
    <div class="panel-title">Underlying Valuations (Theoretical Supply & Demand)</div>
    <div class="canvas-container-half">
      <canvas id="sdCanvas"></canvas>
    </div>
  </div>

  <div class="panel">
    <div class="panel-title">
      <span>Transaction Price Convergence & Dispersion</span>
      <span style="font-size: 11px; font-weight: normal; color: var(--text-muted);">
        <span style="color: #a855f7;">■</span> Eq P* 
        <span style="color: #06b6d4; margin-left: 6px;">■</span> Mean P̄ 
        <span style="color: #10b981; margin-left: 6px;">●</span> Trades
      </span>
    </div>
    <div class="canvas-container-half">
      <canvas id="priceCanvas"></canvas>
    </div>
  </div>
</div>

<!-- BOTTOM LISTS -->
<div class="bottom-grid">
  <div class="panel">
    <div class="panel-title">Recent Transactions Tape (With Generated Surplus)</div>
    <div class="list-box" id="tradesList"></div>
  </div>

  <div class="panel">
    <div class="panel-title" style="color: var(--bid);">Resting Bids (Ranked Highest First)</div>
    <div class="list-box" id="bidsList"></div>
  </div>

  <div class="panel">
    <div class="panel-title" style="color: var(--ask);">Resting Asks (Ranked Lowest First)</div>
    <div class="list-box" id="asksList"></div>
  </div>
</div>

<script>
let eqData = null;
let currentData = null;

function setupCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  return { ctx, w: rect.width, h: rect.height };
}

window.addEventListener('resize', () => {
  if (currentData) {
    drawFlippedOrderBook(currentData);
    drawSDChart();
    drawPriceChart(currentData.all_trades, currentData.time, currentData.stats);
  }
});

async function fetchState() {
  try {
    const res = await fetch('/api/state');
    const data = await res.json();
    currentData = data;
    eqData = data.equilibrium;
    if (data.trader_type) {
      document.getElementById('paramTraderType').value = data.trader_type;
    }
    render(data);
  } catch (err) {
    console.error("Fetch state error:", err);
  }
}

async function switchToJevMode() {
  document.getElementById('paramTraderType').value = 'jev';
  await resetModel();
}

async function onTraderTypeChange(val) {
  await resetModel();
}

let isPlaying = false;
let isStepping = false;
let playTimeout = null;
let currentStepAbort = null;

function syncMaxSteps(val) {
  const num = Math.max(1, parseInt(val) || 50);
  document.getElementById('paramMaxSteps').value = num;
  document.getElementById('quickMaxSteps').value = num;
  document.getElementById('valMaxSteps').innerText = num;
}

async function stepModel(dt = 1.0) {
  if (isStepping) return;
  const selectedType = document.getElementById('paramTraderType').value;
  if (currentData && currentData.trader_type !== selectedType) {
    await resetModel();
  }
  const maxSteps = parseInt(document.getElementById('paramMaxSteps').value) || 50;
  if (currentData && (currentData.is_equilibrium_reached || currentData.steps_taken >= maxSteps)) {
    if (isPlaying) togglePlay();
    return;
  }

  isStepping = true;
  currentStepAbort = new AbortController();

  try {
    const res = await fetch('/api/step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dt }),
      signal: currentStepAbort.signal,
    });
    const data = await res.json();
    currentData = data;
    render(data);

    if ((data.is_equilibrium_reached || data.steps_taken >= maxSteps) && isPlaying) {
      togglePlay();
    }
  } catch (err) {
    if (err.name !== 'AbortError') {
      console.error("Step error:", err);
    }
  } finally {
    isStepping = false;
    currentStepAbort = null;
  }
}

async function runPlayLoop() {
  if (!isPlaying) return;
  const maxSteps = parseInt(document.getElementById('paramMaxSteps').value) || 50;
  if (currentData && (currentData.is_equilibrium_reached || currentData.steps_taken >= maxSteps)) {
    togglePlay();
    return;
  }

  // Use micro-tick (0.2s) during playback for rapid, responsive streaming updates
  const isJev = document.getElementById('paramTraderType').value === 'jev';
  const dt = isJev ? 0.2 : 0.4;
  await stepModel(dt);

  if (isPlaying && currentData && !currentData.is_equilibrium_reached && currentData.steps_taken < maxSteps) {
    const speed = parseInt(document.getElementById('speedSelect').value);
    playTimeout = setTimeout(runPlayLoop, speed);
  } else if (isPlaying) {
    togglePlay();
  }
}

async function resetModel() {
  if (isPlaying) togglePlay();
  const traderType = document.getElementById('paramTraderType').value;
  const maxSteps = parseInt(document.getElementById('paramMaxSteps').value) || 50;
  const params = {
    trader_type: traderType,
    n_buyers: parseInt(document.getElementById('paramBuyers').value),
    n_sellers: parseInt(document.getElementById('paramSellers').value),
    max_valuation: parseFloat(document.getElementById('paramMaxVal').value),
    mean_interarrival: parseFloat(document.getElementById('paramArrival').value),
    max_steps: maxSteps,
  };
  const res = await fetch('/api/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params)
  });
  const data = await res.json();
  currentData = data;
  eqData = data.equilibrium;
  
  document.getElementById('modelSubtitle').innerText = traderType === 'jev' 
    ? 'TypeSafe AI (Jev System One) • Cognitive Traders' 
    : 'Continuous Poisson-Arrival Market • Price Dispersion & Efficiency Analytics';

  render(data);
}

async function togglePlay() {
  const selectedType = document.getElementById('paramTraderType').value;
  if (currentData && currentData.trader_type !== selectedType) {
    await resetModel();
  }
  const maxSteps = parseInt(document.getElementById('paramMaxSteps').value) || 50;
  if (currentData && currentData.is_equilibrium_reached && !isPlaying) {
    alert("Equilibrium has already been reached! Click Apply & Reset to start a new simulation.");
    return;
  }
  if (currentData && currentData.steps_taken >= maxSteps && !isPlaying) {
    alert(`Max steps limit (${maxSteps}) reached! Increase Max Steps Limit or click Apply & Reset to run further.`);
    return;
  }

  isPlaying = !isPlaying;
  const btn = document.getElementById('btnPlay');
  if (isPlaying) {
    btn.innerText = 'Stop';
    btn.className = 'danger';
    runPlayLoop();
  } else {
    btn.innerText = 'Play';
    btn.className = 'primary';
    if (playTimeout) {
      clearTimeout(playTimeout);
      playTimeout = null;
    }
    if (currentStepAbort) {
      currentStepAbort.abort();
      currentStepAbort = null;
    }
    isStepping = false;
    // Send immediate stop signal to Python server to cancel any chunk loop
    fetch('/api/stop', { method: 'POST' }).catch(() => {});
  }
}

document.getElementById('speedSelect').addEventListener('change', () => {
  // speed dynamically applied on next runPlayLoop cycle
});

let isApiKeyVisible = false;

function toggleApiKeyVisibility() {
  const input = document.getElementById('inputApiKey');
  isApiKeyVisible = !isApiKeyVisible;
  input.type = isApiKeyVisible ? 'text' : 'password';
  document.getElementById('btnToggleKeyVis').innerText = isApiKeyVisible ? '🔒' : '👁️';
}

async function saveApiKey() {
  const input = document.getElementById('inputApiKey');
  const key = input.value.trim();
  if (!key) {
    alert("Please paste your TypeSafe API key first.");
    return;
  }
  const text = document.getElementById('serverStatusText');
  text.innerText = 'Connecting & testing TypeSafe Cloud...';
  try {
    const res = await fetch('/api/set_api_key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: key }),
    });
    const data = await res.json();
    if (data.is_connected) {
      input.value = '';
      input.placeholder = `Active: ${data.masked_key}`;
      if (data.connection) updateConnectionUI(data.connection);
      document.getElementById('paramTraderType').value = 'jev';
      await resetModel();
    } else {
      if (data.connection) updateConnectionUI(data.connection);
      alert("TypeSafe AI Notice: " + (data.connection && data.connection.error_message ? data.connection.error_message : (data.message || "Failed to connect")));
    }
  } catch (e) {
    alert("Error saving API key: " + e.message);
  }
}

async function clearApiKey() {
  try {
    const res = await fetch('/api/set_api_key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ api_key: '' }),
    });
    const data = await res.json();
    const input = document.getElementById('inputApiKey');
    input.value = '';
    input.placeholder = 'Paste TYPESAFE_API_KEY (e.g. sk-typ_...)';
    updateConnectionUI(null);
    fetchState();
  } catch (e) {
    alert("Error clearing API key: " + e.message);
  }
}

async function testConnectionLive() {
  const text = document.getElementById('serverStatusText');
  text.innerText = 'Pinging TypeSafe Cloud...';
  try {
    const res = await fetch('/api/test_connection');
    const data = await res.json();
    updateConnectionUI(data);
  } catch (e) {
    updateConnectionUI({ tested: true, is_connected: false, error_message: e.message });
  }
}

function updateConnectionUI(conn) {
  const ind = document.getElementById('serverLiveIndicator');
  const dot = document.getElementById('serverDot');
  const text = document.getElementById('serverStatusText');
  if (!conn || !conn.tested) {
    ind.style.background = 'rgba(148, 163, 184, 0.12)';
    ind.style.borderColor = 'rgba(148, 163, 184, 0.25)';
    ind.style.color = '#94a3b8';
    dot.style.background = '#94a3b8';
    text.innerText = 'TypeSafe Cloud: Standby (Offline Simulation)';
    return;
  }
  if (conn.is_connected) {
    ind.style.background = 'rgba(16, 185, 129, 0.16)';
    ind.style.borderColor = 'rgba(16, 185, 129, 0.45)';
    ind.style.color = '#34d399';
    dot.style.background = '#10b981';
    const lat = conn.latency_ms !== null ? ` (${conn.latency_ms}ms latency)` : '';
    text.innerText = `🟢 TypeSafe Cloud: Live Connected${lat}`;
  } else {
    ind.style.background = 'rgba(239, 68, 68, 0.15)';
    ind.style.borderColor = 'rgba(239, 68, 68, 0.4)';
    ind.style.color = '#f87171';
    dot.style.background = '#ef4444';
    const err = conn.error_message ? ` - ${conn.error_message}` : '';
    text.innerText = `🔴 TypeSafe Cloud: Error${err}`;
  }
}

function render(data) {
  if (data.equilibrium) eqData = data.equilibrium;
  const s = data.stats;

  // 1. Time (continuous decimal explanation)
  const maxLimit = data.max_steps || parseInt(document.getElementById('paramMaxSteps').value) || 50;
  const isHalted = data.steps_taken >= maxLimit;
  document.getElementById('statTime').innerText = data.time.toFixed(2) + 's';
  document.getElementById('statTimeSub').innerText = `Step: ${data.steps_taken} / ${maxLimit} ticks${isHalted && !data.is_equilibrium_reached ? ' (Limit reached)' : ''}`;

  // 2. Market Price & Dispersion
  if (s.mean_price !== null) {
    document.getElementById('statMarketPrice').innerText = '$' + s.mean_price.toFixed(2);
    const lastP = data.clearing_price !== null ? '$' + data.clearing_price.toFixed(2) : '—';
    const midP = s.quote_midpoint !== null ? '$' + s.quote_midpoint.toFixed(2) : '—';
    document.getElementById('statMarketPriceSub').innerText = `Last: ${lastP} | Mid: ${midP}`;
  } else {
    document.getElementById('statMarketPrice').innerText = '—';
    document.getElementById('statMarketPriceSub').innerText = 'No trades executed yet';
  }

  // 3. Price Dispersion & RMSE from Eq
  if (s.std_dev !== null && s.rmse_from_eq !== null) {
    document.getElementById('statDispersion').innerText = '±$' + s.std_dev.toFixed(2);
    const eqDelta = eqData && eqData.eq_price ? Math.abs(s.mean_price - eqData.eq_price).toFixed(2) : '—';
    document.getElementById('statEqDev').innerText = `RMSE from P*: ±$${s.rmse_from_eq.toFixed(2)} (Δ $${eqDelta})`;
  } else {
    document.getElementById('statDispersion').innerText = '—';
    document.getElementById('statEqDev').innerText = eqData && eqData.eq_price ? `P* = $${eqData.eq_price.toFixed(2)}` : 'RMSE from P*: —';
  }

  // 4. Allocative Efficiency & Surplus
  if (s.allocative_efficiency !== null) {
    const eff = s.allocative_efficiency;
    const effEl = document.getElementById('statEfficiency');
    effEl.innerText = eff.toFixed(1) + '%';
    effEl.style.color = eff >= 90 ? '#10b981' : (eff >= 70 ? '#f59e0b' : '#38bdf8');
    document.getElementById('statSurplus').innerText = `Surplus: $${s.realized_surplus.toFixed(1)} / $${s.max_surplus.toFixed(1)} max`;
  } else {
    document.getElementById('statEfficiency').innerText = '—%';
    document.getElementById('statSurplus').innerText = eqData && eqData.max_surplus ? `Max Surplus: $${eqData.max_surplus.toFixed(1)}` : 'Surplus: $0.00';
  }

  // 5. Volume Precision
  const eqQty = eqData ? eqData.eq_qty : 0;
  const volEl = document.getElementById('statVolume');
  volEl.innerText = `${data.cumulative_volume} / ${eqQty}`;
  const spreadStr = data.spread !== null ? `$${data.spread.toFixed(2)}` : 'One-Sided';
  document.getElementById('statSpreadSub').innerText = `Current Spread: ${spreadStr}`;

  // Equilibrium Banner
  const banner = document.getElementById('marketBanner');
  if (data.is_equilibrium_reached) {
    banner.style.display = 'flex';
    document.getElementById('bannerStats').innerText = `Realized Allocative Efficiency: ${s.allocative_efficiency ? s.allocative_efficiency.toFixed(1) : 100}% (${data.cumulative_volume} of ${eqQty} units)`;
    document.getElementById('btnStep').disabled = true;
    document.getElementById('btnStepFast').disabled = true;
    document.getElementById('btnPlay').disabled = true;
  } else if (isHalted) {
    banner.style.display = 'none';
    document.getElementById('btnStep').disabled = true;
    document.getElementById('btnStepFast').disabled = true;
  } else {
    banner.style.display = 'none';
    document.getElementById('btnStep').disabled = false;
    document.getElementById('btnStepFast').disabled = false;
    document.getElementById('btnPlay').disabled = false;
  }

  // Order Book Badge & Counts
  document.getElementById('obSpreadBadge').innerText = data.spread !== null ? `Spread: $${data.spread.toFixed(2)}` : 'Book One-Sided';
  document.getElementById('obCountsText').innerText = `Resting Bids: ${data.all_bids.length} | Resting Asks: ${data.all_asks.length}`;

  const bidsEl = document.getElementById('bidsList');
  if (data.bids.length === 0) {
    bidsEl.innerHTML = '<div style="color: var(--text-muted); font-size: 0.75rem; padding: 4px;">No resting bids</div>';
  } else {
    bidsEl.innerHTML = data.bids.map((b, i) => 
      `<div class="ob-row ob-bid"><span>#${i+1} Buyer ${b.agent_id}</span><b>$${b.price.toFixed(2)}</b></div>`
    ).join('');
  }

  const asksEl = document.getElementById('asksList');
  if (data.asks.length === 0) {
    asksEl.innerHTML = '<div style="color: var(--text-muted); font-size: 0.75rem; padding: 4px;">No resting asks</div>';
  } else {
    asksEl.innerHTML = data.asks.map((a, i) => 
      `<div class="ob-row ob-ask"><span>#${i+1} Seller ${a.agent_id}</span><b>$${a.price.toFixed(2)}</b></div>`
    ).join('');
  }

  // Recent Transactions Tape
  const tradesEl = document.getElementById('tradesList');
  if (data.trade_records.length === 0) {
    tradesEl.innerHTML = '<div style="color: var(--text-muted); font-size: 0.78rem;">No trades yet. Click Play or Step.</div>';
  } else {
    tradesEl.innerHTML = data.trade_records.slice(-10).reverse().map(t => 
      `<div class="trade-item">
         <div>
           <b style="color: #fff;">$${t.price.toFixed(2)}</b>
           <span style="color: var(--text-muted); font-size: 11px; margin-left: 6px;">t = ${t.time.toFixed(2)}s</span>
         </div>
         <div>
           <span style="color: #38bdf8; font-size: 11px; margin-right: 8px;">Surplus: +$${t.surplus.toFixed(2)}</span>
           <span style="color: var(--text-muted); font-size: 10px;">B#${t.buyer_id} ↔ S#${t.seller_id}</span>
         </div>
       </div>`
    ).join('');
  }

  // 6. TypeSafe Telemetry, Spend Ledger & Live Connection
  const ts = data.typesafe_telemetry;
  if (ts) {
    const isJev = data.trader_type === 'jev';
    const bar = document.getElementById('typesafeUnifiedBar');
    const dot = document.getElementById('tsStatusDot');
    const title = document.getElementById('tsModelTitle');
    const spend = document.getElementById('tsTotalSpend');
    const tokens = document.getElementById('tsTokenCounts');
    const rate = document.getElementById('tsRateInfo');
    const savedTok = document.getElementById('tsSavedTokens');
    const savedSp = document.getElementById('tsSavedSpend');
    const btnClear = document.getElementById('btnClearKey');
    const input = document.getElementById('inputApiKey');

    if (ts.api_key_status && ts.api_key_status.is_connected) {
      btnClear.style.display = 'inline-block';
      if (!input.value) input.placeholder = `Connected: ${ts.api_key_status.masked_key}`;
    } else {
      btnClear.style.display = 'none';
      if (!input.value) input.placeholder = 'Paste TYPESAFE_API_KEY (e.g. sk-typ_...)';
    }

    if (ts.connection_test) {
      updateConnectionUI(ts.connection_test);
    }

    if (isJev) {
      bar.style.borderColor = 'rgba(56, 189, 248, 0.6)';
      bar.style.background = 'linear-gradient(135deg, #0f172a 0%, #172554 100%)';
      dot.style.background = ts.is_live_api ? '#10b981' : '#38bdf8';
      title.innerText = ts.is_live_api ? 'TypeSafe AI (Live API Verified)' : 'TypeSafe AI (Jev 1.13)';
      spend.innerText = '$' + ts.total_spend_usd.toFixed(6);
      tokens.innerText = `${ts.total_input_tokens.toLocaleString()} in • ${ts.total_output_tokens.toLocaleString()} out`;
      rate.innerText = ts.is_live_api ? '✓ Verified usage.input_tokens' : '$0.042/Mtok • Out free';

      const totalDecisions = ts.total_decisions || 1;
      const savedDecisions = ts.cached_skips + ts.submarginal_skips;
      const savedPct = ((savedDecisions / totalDecisions) * 100).toFixed(0);
      savedTok.innerText = `${ts.saved_input_tokens.toLocaleString()} saved (${savedPct}%)`;
      savedSp.innerText = `Saved $${ts.saved_spend_usd.toFixed(6)}`;
    } else {
      bar.style.borderColor = 'rgba(255, 255, 255, 0.1)';
      bar.style.background = 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)';
      dot.style.background = '#64748b';
      title.innerText = 'ZI-C Strategy (Zero AI Tokens)';
      spend.innerText = '$0.000000';
      tokens.innerText = '0 tokens (Heuristic)';
      rate.innerText = 'Switch to Jev to run AI';
      savedTok.innerText = 'No AI calls needed';
      savedSp.innerText = 'Free execution';
    }
  }

  // Jev Cognitive Decision Visualizer & Inspector
  renderJevDecisions(data);

  // Draw Charts
  drawFlippedOrderBook(data);
  drawSDChart();
  drawPriceChart(data.all_trades, data.time, s);
}

let selectedAgentId = null;
let isInspectorExpanded = false;

function toggleInspectorCollapse(forceState) {
  if (typeof forceState === 'boolean') {
    isInspectorExpanded = forceState;
  } else {
    isInspectorExpanded = !isInspectorExpanded;
  }
  const drawer = document.getElementById('collapsibleAgentInspector');
  const icon = document.getElementById('toggleInspectorIcon');
  const text = document.getElementById('toggleInspectorText');
  const btn = document.getElementById('btnToggleInspector');

  if (drawer) {
    drawer.style.display = isInspectorExpanded ? 'block' : 'none';
  }
  if (icon) icon.innerText = isInspectorExpanded ? '▴' : '🔍';
  if (text) text.innerText = isInspectorExpanded ? 'Collapse Inspector' : 'Expand Agent Inspector';
  if (btn) {
    btn.style.background = isInspectorExpanded ? 'rgba(56, 189, 248, 0.2)' : '#1e293b';
    btn.style.borderColor = isInspectorExpanded ? '#38bdf8' : '#334155';
  }
  if (isInspectorExpanded && currentData) {
    renderAgentInspectorDetails(currentData);
  }
}

function renderJevDecisions(data) {
  const isJev = data.trader_type === 'jev';
  const icon = document.getElementById('consoleIcon');
  const titleText = document.getElementById('consoleTitleText');
  const subtitle = document.getElementById('consoleSubtitle');
  const badge = document.getElementById('jevModeBadge');
  const chipLabel1 = document.getElementById('chipLabel1');
  const chipAvg = document.getElementById('chipAvgScore');
  const chipLabel2 = document.getElementById('chipLabel2');
  const chipCache = document.getElementById('chipCacheRatio');
  const chipActive = document.getElementById('chipActiveTraders');
  const specTitle = document.getElementById('spectrumBarTitle');
  const specTotals = document.getElementById('spectrumTotalsText');
  const specLegend = document.getElementById('spectrumLegend');
  const streamTitle = document.getElementById('streamTitle');
  const streamSub = document.getElementById('streamSubtitle');
  const inspectorTitle = document.getElementById('inspectorTitle');

  const ts = data.typesafe_telemetry || {};
  const isLive = ts.is_live_api;
  const decisions = data.jev_decisions || [];
  const agents = data.jev_agents || [];

  if (isJev) {
    if (icon) icon.innerText = '🧠';
    if (titleText) titleText.innerText = 'TypeSafe Jev System One • Market Cognitive Overview';
    if (subtitle) subtitle.innerText = 'Autonomous agent cognitive reasoning, stochastic Choice primitives, and order book delta caching';
    if (badge) {
      badge.innerText = isLive ? '⚡ Live TypeSafe API' : '🧠 Jev System One (Active)';
      badge.style.background = isLive ? 'rgba(16, 185, 129, 0.2)' : 'rgba(6, 182, 212, 0.2)';
      badge.style.color = isLive ? '#34d399' : '#22d3ee';
      badge.style.borderColor = isLive ? 'rgba(16, 185, 129, 0.4)' : 'rgba(6, 182, 212, 0.4)';
    }
    if (chipLabel1) chipLabel1.innerText = 'Primitive:';
    if (chipLabel2) chipLabel2.innerText = 'Cache Hit Ratio:';
    if (chipAvg) {
      if (decisions.length > 0) {
        const avgScore = (decisions.reduce((acc, d) => acc + (d.score || 0), 0) / decisions.length).toFixed(2);
        chipAvg.innerText = "Stochastic Choice";
      } else {
        chipAvg.innerText = '—';
      }
    }
    if (chipCache) {
      const totalDecs = ts.total_decisions || 0;
      const savedDecs = (ts.cached_skips || 0) + (ts.submarginal_skips || 0);
      const cachePct = totalDecs > 0 ? ((savedDecs / totalDecs) * 100).toFixed(0) + '%' : '0%';
      chipCache.innerText = cachePct;
    }
    if (specTitle) specTitle.innerText = 'COGNITIVE TACTIC SPECTRUM (4 STOCHASTIC ARCHETYPES)';
    if (specTotals) specTotals.innerText = `${decisions.length} Logged Decisions (${ts.total_ai_calls || 0} Total AI Calls)`;
    if (streamTitle) streamTitle.innerText = 'Live Jev Decision Stream';
    if (streamSub) streamSub.innerText = '(Continuous arrival events & order book interactions)';
    if (inspectorTitle) inspectorTitle.innerText = 'Individual Agent Cognitive Deep Dive';

    if (specLegend) {
      specLegend.innerHTML = `
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #c084fc;"></span> Urgent Taker (3.8-4.0)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #38bdf8;"></span> Spread Crosser (3.0-3.8)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #10b981;"></span> Queue Competitor (2.0-3.0)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #f59e0b;"></span> Patient Maker (1.0-2.0)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #64748b;"></span> Discount / Guard (0-1.0)</span>
      `;
    }
  } else {
    // ZI-C Mode
    if (icon) icon.innerText = '🎲';
    if (titleText) titleText.innerText = 'Gode & Sunder (1993) • ZI-C Strategy Overview';
    if (subtitle) subtitle.innerText = 'Canonical budget-constrained uniform random bidding • Zero AI tokens ($0.00) baseline';
    if (badge) {
      badge.innerText = '🎲 ZI-C Baseline (Active)';
      badge.style.background = 'rgba(168, 85, 247, 0.2)';
      badge.style.color = '#c084fc';
      badge.style.borderColor = 'rgba(168, 85, 247, 0.4)';
    }
    if (chipLabel1) chipLabel1.innerText = 'Mean Shading:';
    if (chipLabel2) chipLabel2.innerText = 'AI Tokens:';
    if (chipAvg) {
      if (decisions.length > 0) {
        const avgAlpha = (decisions.reduce((acc, d) => acc + (d.alpha || 0), 0) / decisions.length * 100).toFixed(1);
        chipAvg.innerText = `${avgAlpha}%`;
      } else {
        chipAvg.innerText = '—';
      }
    }
    if (chipCache) {
      chipCache.innerText = '0 tok ($0.00)';
    }
    if (specTitle) specTitle.innerText = 'ZI-C UNIFORM DRAW SPECTRUM (BUDGET-CONSTRAINED DRAW BUCKETS)';
    if (specTotals) specTotals.innerText = `${decisions.length} Logged Arrivals (U[0, Val] & U[Cost, MaxP])`;
    if (streamTitle) streamTitle.innerText = 'Live ZI-C Decision Stream';
    if (streamSub) streamSub.innerText = '(Continuous Poisson arrivals subject to budget constraint)';
    if (inspectorTitle) inspectorTitle.innerText = 'Individual ZI-C Agent Inspector';

    if (specLegend) {
      specLegend.innerHTML = `
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #c084fc;"></span> Aggressive (80-100% of Range)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #38bdf8;"></span> High Quote (60-80%)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #10b981;"></span> Mid Range (40-60%)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #f59e0b;"></span> Patient / Low (20-40%)</span>
        <span style="display: flex; align-items: center; gap: 4px;"><span style="display: inline-block; width: 8px; height: 8px; border-radius: 2px; background: #64748b;"></span> Deep Margin (0-20%)</span>
      `;
    }
  }

  if (chipActive) {
    const activeTraders = agents.filter(a => !a.done).length;
    chipActive.innerText = `${activeTraders} / ${agents.length || 50}`;
  }

  // Spectrum Bar Distribution Calculation (Applies to BOTH Jev scores [0..4] and ZI-C scores [0..4])
  let counts = { urgent: 0, crosser: 0, queue: 0, maker: 0, discount: 0 };
  for (const d of decisions) {
    const s = d.score || 0;
    if (s >= 3.2) counts.urgent++;
    else if (s >= 2.4) counts.crosser++;
    else if (s >= 1.6) counts.queue++;
    else if (s >= 0.8) counts.maker++;
    else counts.discount++;
  }
  const totalDec = decisions.length || 1;
  const elU = document.getElementById('specUrgent');
  const elC = document.getElementById('specCrosser');
  const elQ = document.getElementById('specQueue');
  const elM = document.getElementById('specMaker');
  const elD = document.getElementById('specDiscount');
  if (elU) elU.style.width = ((counts.urgent / totalDec) * 100) + '%';
  if (elC) elC.style.width = ((counts.crosser / totalDec) * 100) + '%';
  if (elQ) elQ.style.width = ((counts.queue / totalDec) * 100) + '%';
  if (elM) elM.style.width = ((counts.maker / totalDec) * 100) + '%';
  if (elD) elD.style.width = ((counts.discount / totalDec) * 100) + '%';

  // Render Decision Feed in responsive grid
  const feed = document.getElementById('jevDecisionFeed');
  if (feed) {
    if (decisions.length === 0) {
      feed.innerHTML = `<div style="color: #64748b; font-size: 0.74rem; text-align: center; padding: 30px; grid-column: 1 / -1;">No decisions logged yet. Click Step or Play to observe ${isJev ? 'Jev AI' : 'ZI-C'} traders arrive.</div>`;
    } else {
      feed.innerHTML = decisions.map(d => {
        const isBuyer = d.role === 'Buyer';
        const roleColor = isBuyer ? '#10b981' : '#ef4444';
        let badgeHtml = '';
        if (d.decision_type === 'zi_heuristic') {
          badgeHtml = '<span class="badge" style="background: rgba(168, 85, 247, 0.2); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3);">🎲 ZI Draw (0 tok)</span>';
        } else if (d.decision_type === 'submarginal_guard') {
          badgeHtml = '<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.3);">🛡️ Guard (0 tok)</span>';
        } else if (d.decision_type === 'delta_cache_hit') {
          badgeHtml = '<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3);">💾 Cache (0 tok)</span>';
        } else {
          const liveTag = d.is_live ? 'Live ' : '';
          badgeHtml = `<span class="badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3);">⚡ ${liveTag}Jev (90 tok)</span>`;
        }

        const scorePct = Math.min(100, Math.max(0, ((d.score || 0) / 4.0) * 100));
        const scoreColor = d.score >= 3.0 ? '#c084fc' : (d.score >= 2.0 ? '#38bdf8' : (d.score >= 1.0 ? '#f59e0b' : '#64748b'));
        const isSelected = String(selectedAgentId) === String(d.agent_id);

        return `
          <div onclick="selectAgentToInspect('${d.agent_id}')" style="
            background: ${isSelected ? '#1e293b' : '#111827'};
            border: 1px solid ${isSelected ? '#38bdf8' : '#1f293d'};
            border-left: 3px solid ${roleColor};
            border-radius: 6px;
            padding: 8px 10px;
            cursor: pointer;
            transition: all 0.15s ease;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
          " onmouseover="this.style.background='#1e293b'" onmouseout="this.style.background='${isSelected ? '#1e293b' : '#111827'}'">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <div style="font-weight: 700; color: #fff; font-size: 0.78rem; display: flex; align-items: center; gap: 6px;">
                <span style="color: ${roleColor};">${d.role} #${d.agent_id}</span>
                <span style="color: #94a3b8; font-weight: normal; font-size: 0.72rem;">(${isBuyer ? 'Val' : 'Cost'}: $${d.val.toFixed(2)})</span>
              </div>
              <div style="display: flex; align-items: center; gap: 6px;">
                ${badgeHtml}
                <span style="color: #64748b; font-size: 0.68rem;">t=${d.time.toFixed(2)}s</span>
              </div>
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.73rem; margin-bottom: 4px;">
              <div style="color: #cbd5e1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                <b style="color: ${scoreColor};">${d.tactic}</b> ➔ ${isBuyer ? 'Bid' : 'Ask'} <b>$${d.submitted_price.toFixed(2)}</b>
              </div>
              <div style="display: flex; align-items: center; gap: 4px; font-size: 0.7rem; color: #94a3b8; flex-shrink: 0;">
                
                <div style="width: 38px; height: 6px; background: #334155; border-radius: 3px; overflow: hidden; display: inline-block;">
                  <div style="width: ${scorePct}%; height: 100%; background: ${scoreColor};"></div>
                </div>
                <b style="color: #fff;">${isJev ? (d.score || 0).toFixed(2) : scorePct.toFixed(0) + '%'}</b>
              </div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.68rem; color: #94a3b8; border-top: 1px dashed #1e293b; padding-top: 4px;">
              <span>Surplus Margin: <b style="color: #10b981;">$${d.margin.toFixed(2)}</b></span>
              <span style="color: #38bdf8; font-weight: 600;">Inspect Agent ▾</span>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // Render Agent Selector Strip (50 agents)
  renderAgentSelectorChips(agents);

  // If inspector is expanded, refresh its details
  if (isInspectorExpanded) {
    if (!selectedAgentId && decisions.length > 0) {
      selectedAgentId = decisions[0].agent_id;
    }
    renderAgentInspectorDetails(data);
  }
}

function renderAgentSelectorChips(agents) {
  const container = document.getElementById('agentSelectorChips');
  if (!container) return;
  if (!agents || agents.length === 0) {
    container.innerHTML = '<span style="color: #64748b; font-size: 0.72rem;">No agents active</span>';
    return;
  }
  container.innerHTML = agents.map(a => {
    const isBuyer = a.role === 'Buyer';
    const isSelected = String(selectedAgentId) === String(a.agent_id);
    const baseColor = isBuyer ? '#10b981' : '#ef4444';
    const bg = isSelected ? (isBuyer ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)') : (a.done ? '#1e293b' : '#0f172a');
    const border = isSelected ? baseColor : (a.done ? '#334155' : (isBuyer ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)'));
    const text = a.done ? '#64748b' : '#f1f5f9';
    const prefix = isBuyer ? 'B' : 'S';

    return `
      <button onclick="selectAgentToInspect('${a.agent_id}')" style="
        background: ${bg};
        border: 1px solid ${border};
        color: ${text};
        padding: 2px 7px;
        border-radius: 4px;
        font-size: 0.7rem;
        cursor: pointer;
        white-space: nowrap;
        font-family: monospace;
      " title="${a.role} #${a.agent_id} • ${isBuyer ? 'Valuation' : 'Cost'} $${a.val.toFixed(2)}${a.done ? ' (Trade Completed)' : ''}">
        ${prefix}${a.agent_id}${a.done ? '✓' : ''}
      </button>
    `;
  }).join('');
}

function selectAgentToInspect(agentId) {
  selectedAgentId = agentId;
  toggleInspectorCollapse(true);
  if (currentData) {
    renderJevDecisions(currentData);
  }
}

function renderAgentInspectorDetails(data) {
  const card = document.getElementById('agentInspectorCard');
  const badge = document.getElementById('selectedAgentBadge');
  if (!card) return;

  if (!selectedAgentId) {
    if (badge) badge.innerText = 'Select an Agent';
    card.innerHTML = '<div style="color: #94a3b8; text-align: center; padding: 25px;">Click any decision above or agent chip to inspect agent state and quotes.</div>';
    return;
  }

  const isJev = data.trader_type === 'jev';
  const agents = data.jev_agents || [];
  const agent = agents.find(a => String(a.agent_id) === String(selectedAgentId));
  const decisions = data.jev_decisions || [];
  const lastDec = decisions.find(d => String(d.agent_id) === String(selectedAgentId)) || (agent ? agent.profile : null);

  const isBuyer = agent ? agent.role === 'Buyer' : (lastDec ? lastDec.role === 'Buyer' : true);
  const roleName = isBuyer ? 'Buyer' : 'Seller';
  const roleColor = isBuyer ? '#10b981' : '#ef4444';
  const valCost = agent ? agent.val : (lastDec ? lastDec.val : 0);
  const isDone = agent ? agent.done : false;

  if (badge) {
    badge.innerText = `${roleName} #${selectedAgentId}`;
    badge.style.background = isBuyer ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)';
    badge.style.color = roleColor;
  }

  if (!lastDec) {
    card.innerHTML = `
      <div style="padding: 10px;">
        <div style="font-weight: 700; color: #fff; font-size: 0.85rem; margin-bottom: 6px;">${roleName} #${selectedAgentId}</div>
        <div style="color: #94a3b8; margin-bottom: 4px;">Private ${isBuyer ? 'Valuation' : 'Cost'}: <b style="color: #fff;">$${valCost.toFixed(2)}</b></div>
        <div style="color: #94a3b8; margin-bottom: 8px;">Status: <b style="color: ${isDone ? '#34d399' : '#38bdf8'};">${isDone ? 'Trade Completed' : 'Pending Arrival'}</b></div>
        <div style="font-style: italic; color: #64748b;">Waiting for Poisson arrival event to generate market quote.</div>
      </div>
    `;
    return;
  }

  const scorePct = Math.min(100, Math.max(0, ((lastDec.score || 0) / 4.0) * 100));
  const scoreColor = lastDec.score >= 3.0 ? '#c084fc' : (lastDec.score >= 2.0 ? '#38bdf8' : (lastDec.score >= 1.0 ? '#f59e0b' : '#64748b'));

  if (isJev) {
    card.innerHTML = `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
        <!-- Column 1: Last Decision & Reasoning -->
        <div style="background: #0f172a; padding: 10px 12px; border-radius: 5px; border: 1px solid #1e293b;">
          <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #26334d; padding-bottom: 6px; margin-bottom: 6px;">
            <div>
              <span style="font-weight: 800; font-size: 0.86rem; color: ${roleColor};">${roleName} #${selectedAgentId}</span>
              <span style="color: #94a3b8; font-size: 0.72rem; margin-left: 6px;">Private ${isBuyer ? 'Val' : 'Cost'}: <b style="color: #fff;">$${valCost.toFixed(2)}</b></span>
            </div>
            <span class="badge" style="background: ${isDone ? 'rgba(16, 185, 129, 0.2)' : 'rgba(56, 189, 248, 0.2)'}; color: ${isDone ? '#34d399' : '#38bdf8'};">
              ${isDone ? '✓ Filled' : 'Active Trader'}
            </span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span style="color: #94a3b8; font-size: 0.68rem; text-transform: uppercase;">Cognitive Decision:</span>
            <span style="color: #38bdf8; font-size: 0.72rem; font-weight: 600;">Stochastic <b style="color: #22d3ee;">Choice()</b></span>
          </div>
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
            <div style="flex: 1; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden;">
              <div style="width: ${scorePct}%; height: 100%; background: ${scoreColor};"></div>
            </div>
            <span style="font-size: 0.75rem; font-weight: 700; color: #fff;">${lastDec.tactic}</span>
          </div>
          <div style="font-size: 0.72rem; color: #cbd5e1; line-height: 1.35; margin-bottom: 6px;">
            ${lastDec.reasoning || 'Calibrated economic placement.'}
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: #94a3b8; border-top: 1px dashed #26334d; padding-top: 4px;">
            <span>Submitted ${isBuyer ? 'Bid' : 'Ask'}: <b style="color: #fff;">$${lastDec.submitted_price.toFixed(2)}</b></span>
            <span>Surplus Margin: <b style="color: #10b981;">$${lastDec.margin.toFixed(2)}</b></span>
          </div>
        </div>

        <!-- Column 2: System One Frame & TypeSafe Prompt -->
        <div style="background: #0b0f19; padding: 10px 12px; border-radius: 5px; border: 1px solid #1e293b; font-size: 0.7rem; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="color: #94a3b8; font-weight: 700; font-size: 0.68rem; text-transform: uppercase; margin-bottom: 4px;">
              TypeSafe System One Specification
            </div>
            <div style="color: #38bdf8; font-family: monospace; font-size: 0.68rem; margin-bottom: 4px;">
              Choice(options=["spread_crosser", "queue_competitor", "patient_maker", "deep_discount"])
            </div>
            <div style="color: #94a3b8; font-size: 0.68rem; line-height: 1.35;">
              <div>• <b>State:</b> {val: $${valCost.toFixed(2)}, bid: ${lastDec.best_bid !== null ? '$' + lastDec.best_bid.toFixed(2) : 'null'}, ask: ${lastDec.best_ask !== null ? '$' + lastDec.best_ask.toFixed(2) : 'null'}}</div>
              <div>• <b>Guard:</b> ${isBuyer ? 'Bid <= Valuation' : 'Ask >= Cost'} (Surplus >= 0 guaranteed)</div>
              <div>• <b>Tokens:</b> ${lastDec.tokens} tok (${lastDec.decision_type})</div>
            </div>
          </div>
          <div style="font-size: 0.68rem; color: #64748b; border-top: 1px dashed #26334d; padding-top: 4px; margin-top: 4px;">
            Decisions are cached across unchanged order book states via delta caching.
          </div>
        </div>
      </div>
    `;
  } else {
    // ZI-C Mode Inspector
    const sys = lastDec.system_one || {};
    card.innerHTML = `
      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px;">
        <!-- Column 1: ZI-C Random Draw & Budget Constraint -->
        <div style="background: #0f172a; padding: 10px 12px; border-radius: 5px; border: 1px solid #1e293b;">
          <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #26334d; padding-bottom: 6px; margin-bottom: 6px;">
            <div>
              <span style="font-weight: 800; font-size: 0.86rem; color: ${roleColor};">${roleName} #${selectedAgentId}</span>
              <span style="color: #94a3b8; font-size: 0.72rem; margin-left: 6px;">Private ${isBuyer ? 'Valuation' : 'Cost'}: <b style="color: #fff;">$${valCost.toFixed(2)}</b></span>
            </div>
            <span class="badge" style="background: ${isDone ? 'rgba(16, 185, 129, 0.2)' : 'rgba(168, 85, 247, 0.2)'}; color: ${isDone ? '#34d399' : '#c084fc'};">
              ${isDone ? '✓ Filled' : 'Active Trader'}
            </span>
          </div>
          <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
            <span style="color: #94a3b8; font-size: 0.68rem; text-transform: uppercase;">Heuristic Draw:</span>
            <span style="color: #c084fc; font-size: 0.72rem; font-weight: 600;">Draw Ratio: <b>${scorePct.toFixed(1)}%</b></span>
          </div>
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
            <div style="flex: 1; height: 6px; background: #1e293b; border-radius: 3px; overflow: hidden;">
              <div style="width: ${scorePct}%; height: 100%; background: ${scoreColor};"></div>
            </div>
            <span style="font-size: 0.75rem; font-weight: 700; color: #fff;">${lastDec.tactic}</span>
          </div>
          <div style="font-size: 0.72rem; color: #cbd5e1; line-height: 1.35; margin-bottom: 6px;">
            ${lastDec.reasoning || 'Budget-constrained uniform random draw.'}
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: #94a3b8; border-top: 1px dashed #26334d; padding-top: 4px;">
            <span>Submitted ${isBuyer ? 'Bid' : 'Ask'}: <b style="color: #fff;">$${lastDec.submitted_price.toFixed(2)}</b></span>
            <span>Surplus Margin: <b style="color: #10b981;">$${lastDec.margin.toFixed(2)}</b></span>
          </div>
        </div>

        <!-- Column 2: Canonical Model Framing -->
        <div style="background: #0b0f19; padding: 10px 12px; border-radius: 5px; border: 1px solid #1e293b; font-size: 0.7rem; display: flex; flex-direction: column; justify-content: space-between;">
          <div>
            <div style="color: #94a3b8; font-weight: 700; font-size: 0.68rem; text-transform: uppercase; margin-bottom: 4px;">
              Gode & Sunder (1993) Specification
            </div>
            <div style="color: #c084fc; font-family: monospace; font-size: 0.68rem; margin-bottom: 4px;">
              ${sys.theory || 'Zero-Intelligence Constrained (ZI-C)'}
            </div>
            <div style="color: #94a3b8; font-size: 0.68rem; line-height: 1.35;">
              <div>• <b>Budget Constraint:</b> <span style="color: #10b981;">${sys.budget_constraint || (isBuyer ? 'P <= Val' : 'P >= Cost')}</span></div>
              <div>• <b>Draw Range:</b> ${sys.draw_range || 'Uniform'}</div>
              <div>• <b>Intelligence:</b> Zero (no learning, no memory, no tactical optimization)</div>
              <div>• <b>Tokens Used:</b> 0 tokens (pure random number generator)</div>
            </div>
          </div>
          <div style="font-size: 0.68rem; color: #64748b; border-top: 1px dashed #26334d; padding-top: 4px; margin-top: 4px;">
            Gode & Sunder demonstrated market institutions extract ~99% allocative efficiency even from zero-intelligence traders.
          </div>
        </div>
      </div>
    `;
  }
}

function drawFlippedOrderBook(data) {
  const canvas = document.getElementById('obCanvas');
  const { ctx, w, h } = setupCanvas(canvas);

  const bids = data.all_bids;
  const asks = data.all_asks;
  const maxP = eqData ? Math.max(...eqData.demand, ...eqData.supply, 100) : 100;
  const maxQ = Math.max(bids.length, asks.length, 8);

  const pad = { top: 22, right: 30, bottom: 30, left: 45 };
  const plotW = w - pad.left - pad.right;
  const plotH = h - pad.top - pad.bottom;

  const pToX = p => pad.left + (p / maxP) * plotW;
  const qToY = q => pad.top + plotH - (q / maxQ) * plotH;

  // Grid
  ctx.strokeStyle = '#1e293b';
  ctx.lineWidth = 1;
  ctx.beginPath();
  const qStep = Math.max(1, Math.ceil(maxQ / 5));
  for (let q = 0; q <= maxQ; q += qStep) {
    const y = qToY(q);
    ctx.moveTo(pad.left, y);
    ctx.lineTo(pad.left + plotW, y);
  }
  for (let p = 0; p <= maxP; p += 25) {
    const x = pToX(p);
    ctx.moveTo(x, pad.top);
    ctx.lineTo(x, pad.top + plotH);
  }
  ctx.stroke();

  // Axes
  ctx.strokeStyle = '#334155';
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, pad.top + plotH);
  ctx.lineTo(pad.left + plotW, pad.top + plotH);
  ctx.stroke();

  // Labels
  ctx.fillStyle = '#94a3b8';
  ctx.font = '10px sans-serif';
  ctx.fillText('0', pad.left - 14, pad.top + plotH + 4);
  ctx.fillText(`Q=${maxQ}`, pad.left - 30, pad.top + 10);
  ctx.fillText('$0', pad.left - 6, pad.top + plotH + 18);
  ctx.fillText('$' + maxP, pad.left + plotW - 14, pad.top + plotH + 18);
  ctx.fillText('Price ($)', pad.left + plotW / 2 - 20, pad.top + plotH + 18);

  // Theoretical Equilibrium Price Line
  if (eqData && eqData.eq_price !== null) {
    const eqX = pToX(eqData.eq_price);
    ctx.strokeStyle = '#a855f7';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(eqX, pad.top);
    ctx.lineTo(eqX, pad.top + plotH);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = '#a855f7';
    ctx.fillText(`P* = $${eqData.eq_price.toFixed(1)}`, eqX + 6, pad.top + 14);
  }

  // 1. ACCUMULATED BIDS (steps upwards to left)
  if (bids.length > 0) {
    ctx.strokeStyle = '#10b981';
    ctx.fillStyle = 'rgba(16, 185, 129, 0.18)';
    ctx.lineWidth = 2.5;

    ctx.beginPath();
    const bbX = pToX(bids[0].price);
    const bbY = qToY(1);
    ctx.moveTo(bbX, pad.top + plotH);
    ctx.lineTo(bbX, bbY);

    bids.forEach((b, i) => {
      const x = pToX(b.price);
      const y = qToY(i + 1);
      ctx.lineTo(x, y);
      if (i < bids.length - 1) {
        const nextX = pToX(bids[i + 1].price);
        ctx.lineTo(nextX, y);
      }
    });

    const lastY = qToY(bids.length);
    ctx.lineTo(pad.left, lastY);
    ctx.lineTo(pad.left, pad.top + plotH);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#10b981';
    ctx.beginPath();
    ctx.arc(bbX, bbY, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillText(`Best Bid $${bids[0].price.toFixed(1)}`, bbX - 75, bbY - 6);
  }

  // 2. ACCUMULATED ASKS (steps upwards to right)
  if (asks.length > 0) {
    ctx.strokeStyle = '#ef4444';
    ctx.fillStyle = 'rgba(239, 68, 68, 0.18)';
    ctx.lineWidth = 2.5;

    ctx.beginPath();
    const baX = pToX(asks[0].price);
    const baY = qToY(1);
    ctx.moveTo(baX, pad.top + plotH);
    ctx.lineTo(baX, baY);

    asks.forEach((a, i) => {
      const x = pToX(a.price);
      const y = qToY(i + 1);
      ctx.lineTo(x, y);
      if (i < asks.length - 1) {
        const nextX = pToX(asks[i + 1].price);
        ctx.lineTo(nextX, y);
      }
    });

    const lastY = qToY(asks.length);
    ctx.lineTo(pad.left + plotW, lastY);
    ctx.lineTo(pad.left + plotW, pad.top + plotH);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();

    ctx.fillStyle = '#ef4444';
    ctx.beginPath();
    ctx.arc(baX, baY, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillText(`Best Ask $${asks[0].price.toFixed(1)}`, baX + 8, baY - 6);
  }

  // 3. SPREAD GAP
  if (bids.length > 0 && asks.length > 0) {
    const bbX = pToX(bids[0].price);
    const baX = pToX(asks[0].price);
    const spreadY = qToY(1);

    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 2;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(bbX, spreadY);
    ctx.lineTo(baX, spreadY);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = 'rgba(245, 158, 11, 0.08)';
    ctx.fillRect(bbX, pad.top, Math.max(1, baX - bbX), plotH);

    const midX = (bbX + baX) / 2;
    ctx.fillStyle = '#f59e0b';
    ctx.font = '11px sans-serif';
    ctx.fillText(`Spread: $${(asks[0].price - bids[0].price).toFixed(2)}`, midX - 35, spreadY - 8);
  }
}

function drawSDChart() {
  const canvas = document.getElementById('sdCanvas');
  const { ctx, w, h } = setupCanvas(canvas);

  if (!eqData) return;
  const pad = { top: 16, right: 16, bottom: 25, left: 35 };
  const plotW = w - pad.left - pad.right;
  const plotH = h - pad.top - pad.bottom;

  const maxQ = Math.max(eqData.demand.length, eqData.supply.length, 10);
  const maxP = Math.max(...eqData.demand, ...eqData.supply, 100);

  const xToPx = q => pad.left + (q / maxQ) * plotW;
  const yToPx = p => pad.top + plotH - (p / maxP) * plotH;

  ctx.strokeStyle = '#1e293b';
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let p = 0; p <= maxP; p += 25) {
    const y = yToPx(p);
    ctx.moveTo(pad.left, y);
    ctx.lineTo(pad.left + plotW, y);
  }
  ctx.stroke();

  ctx.strokeStyle = '#334155';
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, pad.top + plotH);
  ctx.lineTo(pad.left + plotW, pad.top + plotH);
  ctx.stroke();

  ctx.fillStyle = '#94a3b8';
  ctx.font = '10px sans-serif';
  ctx.fillText('0', pad.left - 12, pad.top + plotH + 4);
  ctx.fillText(maxP.toString(), pad.left - 24, pad.top + 8);
  ctx.fillText(`Q=${maxQ}`, pad.left + plotW - 25, pad.top + plotH + 16);

  // Demand
  ctx.strokeStyle = '#3b82f6';
  ctx.lineWidth = 2;
  ctx.beginPath();
  eqData.demand.forEach((d, i) => {
    const x1 = xToPx(i);
    const x2 = xToPx(i + 1);
    const y = yToPx(d);
    if (i === 0) ctx.moveTo(x1, y);
    else ctx.lineTo(x1, y);
    ctx.lineTo(x2, y);
  });
  ctx.stroke();

  // Supply
  ctx.strokeStyle = '#ef4444';
  ctx.lineWidth = 2;
  ctx.beginPath();
  eqData.supply.forEach((s, i) => {
    const x1 = xToPx(i);
    const x2 = xToPx(i + 1);
    const y = yToPx(s);
    if (i === 0) ctx.moveTo(x1, y);
    else ctx.lineTo(x1, y);
    ctx.lineTo(x2, y);
  });
  ctx.stroke();

  if (eqData.eq_price !== null && eqData.eq_qty > 0) {
    const eqX = xToPx(eqData.eq_qty);
    const eqY = yToPx(eqData.eq_price);

    ctx.strokeStyle = '#a855f7';
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(pad.left, eqY);
    ctx.lineTo(pad.left + plotW, eqY);
    ctx.moveTo(eqX, pad.top);
    ctx.lineTo(eqX, pad.top + plotH);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = '#a855f7';
    ctx.beginPath();
    ctx.arc(eqX, eqY, 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillText(`P* = $${eqData.eq_price.toFixed(1)}`, eqX + 6, eqY - 4);
  }
}

function drawPriceChart(trades, currentTime, stats) {
  const canvas = document.getElementById('priceCanvas');
  const { ctx, w, h } = setupCanvas(canvas);

  const pad = { top: 16, right: 16, bottom: 25, left: 35 };
  const plotW = w - pad.left - pad.right;
  const plotH = h - pad.top - pad.bottom;

  const maxT = Math.max(currentTime, 30);
  const maxP = eqData ? Math.max(...eqData.demand, 100) : 100;

  const xToPx = t => pad.left + (t / maxT) * plotW;
  const yToPx = p => pad.top + plotH - (p / maxP) * plotH;

  // Grid
  ctx.strokeStyle = '#1e293b';
  ctx.lineWidth = 1;
  ctx.beginPath();
  for (let p = 0; p <= maxP; p += 25) {
    const y = yToPx(p);
    ctx.moveTo(pad.left, y);
    ctx.lineTo(pad.left + plotW, y);
  }
  ctx.stroke();

  // Axes
  ctx.strokeStyle = '#334155';
  ctx.beginPath();
  ctx.moveTo(pad.left, pad.top);
  ctx.lineTo(pad.left, pad.top + plotH);
  ctx.lineTo(pad.left + plotW, pad.top + plotH);
  ctx.stroke();

  // 1. Theoretical Equilibrium Line and Dispersion Band
  if (eqData && eqData.eq_price !== null) {
    const eqY = yToPx(eqData.eq_price);

    // If we have dispersion (std dev), draw the ±1 sigma corridor around equilibrium!
    if (stats && stats.std_dev !== null && stats.std_dev > 0) {
      const topSigmaY = yToPx(Math.min(maxP, eqData.eq_price + stats.std_dev));
      const botSigmaY = yToPx(Math.max(0, eqData.eq_price - stats.std_dev));

      ctx.fillStyle = 'rgba(168, 85, 247, 0.08)';
      ctx.fillRect(pad.left, topSigmaY, plotW, botSigmaY - topSigmaY);
    }

    ctx.strokeStyle = '#a855f7';
    ctx.lineWidth = 1.5;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(pad.left, eqY);
    ctx.lineTo(pad.left + plotW, eqY);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = '#a855f7';
    ctx.font = '10px sans-serif';
    ctx.fillText(`P* ($${eqData.eq_price.toFixed(1)})`, pad.left + 6, eqY - 4);
  }

  // 2. Running Mean Price Line (Cyan solid line)
  if (trades.length > 0) {
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 2;
    ctx.beginPath();
    let cumSum = 0;
    trades.forEach((t, i) => {
      cumSum += t.price;
      const runningMean = cumSum / (i + 1);
      const x = xToPx(t.time);
      const y = yToPx(runningMean);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // 3. Individual Executed Trades (Green dots)
    ctx.fillStyle = '#10b981';
    trades.forEach(t => {
      const x = xToPx(t.time);
      const y = yToPx(t.price);
      ctx.beginPath();
      ctx.arc(x, y, 3, 0, Math.PI * 2);
      ctx.fill();
    });
  }

  ctx.fillStyle = '#94a3b8';
  ctx.font = '10px sans-serif';
  ctx.fillText('0', pad.left - 12, pad.top + plotH + 4);
  ctx.fillText(`t=${currentTime.toFixed(1)}s`, pad.left + plotW - 40, pad.top + plotH + 16);
}

// Initial fetch
fetchState();
</script>

</body>
</html>
"""


class AuctionServer:
    def __init__(self):
        initial_type = "jev" if os.environ.get("TYPESAFE_API_KEY") else "zi"
        self.trader_type = initial_type
        buyer_cls = JevBuyer if initial_type == "jev" else Buyer
        seller_cls = JevSeller if initial_type == "jev" else Seller
        self.model = DoubleAuctionModel(
            n_buyers=25,
            n_sellers=25,
            max_valuation=100.0,
            rng=42,
            buyer_cls=buyer_cls,
            seller_cls=seller_cls,
        )
        self.steps_taken = 0
        self.trade_records = []
        self.stop_requested = False
        self.max_steps = 50

    def reset(self, n_buyers=25, n_sellers=25, max_valuation=100.0, mean_interarrival=1.0, rng=None, trader_type="zi", max_steps=50):
        self.trader_type = trader_type
        self.steps_taken = 0
        self.trade_records = []
        self.stop_requested = False
        self.max_steps = max_steps

        if trader_type == "jev":
            buyer_cls = JevBuyer
            seller_cls = JevSeller
            JevTrader.reset_telemetry()
        else:
            buyer_cls = Buyer
            seller_cls = Seller
            Trader.reset_telemetry()

        self.model = DoubleAuctionModel(
            n_buyers=n_buyers,
            n_sellers=n_sellers,
            max_valuation=max_valuation,
            mean_interarrival=mean_interarrival,
            rng=rng,
            buyer_cls=buyer_cls,
            seller_cls=seller_cls,
        )

    def stop(self):
        """Immediately halt any active simulation step."""
        self.stop_requested = True
        JevTrader.stop_requested = True
        return {"status": "stopped", "steps_taken": self.steps_taken}

    def _calculate_trade_records(self):
        """Construct detailed trade records with realized economic surplus."""
        agents_by_id = {a.unique_id: a for a in self.model.agents}
        records = []
        for o in self.model.order_book.bids:
            pass  # book inspections
        # Build from model price history and completed traders
        # For precision, compute total realized surplus from completed agents:
        buyers_done = [a for a in self.model.agents if isinstance(a, self.model.buyer_cls) and a.done_trading]
        sellers_done = [a for a in self.model.agents if isinstance(a, self.model.seller_cls) and a.done_trading]

        # In price history (time, price)
        for i, (t, p) in enumerate(self.model.price_history):
            b_agent = buyers_done[i] if i < len(buyers_done) else None
            s_agent = sellers_done[i] if i < len(sellers_done) else None
            b_val = b_agent.private_value if b_agent else p
            s_cost = s_agent.private_value if s_agent else p
            surplus = b_val - s_cost

            records.append({
                "time": round(t, 2),
                "price": round(p, 2),
                "buyer_id": b_agent.unique_id if b_agent else None,
                "seller_id": s_agent.unique_id if s_agent else None,
                "buyer_val": round(b_val, 2),
                "seller_cost": round(s_cost, 2),
                "surplus": round(surplus, 2),
            })
        return records

    def get_state(self):
        m = self.model
        bb = m.order_book.best_bid()
        ba = m.order_book.best_ask()

        all_bids = [
            {"agent_id": o.agent_id, "price": round(o.price, 2), "time": round(o.timestamp, 2)}
            for o in sorted(m.order_book.bids, key=lambda x: -x.price)
        ]
        all_asks = [
            {"agent_id": o.agent_id, "price": round(o.price, 2), "time": round(o.timestamp, 2)}
            for o in sorted(m.order_book.asks, key=lambda x: x.price)
        ]

        buyers = [a for a in m.agents if isinstance(a, m.buyer_cls)]
        sellers = [a for a in m.agents if isinstance(a, m.seller_cls)]
        demand = sorted([round(b.private_value, 2) for b in buyers], reverse=True)
        supply = sorted([round(s.private_value, 2) for s in sellers])

        eq_qty = 0
        for q in range(1, min(len(demand), len(supply)) + 1):
            if demand[q - 1] >= supply[q - 1]:
                eq_qty = q
            else:
                break
        eq_price = round((demand[eq_qty - 1] + supply[eq_qty - 1]) / 2.0, 2) if eq_qty > 0 else None
        max_surplus = round(sum(demand[q] - supply[q] for q in range(eq_qty)), 2) if eq_qty > 0 else 0.0

        buyers_done = [a for a in buyers if a.done_trading]
        sellers_done = [a for a in sellers if a.done_trading]

        # Canonical Gode & Sunder Precision Metrics
        prices = [p for _, p in m.price_history]
        n_trades = len(prices)

        if n_trades > 0:
            mean_price = round(sum(prices) / n_trades, 2)
            std_dev = round(math.sqrt(sum((p - mean_price) ** 2 for p in prices) / n_trades), 2)
            rmse_from_eq = (
                round(math.sqrt(sum((p - eq_price) ** 2 for p in prices) / n_trades), 2)
                if eq_price is not None
                else None
            )
        else:
            mean_price = None
            std_dev = None
            rmse_from_eq = None

        quote_mid = (
            round((bb.price + ba.price) / 2.0, 2)
            if (bb and ba)
            else None
        )

        realized_surplus = round(sum(b.private_value for b in buyers_done) - sum(s.private_value for s in sellers_done), 2)
        allocative_efficiency = (
            round((realized_surplus / max_surplus) * 100.0, 1)
            if max_surplus > 0
            else (100.0 if n_trades > 0 else 0.0)
        )

        records = self._calculate_trade_records()

        if self.trader_type == "jev":
            decisions = list(reversed(JevTrader.recent_decisions[-40:]))
            profiles = JevTrader.agent_profiles
        else:
            decisions = list(reversed(Trader.recent_decisions[-40:]))
            profiles = Trader.agent_profiles

        agent_list = [
            {
                "agent_id": a.unique_id,
                "role": "Buyer" if isinstance(a, self.model.buyer_cls) else "Seller",
                "val": round(a.private_value, 2),
                "done": a.done_trading,
                "profile": profiles.get(a.unique_id),
            }
            for a in self.model.agents
        ]

        return {
            "time": m.time,
            "steps_taken": self.steps_taken,
            "max_steps": self.max_steps,
            "is_max_steps_reached": self.steps_taken >= self.max_steps,
            "clearing_price": m.clearing_price,
            "cumulative_volume": m.cumulative_volume,
            "spread": m.order_book.spread(),
            "best_bid": bb.price if bb else None,
            "best_ask": ba.price if ba else None,
            "bids": all_bids[:10],
            "asks": all_asks[:10],
            "all_bids": all_bids,
            "all_asks": all_asks,
            "all_trades": [{"time": t, "price": p} for t, p in m.price_history],
            "trade_records": records,
            "buyers_done": len(buyers_done),
            "total_buyers": len(buyers),
            "sellers_done": len(sellers_done),
            "total_sellers": len(sellers),
            "trader_type": self.trader_type,
            "is_equilibrium_reached": m.is_equilibrium_reached,
            "typesafe_telemetry": JevTrader.get_token_telemetry(),
            "jev_decisions": decisions,
            "jev_agents": agent_list,
            "stats": {
                "mean_price": mean_price,
                "quote_midpoint": quote_mid,
                "std_dev": std_dev,
                "rmse_from_eq": rmse_from_eq,
                "realized_surplus": realized_surplus,
                "max_surplus": max_surplus,
                "allocative_efficiency": allocative_efficiency,
            },
            "equilibrium": {
                "demand": demand,
                "supply": supply,
                "eq_qty": eq_qty,
                "eq_price": eq_price,
                "max_surplus": max_surplus,
            },
        }

    def step(self, dt=1.0):
        self.stop_requested = False
        JevTrader.stop_requested = False
        if not self.model.is_equilibrium_reached and self.steps_taken < self.max_steps:
            elapsed = 0.0
            step_chunk = 0.05
            while elapsed < dt and not self.model.is_equilibrium_reached and not self.stop_requested:
                cur_dt = min(step_chunk, dt - elapsed)
                self.model.run_for(cur_dt)
                elapsed += cur_dt
            self.steps_taken += 1
        return self.get_state()


auction_server = AuctionServer()


class RequestHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ["/", "/index.html"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode("utf-8"))
        elif parsed.path in ["/api/state", "/state"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            state = auction_server.get_state()
            self.wfile.write(json.dumps(state).encode("utf-8"))
        elif parsed.path == "/api/test_connection":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            conn = JevTrader.test_connection()
            self.wfile.write(json.dumps(conn).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_len = int(self.headers.get("Content-Length", 0))
        post_body = self.rfile.read(content_len) if content_len > 0 else b"{}"
        try:
            params = json.loads(post_body.decode("utf-8"))
        except Exception:
            params = {}

        if parsed.path == "/api/step":
            dt = float(params.get("dt", 1.0))
            new_state = auction_server.step(dt)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(new_state).encode("utf-8"))
        elif parsed.path == "/api/stop":
            res = auction_server.stop()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        elif parsed.path == "/api/reset":
            auction_server.reset(
                n_buyers=int(params.get("n_buyers", 25)),
                n_sellers=int(params.get("n_sellers", 25)),
                max_valuation=float(params.get("max_valuation", 100.0)),
                mean_interarrival=float(params.get("mean_interarrival", 1.0)),
                rng=params.get("rng"),
                trader_type=params.get("trader_type", "zi"),
                max_steps=int(params.get("max_steps", 50)),
            )
            state = auction_server.get_state()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(state).encode("utf-8"))
        elif parsed.path == "/api/set_api_key":
            api_key = params.get("api_key", "")
            res = JevTrader.set_api_key(api_key)
            if res.get("is_connected"):
                auction_server.reset(trader_type="jev", max_steps=auction_server.max_steps)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(res).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
        host, port = server_address
        if host in ("", "::"):
            self.address_family = socket.AF_INET6
        else:
            self.address_family = socket.AF_INET
        super().__init__(server_address, RequestHandlerClass, bind_and_activate=bind_and_activate)

    def server_bind(self):
        if getattr(self, "address_family", None) == socket.AF_INET6:
            try:
                # Enable dual-stack so Windows handles localhost (::1) and 127.0.0.1 with zero delay
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
            except (AttributeError, OSError):
                pass
        super().server_bind()


def run_server(port=8000):
    try:
        with ThreadedHTTPServer(("", port), RequestHandler) as httpd:
            print(f"Server started at http://localhost:{port} (dual-stack IPv4/IPv6 enabled)", flush=True)
            print("Press Ctrl+C to stop.", flush=True)
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nShutting down server.", flush=True)
    except Exception:
        with ThreadedHTTPServer(("127.0.0.1", port), RequestHandler) as httpd:
            print(f"Server started at http://localhost:{port} (IPv4 fallback)", flush=True)
            httpd.serve_forever()


if __name__ == "__main__":
    run_server()
