/**
 * WhatsApp Blast Dashboard — Main JS
 * Vanilla ES6+, no external deps
 */

const API = window.API_BASE ?? '';

/* ─────────────────────────────
   STATE
───────────────────────────── */
const state = {
  session: {
    status: 'stopped',
    raw_status: 'STOPPED',
    connected: false,
    me: null,
  },
  file: null,
  fileHeaders: [],
  fileRows: 0,
  fileSample: {},
  fileData: [],
  recipientColumn: '',
  template: '',
  additionalFields: [],
  delay: {
    typingMin: 3, typingMax: 11,
    durationMin: 10, durationMax: 39,
    sendMin: 1, sendMax: 4,
    batchSize: 10, batchRest: 300,
  },
  pollingStatus: null,
  pollingQr: null,
  blasting: false,
};

/* ─────────────────────────────
   DOM REFS
───────────────────────────── */
const $ = id => document.getElementById(id);
const $$ = sel => document.querySelectorAll(sel);

/* ─────────────────────────────
   TOAST
───────────────────────────── */
function toast(type, title, msg, duration = null) {
  const dur = duration ?? (type === 'error' ? 5000 : 3000);
  const icons = { success: '✅', error: '❌', info: 'ℹ️', warning: '⚠️' };
  const container = $('toast-container');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `
    <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
    <div class="toast-content">
      <div class="toast-title">${title}</div>
      ${msg ? `<div class="toast-msg">${msg}</div>` : ''}
    </div>
    <div class="toast-progress" style="animation-duration:${dur}ms"></div>
  `;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add('removing');
    setTimeout(() => el.remove(), 350);
  }, dur);
}

/* ─────────────────────────────
   API HELPERS
───────────────────────────── */
async function apiFetch(method, path, body = null, isBlob = false) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(API + path, opts);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`HTTP ${res.status}: ${err}`);
  }
  if (isBlob) return res.blob();
  return res.json();
}

async function apiFormFetch(path, formData) {
  const res = await fetch(API + path, { method: 'POST', body: formData });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`HTTP ${res.status}: ${err}`);
  }
  return res.json();
}

/* ─────────────────────────────
   SESSION MANAGEMENT
───────────────────────────── */
async function fetchStatus() {
  try {
    const data = await apiFetch('GET', '/waha/status');
    state.session = data;
    renderSessionUI();
  } catch (e) {
    // silently fail on poll – no toast spam
    console.warn('Status fetch failed:', e.message);
  }
}

function setRecipientColumn(headerName) {
  const value = String(headerName || '').trim();
  if (!value) return;
  state.recipientColumn = value;
  renderRecipientTarget();
  validateForm();
}

async function startSession() {
  const btn = $('btn-start');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Memulai...`;
  try {
    await apiFetch('POST', '/api/sessions/start');
    toast('success', 'Sesi Dimulai', 'Silakan scan QR code jika diminta');
    await fetchStatus();
  } catch (e) {
    toast('error', 'Gagal Memulai Sesi', e.message);
  } finally {
    btn.disabled = false;
    renderSessionUI();
  }
}

async function logoutSession() {
  const btn = $('btn-logout');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Logout...`;
  try {
    await apiFetch('POST', '/api/sessions/logout');
    toast('info', 'Sesi Diakhiri', 'Sesi WhatsApp telah diputus');
    await fetchStatus();
  } catch (e) {
    toast('error', 'Gagal Logout', e.message);
  } finally {
    btn.disabled = false;
    renderSessionUI();
  }
}

async function refreshQr() {
  const btn = $('btn-qr');
  btn.disabled = true;
  btn.innerHTML = `<span class="spinner"></span> Refresh...`;
  try {
    if (state.session && state.session.connected) {
      toast('info', 'Sudah Terhubung', 'Sesi sudah terhubung; tidak perlu QR');
      return;
    }

    const blob = await apiFetch('GET', '/waha/qr?restart=true', null, true);
    displayQr(blob);
    toast('info', 'QR Diperbarui', 'Silakan scan QR terbaru');
  } catch (e) {
    toast('error', 'Gagal Refresh QR', e.message);
  } finally {
    btn.disabled = false;
    renderSessionUI();
  }
}

