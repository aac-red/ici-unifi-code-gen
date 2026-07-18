"""
app.py

Single FastAPI app, deployed as one Vercel Function, handling both
routes for the voucher web app:

    POST /api/generate          -- insert a pending voucher request
    GET  /api/voucher-status    -- poll for the result

Required Vercel environment variables (Project Settings -> Environment Variables):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY   (the "service_role" key -- secret, server-side only)
"""

import os
from typing import Optional, Union

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ICI WiFi Access — Voucher Generator</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600;700&display=swap" rel="stylesheet">
<style>
  :root {
    --radius-lg: 26px;
    --radius-md: 14px;
    --radius-sm: 10px;
    --font-display: 'Space Grotesk', sans-serif;
    --font-body: 'Inter', sans-serif;
    --font-mono: 'IBM Plex Mono', monospace;
  }

  :root, [data-theme="light"] {
    --base: #E6E9E2;
    --shadow-d: #C2C6BC;
    --shadow-l: #FFFFFF;
    --ink: #2B2E27;
    --ink-soft: #686C60;
    --accent: #3D8C5C;
    --accent-l: #4FA872;
    --accent-d: #2E6E46;
    --accent-ink: #F4FBF6;
    --accent-soft: rgba(61, 140, 92, 0.14);
    --error: #A8483A;
    --error-soft: rgba(168, 72, 58, 0.12);
    --hairline: rgba(43, 46, 39, 0.08);
  }

  [data-theme="dark"] {
    --base: #2A2F3A;
    --shadow-d: #1D2129;
    --shadow-l: #383F4C;
    --ink: #E9ECF2;
    --ink-soft: #9BA1B0;
    --accent: #4FA872;
    --accent-l: #62BF87;
    --accent-d: #3D8C5C;
    --accent-ink: #0E1D15;
    --accent-soft: rgba(79, 168, 114, 0.18);
    --error: #DB8375;
    --error-soft: rgba(219, 131, 117, 0.15);
    --hairline: rgba(255, 255, 255, 0.07);
  }

  * { box-sizing: border-box; }

  body {
    margin: 0;
    min-height: 100vh;
    background: var(--base);
    font-family: var(--font-body);
    color: var(--ink);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 32px 16px;
    transition: background 0.3s ease, color 0.3s ease;
  }

  .page { width: 100%; max-width: 460px; }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 22px;
  }

  .eyebrow {
    font-family: var(--font-mono);
    font-size: 11.5px;
    font-weight: 600;
    letter-spacing: 0.13em;
    text-transform: uppercase;
    color: var(--accent);
    display: flex;
    align-items: center;
    gap: 7px;
  }

  .eyebrow .dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 0 0 var(--accent-soft);
    animation: pulse 2.4s infinite;
  }

  @keyframes pulse {
    0%   { box-shadow: 0 0 0 0 var(--accent-soft); }
    70%  { box-shadow: 0 0 0 7px transparent; }
    100% { box-shadow: 0 0 0 0 transparent; }
  }

  /* --- Theme switch --- */
  .theme-switch { position: relative; display: inline-block; width: 52px; height: 30px; }
  .theme-switch input { position: absolute; opacity: 0; width: 100%; height: 100%; margin: 0; cursor: pointer; }

  .switch-track {
    position: absolute; inset: 0;
    background: var(--base);
    border-radius: 999px;
    box-shadow: inset 3px 3px 6px var(--shadow-d), inset -3px -3px 6px var(--shadow-l);
    transition: background 0.3s ease;
  }

  .switch-knob {
    position: absolute;
    top: 3px; left: 3px;
    width: 24px; height: 24px;
    border-radius: 50%;
    background: var(--base);
    box-shadow: 3px 3px 6px var(--shadow-d), -3px -3px 6px var(--shadow-l);
    display: flex; align-items: center; justify-content: center;
    font-size: 11px;
    transition: transform 0.28s cubic-bezier(0.65, 0, 0.35, 1);
  }

  .theme-switch input:checked ~ .switch-knob { transform: translateX(22px); }

  .theme-switch input:focus-visible ~ .switch-track {
    box-shadow: inset 3px 3px 6px var(--shadow-d), inset -3px -3px 6px var(--shadow-l), 0 0 0 3px var(--accent-soft);
  }

  h1 {
    font-family: var(--font-display);
    font-weight: 700;
    font-size: clamp(23px, 5vw, 28px);
    line-height: 1.15;
    text-align: center;
    margin: 4px 0 6px;
  }

  .subhead {
    text-align: center;
    color: var(--ink-soft);
    font-size: 13.5px;
    margin: 0 0 26px;
  }

  .panel {
    background: var(--base);
    border-radius: var(--radius-lg);
    padding: 28px 26px;
    box-shadow: 12px 12px 24px var(--shadow-d), -12px -12px 24px var(--shadow-l);
    transition: background 0.3s ease;
  }

  .field { margin-bottom: 16px; }
  .field:last-child { margin-bottom: 0; }

  label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.02em;
    color: var(--ink-soft);
    text-transform: uppercase;
    margin-bottom: 8px;
  }

  .hint { font-size: 11.5px; color: var(--ink-soft); margin-top: 6px; opacity: 0.85; }

  input[type="text"], input[type="number"], select {
    width: 100%;
    font-family: var(--font-body);
    font-size: 15px;
    color: var(--ink);
    background: var(--base);
    border: none;
    border-radius: var(--radius-sm);
    padding: 11px 13px;
    box-shadow: inset 4px 4px 8px var(--shadow-d), inset -4px -4px 8px var(--shadow-l);
    transition: box-shadow 0.15s ease;
  }

  input::placeholder { color: var(--ink-soft); opacity: 0.6; }

  input:focus-visible, select:focus-visible, button:focus-visible, summary:focus-visible {
    outline: none;
    box-shadow: inset 4px 4px 8px var(--shadow-d), inset -4px -4px 8px var(--shadow-l), 0 0 0 3px var(--accent-soft);
  }

  .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }

  .quota-row { display: grid; grid-template-columns: 1fr 84px; gap: 8px; }
  .quota-row.is-unlimited input, .quota-row.is-unlimited select { opacity: 0.4; pointer-events: none; }

  .checkline {
    display: flex; align-items: center; gap: 8px;
    margin-top: 10px; font-size: 13px; color: var(--ink-soft);
  }
  .checkline input {
    width: 15px; height: 15px; accent-color: var(--accent);
    box-shadow: none; padding: 0;
  }
  .checkline label {
    display: inline; text-transform: none; font-weight: 400; margin: 0; color: inherit; font-size: inherit;
  }

  .usage-toggle { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .usage-toggle input { position: absolute; opacity: 0; pointer-events: none; }

  .usage-toggle label.opt {
    display: block; text-align: center;
    font-size: 13px; font-weight: 600; text-transform: none; letter-spacing: 0;
    color: var(--ink-soft);
    background: var(--base);
    border-radius: var(--radius-sm);
    padding: 11px 8px;
    cursor: pointer;
    box-shadow: 5px 5px 10px var(--shadow-d), -5px -5px 10px var(--shadow-l);
    transition: all 0.15s ease;
  }

  .usage-toggle input:checked + label.opt {
    color: var(--accent);
    box-shadow: inset 4px 4px 8px var(--shadow-d), inset -4px -4px 8px var(--shadow-l);
  }

  .usage-toggle input:focus-visible + label.opt { box-shadow: 0 0 0 3px var(--accent-soft); }

  details { margin-bottom: 18px; padding-top: 4px; }

  summary {
    cursor: pointer;
    font-size: 12px; font-weight: 600; letter-spacing: 0.02em;
    color: var(--ink-soft); text-transform: uppercase;
    list-style: none;
    display: inline-flex; align-items: center; gap: 7px;
    background: var(--base);
    border-radius: 999px;
    padding: 8px 14px;
    box-shadow: 4px 4px 8px var(--shadow-d), -4px -4px 8px var(--shadow-l);
  }

  summary::-webkit-details-marker { display: none; }
  summary::before { content: '▸'; font-size: 10px; transition: transform 0.15s ease; }
  details[open] summary::before { transform: rotate(90deg); }
  details .row2 { margin-top: 16px; }
  details[open] summary { margin-bottom: 4px; }

  button.generate {
    width: 100%;
    font-family: var(--font-body);
    font-weight: 700;
    font-size: 15px;
    color: var(--accent-ink);
    background: linear-gradient(145deg, var(--accent-l), var(--accent-d));
    border: none;
    border-radius: var(--radius-sm);
    padding: 15px;
    cursor: pointer;
    box-shadow: 6px 6px 14px var(--shadow-d), -6px -6px 14px var(--shadow-l);
    transition: box-shadow 0.12s ease, transform 0.08s ease;
    margin-top: 4px;
  }

  button.generate:active { box-shadow: inset 3px 3px 8px rgba(0,0,0,0.25); transform: scale(0.99); }

  button.generate:disabled {
    background: var(--base);
    color: var(--ink-soft);
    box-shadow: inset 4px 4px 8px var(--shadow-d), inset -4px -4px 8px var(--shadow-l);
    cursor: default;
  }

  .status-line {
    display: none; align-items: center; justify-content: center; gap: 9px;
    font-family: var(--font-mono); font-size: 12.5px; color: var(--ink-soft);
    margin-top: 16px;
  }
  .status-line.visible { display: flex; }

  .spinner {
    width: 13px; height: 13px; border-radius: 50%;
    border: 2px solid var(--shadow-d);
    border-top-color: var(--accent);
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  .error-box {
    display: none; margin-top: 16px;
    background: var(--error-soft);
    border-radius: var(--radius-sm);
    padding: 12px 14px;
    font-size: 13.5px;
    color: var(--error);
    box-shadow: inset 2px 2px 5px rgba(0,0,0,0.06);
  }
  .error-box.visible { display: block; }

  /* --- Ticket / result panel --- */
  .ticket-wrap { display: none; text-align: center; }
  .ticket-wrap.visible { display: block; }

  .ticket .label {
    font-size: 11.5px; font-weight: 600; letter-spacing: 0.13em; text-transform: uppercase;
    color: var(--ink-soft); margin-bottom: 16px;
  }

  .ticket .code {
    font-family: var(--font-mono);
    font-weight: 700;
    font-size: clamp(24px, 8vw, 32px);
    letter-spacing: 0.04em;
    color: var(--accent);
    background: var(--base);
    border-radius: var(--radius-md);
    padding: 16px 10px;
    margin-bottom: 12px;
    box-shadow: inset 5px 5px 10px var(--shadow-d), inset -5px -5px 10px var(--shadow-l);
    word-break: break-all;
  }

  .ticket .meta {
    display: flex; justify-content: center; flex-wrap: wrap; gap: 6px 14px;
    font-size: 12px; color: var(--ink-soft);
    margin: 4px 0 22px;
    font-family: var(--font-mono);
  }

  .ticket-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }

  .btn-secondary {
    font-family: var(--font-body); font-weight: 600; font-size: 13px;
    color: var(--ink);
    background: var(--base);
    border: none;
    border-radius: var(--radius-sm);
    padding: 11px;
    cursor: pointer;
    box-shadow: 5px 5px 10px var(--shadow-d), -5px -5px 10px var(--shadow-l);
    transition: box-shadow 0.12s ease;
  }
  .btn-secondary:active { box-shadow: inset 3px 3px 6px var(--shadow-d), inset -3px -3px 6px var(--shadow-l); }

  .form-wrap.hidden { display: none; }

  .footnote {
    text-align: center; font-size: 11.5px; color: var(--ink-soft);
    margin-top: 18px; opacity: 0.75;
  }

  @media (prefers-reduced-motion: reduce) {
    .eyebrow .dot, .spinner { animation: none; }
    .switch-knob { transition: none; }
  }
</style>
</head>
<body>

<div class="page">
  <div class="topbar">
    <div class="eyebrow"><span class="dot"></span> ICI Network Access Dashboard</div>
    <label class="theme-switch" for="themeToggle" aria-label="Toggle dark mode">
      <input type="checkbox" id="themeToggle">
      <span class="switch-track"></span>
      <span class="switch-knob">🌙</span>
    </label>
  </div>

  <h1>Guest WiFi Access</h1>
  <p class="subhead">Generate a voucher code for a guest in a few seconds.</p>

  <div class="panel">

    <div class="form-wrap" id="formWrap">
      <form id="voucherForm" novalidate>

        <div class="field">
          <label for="name">Requested by / guest name</label>
          <input type="text" id="name" name="name" placeholder="e.g. Front Desk — Room 214" maxlength="200">
        </div>

        <div class="row2">
          <div class="field">
            <label for="qty">Quantity</label>
            <input type="number" id="qty" name="qty" value="1" min="1" max="50" required>
          </div>
          <div class="field">
            <label for="expiration">Valid for</label>
            <select id="expiration" name="expiration">
              <option value="60">1 hour</option>
              <option value="240">4 hours</option>
              <option value="480" selected>8 hours</option>
              <option value="1440">1 day</option>
              <option value="10080">1 week</option>
              <option value="custom">Custom…</option>
            </select>
          </div>
        </div>

        <div class="field" id="customExpirationField" style="display:none;">
          <label for="customExpiration">Custom duration (minutes)</label>
          <input type="number" id="customExpiration" name="customExpiration" min="1" placeholder="e.g. 90">
        </div>

        <div class="field">
          <label>Voucher usage</label>
          <div class="usage-toggle">
            <input type="radio" name="oneTime" id="oneTimeYes" value="yes" checked>
            <label class="opt" for="oneTimeYes">One-time use</label>
            <input type="radio" name="oneTime" id="oneTimeNo" value="no">
            <label class="opt" for="oneTimeNo">Reusable</label>
          </div>
        </div>

        <div class="field">
          <label for="byteQuotaValue">Data quota</label>
          <div class="quota-row" id="quotaRow">
            <input type="number" id="byteQuotaValue" min="0" placeholder="e.g. 3000">
            <select id="byteQuotaUnit">
              <option value="MB" selected>MB</option>
              <option value="GB">GB</option>
            </select>
          </div>
          <div class="checkline">
            <input type="checkbox" id="unlimitedQuota">
            <label for="unlimitedQuota">No data limit</label>
          </div>
        </div>

        <details>
          <summary>Speed limits (optional)</summary>
          <div class="row2">
            <div class="field">
              <label for="downLimit">Download (Kbps)</label>
              <input type="number" id="downLimit" min="0" placeholder="Unlimited">
              <div class="hint">20000 ≈ 20 Mbps</div>
            </div>
            <div class="field">
              <label for="upLimit">Upload (Kbps)</label>
              <input type="number" id="upLimit" min="0" placeholder="Unlimited">
            </div>
          </div>
        </details>

        <button type="submit" class="generate" id="generateBtn">Generate voucher</button>

        <div class="status-line" id="statusLine">
          <span class="spinner"></span>
          <span id="statusText">Sending request…</span>
        </div>

        <div class="error-box" id="errorBox"></div>
      </form>
    </div>

    <div class="ticket-wrap" id="ticketWrap">
      <div class="ticket">
        <div class="label">Voucher ready</div>
        <div id="codesContainer"></div>
        <div class="meta" id="ticketMeta"></div>
        <div class="ticket-actions">
          <button type="button" class="btn-secondary" id="copyBtn">Copy code</button>
          <button type="button" class="btn-secondary" id="resetBtn">Generate another</button>
        </div>
      </div>
    </div>

  </div>

  <p class="footnote">Vouchers are generated live from the network controller — please allow a few seconds.</p>
</div>

<script>
(function () {
  // --- Theme handling ---
  const themeToggle = document.getElementById('themeToggle');
  const knob = document.querySelector('.switch-knob');

  function applyTheme(isDark) {
    document.documentElement.setAttribute('data-theme', isDark ? 'dark' : 'light');
    if (knob) knob.textContent = isDark ? '🌙' : '☀️';
  }

  const stored = localStorage.getItem('voucher-theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initialDark = stored ? stored === 'dark' : prefersDark;
  applyTheme(initialDark);
  themeToggle.checked = initialDark;

  themeToggle.addEventListener('change', () => {
    applyTheme(themeToggle.checked);
    localStorage.setItem('voucher-theme', themeToggle.checked ? 'dark' : 'light');
  });

  // --- Form logic ---
  const form = document.getElementById('voucherForm');
  const formWrap = document.getElementById('formWrap');
  const ticketWrap = document.getElementById('ticketWrap');
  const generateBtn = document.getElementById('generateBtn');
  const statusLine = document.getElementById('statusLine');
  const statusText = document.getElementById('statusText');
  const errorBox = document.getElementById('errorBox');

  const expirationSelect = document.getElementById('expiration');
  const customExpirationField = document.getElementById('customExpirationField');
  const customExpirationInput = document.getElementById('customExpiration');

  const unlimitedCheckbox = document.getElementById('unlimitedQuota');
  const quotaRow = document.getElementById('quotaRow');
  const byteQuotaValue = document.getElementById('byteQuotaValue');
  const byteQuotaUnit = document.getElementById('byteQuotaUnit');

  const copyBtn = document.getElementById('copyBtn');
  const resetBtn = document.getElementById('resetBtn');
  const codesContainer = document.getElementById('codesContainer');
  const ticketMeta = document.getElementById('ticketMeta');

  let pollTimer = null;
  let pollAttempts = 0;
  const MAX_POLL_ATTEMPTS = 30; // ~60s at 2s intervals
  let lastCodes = [];

  expirationSelect.addEventListener('change', () => {
    const isCustom = expirationSelect.value === 'custom';
    customExpirationField.style.display = isCustom ? 'block' : 'none';
    customExpirationInput.required = isCustom;
  });

  unlimitedCheckbox.addEventListener('change', () => {
    quotaRow.classList.toggle('is-unlimited', unlimitedCheckbox.checked);
  });

  function showError(message) {
    errorBox.textContent = message;
    errorBox.classList.add('visible');
  }
  function clearError() {
    errorBox.textContent = '';
    errorBox.classList.remove('visible');
  }
  function setLoading(isLoading, text) {
    generateBtn.disabled = isLoading;
    generateBtn.textContent = isLoading ? 'Generating…' : 'Generate voucher';
    statusLine.classList.toggle('visible', isLoading);
    if (text) statusText.textContent = text;
  }

  function buildPayload() {
    const qty = parseInt(document.getElementById('qty').value, 10);
    if (!qty || qty < 1) throw new Error('Enter a quantity of at least 1.');

    let expirationMinutes;
    if (expirationSelect.value === 'custom') {
      expirationMinutes = parseInt(customExpirationInput.value, 10);
      if (!expirationMinutes || expirationMinutes < 1) {
        throw new Error('Enter a custom duration in minutes.');
      }
    } else {
      expirationMinutes = parseInt(expirationSelect.value, 10);
    }

    let byteQuota;
    if (unlimitedCheckbox.checked) {
      byteQuota = 'unlimited';
    } else {
      const val = byteQuotaValue.value.trim();
      byteQuota = val ? `${val}${byteQuotaUnit.value}` : 'unlimited';
    }

    const downLimit = document.getElementById('downLimit').value;
    const upLimit = document.getElementById('upLimit').value;

    return {
      name: document.getElementById('name').value.trim(),
      qty: qty,
      expiration_minutes: expirationMinutes,
      down_limit_kbps: downLimit ? parseInt(downLimit, 10) : null,
      up_limit_kbps: upLimit ? parseInt(upLimit, 10) : null,
      byte_quota: byteQuota,
      one_time: document.getElementById('oneTimeYes').checked,
    };
  }

  function renderTicket(statusData) {
    const vouchers = (statusData.voucher_data && statusData.voucher_data.length)
      ? statusData.voucher_data
      : (statusData.code ? [{ code: statusData.code }] : []);

    lastCodes = vouchers.map(v => v.code).filter(Boolean);

    codesContainer.innerHTML = '';
    lastCodes.forEach(code => {
      const div = document.createElement('div');
      div.className = 'code';
      div.textContent = code;
      codesContainer.appendChild(div);
    });

    const parts = [];
    if (lastCodes.length > 1) parts.push(`${lastCodes.length} vouchers`);
    if (statusData.completed_at) {
      const t = new Date(statusData.completed_at);
      parts.push(`generated ${t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
    }
    ticketMeta.textContent = parts.join(' · ');

    formWrap.classList.add('hidden');
    ticketWrap.classList.add('visible');
  }

  function stopPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  function pollStatus(requestId) {
    pollAttempts = 0;
    pollTimer = setInterval(async () => {
      pollAttempts++;
      if (pollAttempts > MAX_POLL_ATTEMPTS) {
        stopPolling();
        setLoading(false);
        showError('This is taking longer than expected. The voucher may still complete — try refreshing in a moment, or generate a new one.');
        return;
      }

      try {
        const res = await fetch(`/api/voucher-status?id=${encodeURIComponent(requestId)}`);
        const data = await res.json();

        if (!res.ok) {
          stopPolling();
          setLoading(false);
          showError(data.detail || 'Could not check voucher status.');
          return;
        }

        if (data.status === 'done') {
          stopPolling();
          setLoading(false);
          renderTicket(data);
        } else if (data.status === 'error') {
          stopPolling();
          setLoading(false);
          showError(data.error_message || 'The voucher could not be generated. Please try again.');
        } else {
          statusText.textContent = pollAttempts < 4
            ? 'Talking to the network controller…'
            : 'Still working — this can take a few extra seconds…';
        }
      } catch (err) {
        statusText.textContent = 'Reconnecting…';
      }
    }, 2000);
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearError();

    let payload;
    try {
      payload = buildPayload();
    } catch (err) {
      showError(err.message);
      return;
    }

    setLoading(true, 'Sending request…');

    try {
      const res = await fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await res.json();

      if (!res.ok) {
        setLoading(false);
        const msg = Array.isArray(data.detail)
          ? data.detail.map(d => d.msg).join(', ')
          : (data.detail || 'Could not submit the request.');
        showError(msg);
        return;
      }

      statusText.textContent = 'Generating your voucher…';
      pollStatus(data.request_id);
    } catch (err) {
      setLoading(false);
      showError('Could not reach the server. Check your connection and try again.');
    }
  });

  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(lastCodes.join('\n'));
      copyBtn.textContent = 'Copied!';
      setTimeout(() => { copyBtn.textContent = 'Copy code'; }, 1500);
    } catch (err) {
      copyBtn.textContent = 'Copy failed';
    }
  });

  resetBtn.addEventListener('click', () => {
    stopPolling();
    form.reset();
    quotaRow.classList.remove('is-unlimited');
    customExpirationField.style.display = 'none';
    clearError();
    setLoading(false);
    ticketWrap.classList.remove('visible');
    formWrap.classList.remove('hidden');
  });
})();
</script>

</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
def serve_index():
    return INDEX_HTML

SUPABASE_URL = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")


def require_config():
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise HTTPException(500, "Server misconfigured: missing Supabase env vars")


def write_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY or ''}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def read_headers():
    return {
        "apikey": SUPABASE_SERVICE_KEY or "",
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY or ''}",
    }


class VoucherRequest(BaseModel):
    name: Optional[str] = ""
    qty: int
    expiration_minutes: int
    down_limit_kbps: Optional[int] = None
    up_limit_kbps: Optional[int] = None
    byte_quota: Union[str, int, float]
    one_time: bool


@app.post("/api/generate")
def generate(req: VoucherRequest):
    require_config()

    payload = {
        "name": (req.name or "")[:200],
        "qty": req.qty,
        "expiration_minutes": req.expiration_minutes,
        "down_limit_kbps": req.down_limit_kbps,
        "up_limit_kbps": req.up_limit_kbps,
        "byte_quota": str(req.byte_quota),
        "one_time": req.one_time,
        "status": "pending",
    }

    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/voucher_requests",
            headers=write_headers(),
            json=payload,
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(502, f"Could not reach Supabase: {e}")

    rows = resp.json()
    if not rows:
        raise HTTPException(502, "Insert succeeded but no row was returned")

    return {"request_id": rows[0]["id"]}


@app.get("/api/voucher-status")
def voucher_status(id: str = Query(...)):
    require_config()

    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/voucher_requests",
            headers=read_headers(),
            params={
                "id": f"eq.{id}",
                "select": "status,code,error_message,voucher_data,created_at,completed_at",
            },
            timeout=15,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        raise HTTPException(502, f"Could not reach Supabase: {e}")

    rows = resp.json()
    if not rows:
        raise HTTPException(404, "Request not found")

    return rows[0]