async function autoFetchQr() {
  if (state.session.connected) return;
  try {
    const blob = await apiFetch('GET', '/waha/qr?restart=false', null, true);
    displayQr(blob);
  } catch (e) {
    // ignore – might not be ready
  }
}

function displayQr(blob) {
  const url = URL.createObjectURL(blob);
  const img = $('qr-img');
  const ph = $('qr-placeholder');
  img.src = url;
  img.classList.remove('hidden');
  ph.classList.add('hidden');
}

/* ─────────────────────────────
   RENDER SESSION UI
───────────────────────────── */
function renderSessionUI() {
  const { status, connected, me } = state.session;

  // Badge
  const badge = $('status-badge');
  const labels = { connected: 'Terhubung', connecting: 'Menghubungkan', stopped: 'Terputus' };
  badge.className = `status-badge ${status}`;
  badge.innerHTML = `<span class="dot"></span>${labels[status] || status}`;

  // User info
  const userInfo = $('user-info');
  if (connected && me) {
    userInfo.classList.remove('hidden');
    const displayName = me.pushName || me.pushname || me.name || '—';
    const phoneNumber = me.formattedNumber || me.phoneNumber || me.number || '';
    const jid = me.id || me.jid || '';
    const isBusiness = typeof me.isBusiness === 'boolean' ? me.isBusiness : null;

    $('user-name').textContent = displayName;
    $('user-number').textContent = phoneNumber ? `Nomor: ${phoneNumber}` : '';
    $('user-id').textContent = jid ? `JID: ${jid}` : '';
    $('user-business').textContent = isBusiness === null ? '' : `Akun: ${isBusiness ? 'Business' : 'Personal'}`;
  } else {
    userInfo.classList.add('hidden');
    $('user-name').textContent = '—';
    $('user-number').textContent = '';
    $('user-id').textContent = '';
    $('user-business').textContent = '';
  }

  // Buttons
  const btnStart  = $('btn-start');
  const btnLogout = $('btn-logout');
  const btnQr     = $('btn-qr');

  // Start: visible if not starting/connected
  if (status === 'stopped') {
    btnStart.classList.remove('hidden');
    btnStart.innerHTML = '▶ Mulai Sesi';
    btnStart.disabled = false;
  } else {
    btnStart.classList.add('hidden');
  }

  // Logout: visible if session has been started (any non-stopped state)
  if (status !== 'stopped') {
    btnLogout.classList.remove('hidden');
    btnLogout.innerHTML = '⏏ Logout Sesi';
    btnLogout.disabled = false;
  } else {
    btnLogout.classList.add('hidden');
  }

  // QR: visible if not connected
  if (!connected) {
    btnQr.classList.remove('hidden');
    btnQr.innerHTML = '↻ Refresh QR';
    btnQr.disabled = false;
  } else {
    btnQr.classList.add('hidden');
  }

  // QR section
  const qrSection = $('qr-section');
  if (!connected) {
    qrSection.classList.remove('hidden');
  } else {
    qrSection.classList.add('hidden');
    // Clear QR
    const img = $('qr-img');
    img.classList.add('hidden');
    $('qr-placeholder').classList.remove('hidden');
  }

  // Manage polling
  if (connected) {
    stopQrPolling();
  } else if (status !== 'stopped') {
    startQrPolling();
  }
}

function renderRecipientTarget() {
  const target = $('recipient-target');
  if (!target) return;

  const selected = state.fileHeaders.find(h => h === state.recipientColumn) || '';
  if (selected) {
    target.textContent = selected;
    target.classList.add('has-value');
    target.title = `Kolom penerima: ${selected}`;
  } else {
    target.textContent = 'Drop header di sini';
    target.classList.remove('has-value');
    target.title = 'Seret header yang tersedia ke sini untuk memilih kolom penerima';
  }
}

/* ─────────────────────────────
   POLLING
───────────────────────────── */
function startPolling() {
  if (state.pollingStatus) return;
  state.pollingStatus = setInterval(fetchStatus, 3000);
}
function stopQrPolling() {
  if (state.pollingQr) { clearInterval(state.pollingQr); state.pollingQr = null; }
}
function startQrPolling() {
  if (state.pollingQr) return;
  state.pollingQr = setInterval(autoFetchQr, 2000);
}

/* ─────────────────────────────
   TABS
───────────────────────────── */
function initTabs() {
  $$('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.disabled) return;
      $$('.tab-btn').forEach(b => b.classList.remove('active'));
      $$('.tab-pane').forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      $(`tab-${btn.dataset.tab}`).classList.add('active');
    });
  });
}

/* ─────────────────────────────
   FILE UPLOAD / PARSE
───────────────────────────── */
function initFileUpload() {
  const zone = $('drop-zone');
  const input = $('file-input');

  zone.addEventListener('dragover', e => {
    e.preventDefault();
    zone.classList.add('drag-over');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', e => {
    e.preventDefault();
    zone.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f) handleFile(f);
  });

  input.addEventListener('change', () => {
    if (input.files[0]) handleFile(input.files[0]);
    input.value = '';
  });
}

function handleFile(file) {
  const validExt = /\.(csv|xlsx|xls)$/i;
  if (!validExt.test(file.name)) {
    toast('error', 'Format Tidak Didukung', 'File wajib CSV/XLSX/XLS');
    return;
  }
  state.file = file;
  $('dz-file-name').textContent = file.name;
  $('dz-file-name').classList.remove('hidden');
  $('drop-zone').classList.add('has-file');
  $('dz-icon').textContent = '📄';
  $('dz-title').textContent = 'File terpilih';

  const ext = file.name.split('.').pop().toLowerCase();
  if (ext === 'csv') {
    parseCSV(file);
  } else {
    parseXLSX(file);
  }
}

function parseCSV(file) {
  const reader = new FileReader();
  reader.onload = e => {
    const text = e.target.result;
    const lines = text.split(/\r?\n/).filter(l => l.trim());
    if (lines.length < 1) { toast('error', 'File Kosong', 'CSV tidak memiliki data'); return; }
    const separator = detectSeparator(lines[0]);
    const headers = lines[0].split(separator).map(h => h.trim().replace(/^["']|["']$/g, ''));
    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const vals = splitCSVLine(lines[i], separator);
      const obj = {};
      headers.forEach((h, j) => obj[h] = vals[j]?.replace(/^["']|["']$/g, '').trim() || '');
      rows.push(obj);
    }
    onFileParsed(headers, rows.length, rows[0] || {}, rows);
  };
  reader.readAsText(file);
}

function detectSeparator(line) {
  const counts = { ',': 0, ';': 0, '\t': 0, '|': 0 };
  for (const ch of line) if (ch in counts) counts[ch]++;
  return Object.entries(counts).sort((a,b)=>b[1]-a[1])[0][0];
}

function splitCSVLine(line, sep) {
  const result = [];
  let cur = '', inQ = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"' && (i === 0 || line[i-1] === sep)) { inQ = true; }
    else if (ch === '"' && inQ) { inQ = false; }
    else if (ch === sep && !inQ) { result.push(cur); cur = ''; }
    else cur += ch;
  }
  result.push(cur);
  return result;
}

function parseXLSX(file) {
  // Minimal XLSX parser – reads binary, extracts shared strings + sheet
  // Since no external deps, we use a lightweight approach
  const reader = new FileReader();
  reader.onload = e => {
    try {
      // Attempt to use SheetJS if available (CDN injected)
      if (window.XLSX) {
        const wb = window.XLSX.read(e.target.result, { type: 'array' });
        const ws = wb.Sheets[wb.SheetNames[0]];
        const data = window.XLSX.utils.sheet_to_json(ws, { header: 1, defval: '' });
        if (!data.length) { toast('error', 'File Kosong', 'XLSX tidak memiliki data'); return; }
        const headers = data[0].map(h => String(h).trim());
        const rows = data.slice(1).filter(r => r.some(c => c !== '')).map(r => {
          const obj = {};
          headers.forEach((h, i) => obj[h] = String(r[i] ?? '').trim());
          return obj;
        });
        onFileParsed(headers, rows.length, rows[0] || {}, rows);
      } else {
        toast('warning', 'XLSX Perlu Library', 'Memuat SheetJS...');
        loadSheetJS(() => parseXLSX(file));
      }
    } catch (err) {
      toast('error', 'Gagal Parse XLSX', err.message);
    }
  };
  reader.readAsArrayBuffer(file);
}

function loadSheetJS(cb) {
  const s = document.createElement('script');
  s.src = 'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js';
  s.onload = cb;
  s.onerror = () => toast('error', 'Gagal Muat SheetJS', 'Periksa koneksi internet Anda');
  document.head.appendChild(s);
}

function onFileParsed(headers, rowCount, sample) {
  // If a rows array is provided as 4th arg, capture it
  const rows = arguments[3] || [];
  state.fileHeaders = headers;
  state.fileRows = rowCount;
  state.fileSample = sample;
  state.fileData = rows;

  const nomorHeader = headers.find(h => h.toUpperCase() === 'NOMOR');
  if (!state.recipientColumn || !headers.includes(state.recipientColumn)) {
    state.recipientColumn = nomorHeader || '';
  }

  $('headers-section').classList.remove('hidden');
  renderHeadersPreview();
  validateForm();
  updateTemplatePreview();
  toast('success', 'File Berhasil Dibaca', `${rowCount} baris ditemukan`);
}

function renderHeadersPreview() {
  const { fileHeaders, fileRows, fileSample } = state;

  // Headers chips — draggable
  const hChips = $('header-chips');
  hChips.innerHTML = fileHeaders.map(h =>
    `<span class="chip chip-draggable" draggable="true" data-header="${escHtml(h)}" title="Seret ke template untuk menyisipkan {{${h}}}">${h} <span class="chip-drag-icon">⠿</span></span>`
  ).join('');

  // Attach drag events to each chip
  hChips.querySelectorAll('.chip-draggable').forEach(chip => {
    chip.addEventListener('dragstart', e => {
      const header = chip.dataset.header;
      e.dataTransfer.setData('text/plain', `{{${header}}}`);
      e.dataTransfer.setData('text/x-header-name', header);
      e.dataTransfer.effectAllowed = 'copy';
      chip.classList.add('dragging');
      // Highlight drop target
      $('template-input').classList.add('drop-target-active');
      $('template-drop-hint').classList.remove('hidden');
    });
    chip.addEventListener('dragend', () => {
      chip.classList.remove('dragging');
      $('template-input').classList.remove('drop-target-active');
      $('template-drop-hint').classList.add('hidden');
    });
  });

  // Row count
  $('row-count').textContent = fileRows.toLocaleString('id-ID');

  // Sample data
  const sampleParts = fileHeaders.slice(0, 5).map(h => `${h}=${fileSample[h] || '—'}`);
  $('sample-data').textContent = sampleParts.join(', ') + (fileHeaders.length > 5 ? '...' : '');

  // Recipient selection validation
  renderRecipientTarget();
  const alertBox = $('recipient-alert');
  if (!state.recipientColumn) {
    alertBox.classList.remove('hidden');
    alertBox.className = 'alert alert-warning';
    alertBox.innerHTML = '⚠ Seret salah satu header ke <strong>Kolom penerima</strong> untuk menentukan nomor tujuan.';
  } else if (!fileHeaders.includes(state.recipientColumn)) {
    alertBox.classList.remove('hidden');
    alertBox.className = 'alert alert-error';
    alertBox.innerHTML = '❌ Kolom penerima tidak valid. Pilih header yang tersedia.';
  } else {
    alertBox.classList.add('hidden');
  }
}

/* ─────────────────────────────
   TEMPLATE
───────────────────────────── */
function initTemplate() {
  const ta = $('template-input');

  ta.addEventListener('input', () => {
    state.template = ta.value;
    updatePlaceholderDisplay();
    updateTemplatePreview();
    validateForm();
  });

  initTemplateDrop(ta);
}

function initTemplateDrop(ta) {
  // Track the exact character index resolved on every dragover
  let pendingCaretPos = null;

  ta.addEventListener('dragover', e => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    ta.classList.add('drop-over');

    // Resolve caret position at the current mouse coordinates
    pendingCaretPos = resolveCaretPosAtPoint(ta, e.clientX, e.clientY);

    // Show a live caret inside the textarea so user sees exactly where it'll land
    ta.focus();
    ta.setSelectionRange(pendingCaretPos, pendingCaretPos);
  });

  ta.addEventListener('dragleave', e => {
    if (!ta.contains(e.relatedTarget)) {
      ta.classList.remove('drop-over');
      pendingCaretPos = null;
    }
  });

  ta.addEventListener('drop', e => {
    e.preventDefault();
    ta.classList.remove('drop-over');
    ta.classList.remove('drop-target-active');
    $('template-drop-hint').classList.add('hidden');

    const placeholder = e.dataTransfer.getData('text/plain');
    if (!placeholder) return;

    // Use the position captured during the final dragover; fall back to
    // whatever the textarea's own selectionStart is (already set by dragover)
    const pos = pendingCaretPos ?? ta.selectionStart ?? ta.value.length;
    pendingCaretPos = null;

    insertAtPosition(ta, placeholder, pos);

    state.template = ta.value;
    updatePlaceholderDisplay();
    updateTemplatePreview();
    validateForm();

    flashInserted(ta);
    toast('info', 'Placeholder Disisipkan', `${placeholder} disisipkan ke template`);
  });
}

function initRecipientDrop() {
  const target = $('recipient-target');
  if (!target) return;

  target.addEventListener('dragover', e => {
    e.preventDefault();
    target.classList.add('drop-over');
    e.dataTransfer.dropEffect = 'copy';
  });

  target.addEventListener('dragleave', e => {
    if (!target.contains(e.relatedTarget)) {
      target.classList.remove('drop-over');
    }
  });

  target.addEventListener('drop', e => {
    e.preventDefault();
    target.classList.remove('drop-over');

    const header = e.dataTransfer.getData('text/x-header-name') || e.dataTransfer.getData('text/plain').replace(/^\{\{|\}\}$/g, '');
    if (!header) return;

    setRecipientColumn(header);
    toast('success', 'Kolom Penerima Dipilih', `${header} akan dipakai sebagai nomor tujuan`);
  });
}

/**
 * Use the browser's caret-from-point API to find which character index
 * inside the textarea sits under the pointer, accounting for scroll,
 * padding, font metrics and line-wrapping.
 *
 * Strategy (in priority order):
 *  1. document.caretPositionFromPoint  (Firefox)
 *  2. document.caretRangeFromPoint     (Chrome / Safari / Edge)
 *  3. Mirror-div measurement fallback  (always works)
 */
function resolveCaretPosAtPoint(ta, clientX, clientY) {
  // ── Method 1 & 2: native APIs ──────────────────────────────────────────
  // Both APIs return a position inside the textarea's internal text node.
  // The offset they return IS the character index in ta.value.
  try {
    if (document.caretPositionFromPoint) {           // Firefox
      const pos = document.caretPositionFromPoint(clientX, clientY);
      if (pos) return clamp(pos.offset, 0, ta.value.length);
    }
    if (document.caretRangeFromPoint) {              // Chrome / Safari / Edge
      const range = document.caretRangeFromPoint(clientX, clientY);
      if (range) return clamp(range.startOffset, 0, ta.value.length);
    }
  } catch (_) { /* ignore – fall through to mirror */ }

  // ── Method 3: mirror-div fallback ──────────────────────────────────────
  return resolveCaretPosMirror(ta, clientX, clientY);
}

/**
 * Mirror-div technique: clone the textarea's computed styles into a hidden
 * <div>, render its text as individual <span> characters, then find which
 * span is closest to the pointer.
 */
function resolveCaretPosMirror(ta, clientX, clientY) {
  const style  = window.getComputedStyle(ta);
  const rect   = ta.getBoundingClientRect();

  // Coordinates relative to the textarea's content box
  const localX = clientX - rect.left - parseFloat(style.paddingLeft);
  const localY = clientY - rect.top  - parseFloat(style.paddingTop) + ta.scrollTop;

  // Build mirror
  const mirror = document.createElement('div');
  const mirrorStyles = [
    'position:fixed', 'visibility:hidden', 'pointer-events:none',
    `top:${rect.top}px`, `left:${rect.left}px`,
    `width:${rect.width}px`, `height:${rect.height}px`,
    `padding:${style.padding}`,
    `border:${style.border}`,
    `font:${style.font}`,
    `line-height:${style.lineHeight}`,
    `letter-spacing:${style.letterSpacing}`,
    `white-space:pre-wrap`,
    `word-wrap:break-word`,
    `overflow:hidden`,
    `box-sizing:${style.boxSizing}`,
  ];
  mirror.style.cssText = mirrorStyles.join(';');

  const text = ta.value;
  let bestIdx = text.length;
  let bestDist = Infinity;

  // Wrap every character in a span (batch append via fragment)
  const frag = document.createDocumentFragment();
  const spans = [];
  for (let i = 0; i <= text.length; i++) {
    const ch = i < text.length ? text[i] : '\u200b'; // zero-width sentinel at end
    const span = document.createElement('span');
    span.textContent = ch;
    frag.appendChild(span);
    spans.push(span);
  }
  mirror.appendChild(frag);
  document.body.appendChild(mirror);

  // Measure each span and find nearest to pointer
  for (let i = 0; i < spans.length; i++) {
    const sr = spans[i].getBoundingClientRect();
    const mx = sr.left + sr.width / 2 - rect.left - parseFloat(style.paddingLeft);
    const my = sr.top  + sr.height / 2 - rect.top  - parseFloat(style.paddingTop) + ta.scrollTop;
    const dist = Math.hypot(mx - localX, my - localY);
    if (dist < bestDist) { bestDist = dist; bestIdx = i; }
  }

  document.body.removeChild(mirror);
  return clamp(bestIdx, 0, text.length);
}

function clamp(val, min, max) { return Math.max(min, Math.min(max, val)); }

/**
 * Insert `text` at character index `pos` inside the textarea,
 * adding smart spacing and leaving the caret right after the inserted text.
 */
function insertAtPosition(el, text, pos) {
  const val    = el.value;
  const before = val.slice(0, pos);
  const after  = val.slice(pos);

  const needSpaceBefore = before.length > 0 && !/\s$/.test(before);
  const needSpaceAfter  = after.length  > 0 && !/^\s/.test(after);

  const insert = (needSpaceBefore ? ' ' : '') + text + (needSpaceAfter ? ' ' : '');
  el.value = before + insert + after;

  const newPos = pos + insert.length;
  el.focus();
  el.setSelectionRange(newPos, newPos);
}

function flashInserted(el) {
  el.classList.add('drop-flash');
  setTimeout(() => el.classList.remove('drop-flash'), 600);
}

function extractPlaceholders(text) {
  const matches = text.matchAll(/\{\{(\w+)\}\}/g);
  const set = new Set();
  for (const m of matches) set.add(m[1].toLowerCase());
  return [...set];
}

function updatePlaceholderDisplay() {
  const placeholders = extractPlaceholders(state.template);
  const container = $('placeholder-list');
  if (!placeholders.length) {
    container.innerHTML = '<span class="text-muted text-xs text-mono">Belum ada placeholder terdeteksi</span>';
    return;
  }

  // Build combined data for validation
  const available = [
    ...state.fileHeaders.map(h => h.toLowerCase()),
    ...state.additionalFields.map(f => f.name.toLowerCase()),
  ];

  container.innerHTML = placeholders.map(p => {
    const ok = available.includes(p);
    return `<span class="ph-chip ${ok ? 'ok' : 'err'}">${ok ? '✓' : '✗'} {{${p}}}</span>`;
  }).join('');
}

function updateTemplatePreview() {
  const { template, fileHeaders, fileSample, additionalFields } = state;
  if (!template) {
    $('template-preview').value = '';
    return;
  }
  // Build merge data
  const data = { ...fileSample };
  additionalFields.forEach(f => {
    if (f.name) data[f.name.toLowerCase()] = f.value;
  });
  // Also lowercase all header keys
  const dataLower = {};
  Object.entries(data).forEach(([k, v]) => dataLower[k.toLowerCase()] = v);

  let preview = template;
  preview = preview.replace(/\{\{(\w+)\}\}/g, (_, key) => dataLower[key.toLowerCase()] ?? `{{${key}}}`);
  $('template-preview').value = preview;
}

/* ─────────────────────────────
   ADDITIONAL FIELDS
───────────────────────────── */
function initAdditionalFields() {
  $('btn-add-field').addEventListener('click', () => {
    state.additionalFields.push({ name: '', value: '' });
    renderFieldList();
  });
}

function renderFieldList() {
  const list = $('field-list');
  list.innerHTML = '';
  state.additionalFields.forEach((field, idx) => {
    const row = document.createElement('div');
    row.className = 'field-row';
    row.innerHTML = `
      <input type="text" placeholder="Nama field (cth: campaign)" value="${escHtml(field.name)}" data-idx="${idx}" data-part="name">
      <input type="text" placeholder="Nilai (cth: Summer Promo)" value="${escHtml(field.value)}" data-idx="${idx}" data-part="value">
      <button class="btn-icon" data-del="${idx}" title="Hapus field">✕</button>
    `;
    list.appendChild(row);
  });

  list.querySelectorAll('input').forEach(inp => {
    inp.addEventListener('input', () => {
      const idx = +inp.dataset.idx;
      state.additionalFields[idx][inp.dataset.part] = inp.value;
      updatePlaceholderDisplay();
      updateTemplatePreview();
      validateForm();
    });
  });

  list.querySelectorAll('[data-del]').forEach(btn => {
    btn.addEventListener('click', () => {
      const idx = +btn.dataset.del;
      state.additionalFields.splice(idx, 1);
      renderFieldList();
      updatePlaceholderDisplay();
      updateTemplatePreview();
      validateForm();
    });
  });
}

/* ─────────────────────────────
   DELAY SETTINGS
───────────────────────────── */
function initDelay() {
  const map = {
    'delay-typing-min':   ['delay', 'typingMin'],
    'delay-typing-max':   ['delay', 'typingMax'],
    'delay-duration-min': ['delay', 'durationMin'],
    'delay-duration-max': ['delay', 'durationMax'],
    'delay-send-min':     ['delay', 'sendMin'],
    'delay-send-max':     ['delay', 'sendMax'],
    'delay-batch-size':   ['delay', 'batchSize'],
    'delay-batch-rest':   ['delay', 'batchRest'],
  };
  Object.entries(map).forEach(([id, [obj, key]]) => {
    const el = $(id);
    if (el) {
      el.value = state[obj][key];
      el.addEventListener('input', () => {
        state[obj][key] = +el.value;
      });
    }
  });
}

/* ─────────────────────────────
   VALIDATION
───────────────────────────── */
function validateForm() {
  const checks = [];

  if (!state.file) checks.push('File belum dipilih');
  if (state.fileHeaders.length === 0) checks.push('File belum diparsing');

  if (!state.recipientColumn) {
    checks.push('Kolom penerima belum dipilih');
  } else if (state.fileHeaders.length > 0 && !state.fileHeaders.includes(state.recipientColumn)) {
    checks.push('Kolom penerima tidak valid');
  }

  if (!state.template.trim()) checks.push('Template pesan kosong');

  if (state.template) {
    const placeholders = extractPlaceholders(state.template);
    const available = [
      ...state.fileHeaders.map(h => h.toLowerCase()),
      ...state.additionalFields.map(f => f.name.toLowerCase()).filter(Boolean),
    ];
    const missing = placeholders.filter(p => !available.includes(p));
    if (missing.length > 0) checks.push(`Placeholder hilang: ${missing.map(p=>`{{${p}}}`).join(', ')}`);
  }

  const blastBtn = $('btn-blast');
  const statusEl = $('blast-status');

  if (checks.length === 0) {
    blastBtn.disabled = false;
    statusEl.innerHTML = `<span class="bs-ok">✅ Semua validasi OK — siap blast ${state.fileRows.toLocaleString('id-ID')} pesan</span>`;
  } else {
    blastBtn.disabled = true;
    statusEl.innerHTML = checks.map(c => `<span class="bs-err">⚠ ${c}</span>`).join('<br>');
  }
}

/* ─────────────────────────────
   SEND BLAST
───────────────────────────── */
async function sendBlast() {
  if (state.blasting) return;
  state.blasting = true;

  const btn = $('btn-blast');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Memproses...';

  try {
    // Build JSON payload matching backend DynamicBlastRequest
    const payload = {
      rows: state.fileData,
      template: state.template,
      recipient_column: state.recipientColumn,
      additional_fields: {},
      pre_typing_delay_min: Number(state.delay.typingMin),
      pre_typing_delay_max: Number(state.delay.typingMax),
      typing_duration_min: Number(state.delay.durationMin),
      typing_duration_max: Number(state.delay.durationMax),
      pre_send_delay_min: Number(state.delay.sendMin),
      pre_send_delay_max: Number(state.delay.sendMax),
      batch_size: Number(state.delay.batchSize),
      batch_rest_seconds: Number(state.delay.batchRest),
    };
    state.additionalFields.forEach(f => { if (f.name) payload.additional_fields[f.name] = f.value; });

    const result = await apiFetch('POST', '/send-blast-dynamic', payload);
    displayBlastResult(result);
    const sent = Number(result.sent_count ?? 0);
    const failed = Number(result.failed_count ?? 0);
    const skipped = Number(result.skipped_count ?? 0);
    toast('success', 'Blast Selesai', `${sent} terkirim, ${failed} gagal, ${skipped} dilewati`);
  } catch (e) {
    toast('error', 'Blast Gagal', e.message);
  } finally {
    state.blasting = false;
    btn.disabled = false;
    btn.innerHTML = '🚀 Mulai Blast';
    validateForm();
  }
}

function displayBlastResult(result) {
  const container = $('blast-result');
  container.classList.remove('hidden');
  const totalRows = result.total_rows ?? result.rows_count ?? '?';
  const sentCount = result.sent_count ?? 0;
  const failedCount = result.failed_count ?? 0;
  const skippedCount = result.skipped_count ?? 0;
  container.innerHTML = `
    <div class="result-card">
      <div class="result-header">
        <span>📊</span> Hasil Blast
      </div>
      <div class="result-stat">
        <div class="stat-item">
          <span class="stat-val">${totalRows}</span>
          <span class="stat-label">Total Pesan</span>
        </div>
        <div class="stat-item">
          <span class="stat-val" style="color:var(--success)">${sentCount}</span>
          <span class="stat-label">Berhasil</span>
        </div>
        <div class="stat-item">
          <span class="stat-val" style="color:var(--error)">${failedCount}</span>
          <span class="stat-label">Gagal</span>
        </div>
        <div class="stat-item">
          <span class="stat-val" style="color:var(--warning)">${skippedCount}</span>
          <span class="stat-label">Dilewati</span>
        </div>
      </div>
      ${result.preview ? `<div class="info-row"><span class="info-label">Preview:</span><span class="info-value">${escHtml(result.preview)}</span></div>` : ''}
      ${Array.isArray(result.failed_items) && result.failed_items.length ? `<div class="info-row"><span class="info-label">Gagal Kirim:</span><span class="info-value">${escHtml(result.failed_items.slice(0, 3).map(item => `baris ${item.row}${item.chatId ? ` (${item.chatId})` : ''}`).join(', '))}${result.failed_items.length > 3 ? '...' : ''}</span></div>` : ''}
    </div>
  `;
}

/* ─────────────────────────────
   SIDEBAR MOBILE TOGGLE
───────────────────────────── */
function initMobileNav() {
  $('hamburger').addEventListener('click', () => {
    $('sidebar').classList.toggle('open');
    $('overlay').classList.toggle('active');
  });
  $('overlay').addEventListener('click', () => {
    $('sidebar').classList.remove('open');
    $('overlay').classList.remove('active');
  });
}

/* ─────────────────────────────
   UTILS
───────────────────────────── */
function escHtml(str) {
  return String(str)
    .replace(/&/g,'&amp;')
    .replace(/</g,'&lt;')
    .replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;');
}

/* ─────────────────────────────
   INIT
───────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initFileUpload();
  initTemplate();
  initRecipientDrop();
  initAdditionalFields();
  initDelay();
  initMobileNav();

  // Session buttons
  $('btn-start').addEventListener('click', startSession);
  $('btn-logout').addEventListener('click', logoutSession);
  $('btn-qr').addEventListener('click', refreshQr);
  $('btn-blast').addEventListener('click', sendBlast);

  // Initial state
  validateForm();
  renderFieldList();

  // Kick off polling
  fetchStatus().then(() => {
    startPolling();
  });
});