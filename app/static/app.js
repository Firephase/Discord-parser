/* ─── State ─────────────────────────────────────────────── */
const state = {
  messages: [],
  keywords: [],
  links: [],
  unreadCount: 0,
  ws: null,
  wsReconnectTimer: null,
};

/* ─── API helpers ───────────────────────────────────────── */
async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch('/api/v1' + path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || res.statusText);
  }
  return res.json();
}

/* ─── Toast ─────────────────────────────────────────────── */
function toast(msg, type = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  document.getElementById('toast-container').appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

/* ─── Tab routing ───────────────────────────────────────── */
document.querySelectorAll('nav button').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('nav button').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('section.tab').forEach(s => s.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('tab-' + btn.dataset.tab).classList.add('active');
    if (btn.dataset.tab === 'status') loadStatus();
  });
});

/* ─── Utilities ─────────────────────────────────────────── */
function relTime(iso) {
  const d = new Date(iso);
  const secs = Math.floor((Date.now() - d.getTime()) / 1000);
  if (secs < 60) return 'just now';
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return d.toLocaleDateString();
}

function highlightKeywords(text, keywords) {
  if (!keywords || keywords.length === 0) return escHtml(text);
  let out = escHtml(text);
  keywords.forEach(kw => {
    const re = new RegExp(escRe(kw), 'gi');
    out = out.replace(re, m => `<mark>${m}</mark>`);
  });
  return out;
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function escRe(s) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function avatarLetter(name) {
  return (name || '?')[0].toUpperCase();
}

function fmtUptime(s) {
  const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
  return `${h}h ${m}m ${sec}s`;
}

/* ─── Messages ──────────────────────────────────────────── */
async function loadMessages() {
  const search = document.getElementById('msgSearch').value.trim();
  const unreadOnly = document.getElementById('unreadFilter').checked;
  const params = new URLSearchParams({ skip: 0, limit: 100 });
  if (search) params.set('keyword', search);
  if (unreadOnly) params.set('unread_only', 'true');

  const data = await api('GET', '/messages?' + params.toString()).catch(e => {
    toast(e.message, 'error'); return null;
  });
  if (!data) return;

  state.messages = data.items;
  renderMessages();
  updateUnreadBadge();
}

function renderMessages() {
  const list = document.getElementById('msgList');
  if (state.messages.length === 0) {
    list.innerHTML = '<div class="empty"><div class="empty-icon">💬</div>No messages captured yet.<br>Add keywords and connect to Discord servers.</div>';
    return;
  }
  list.innerHTML = state.messages.map(m => renderMsgCard(m)).join('');

  list.querySelectorAll('[data-read]').forEach(btn => {
    btn.addEventListener('click', () => markRead(+btn.dataset.read));
  });
  list.querySelectorAll('[data-del]').forEach(btn => {
    btn.addEventListener('click', () => deleteMsg(+btn.dataset.del));
  });
}

function renderMsgCard(m) {
  const unread = m.is_read ? '' : ' unread';
  const loc = [m.guild_name, m.channel_name ? '#' + m.channel_name : null].filter(Boolean).join(' › ');
  return `
  <div class="card${unread}" id="msg-${m.id}">
    <div class="card-header">
      <div class="avatar">${avatarLetter(m.author_name)}</div>
      <div class="msg-meta">
        <div class="msg-author">${escHtml(m.author_name)}</div>
        <div class="msg-location">${escHtml(loc)}</div>
      </div>
      <div class="msg-time">${relTime(m.captured_at)}</div>
    </div>
    <div class="msg-content">${highlightKeywords(m.content, m.matched_keywords)}</div>
    <div class="keywords-row">
      ${(m.matched_keywords || []).map(k => `<span class="kw-badge">${escHtml(k)}</span>`).join('')}
      <div style="flex:1"></div>
      ${!m.is_read ? `<button class="btn btn-ghost btn-sm" data-read="${m.id}">Mark read</button>` : ''}
      <button class="btn btn-danger btn-sm" data-del="${m.id}">Delete</button>
    </div>
  </div>`;
}

function prependMessage(m) {
  state.messages.unshift(m);
  const list = document.getElementById('msgList');
  const empty = list.querySelector('.empty');
  if (empty) empty.remove();

  const div = document.createElement('div');
  div.innerHTML = renderMsgCard(m);
  const card = div.firstElementChild;
  list.prepend(card);

  card.querySelector('[data-read]')?.addEventListener('click', () => markRead(m.id));
  card.querySelector('[data-del]')?.addEventListener('click', () => deleteMsg(m.id));
  updateUnreadBadge();
}

async function markRead(id) {
  await api('POST', `/messages/${id}/read`).catch(e => toast(e.message, 'error'));
  const m = state.messages.find(x => x.id === id);
  if (m) m.is_read = true;
  const card = document.getElementById('msg-' + id);
  if (card) {
    card.classList.remove('unread');
    card.querySelector('[data-read]')?.remove();
  }
  updateUnreadBadge();
}

async function deleteMsg(id) {
  await api('DELETE', `/messages/${id}`).catch(e => { toast(e.message, 'error'); return; });
  state.messages = state.messages.filter(x => x.id !== id);
  document.getElementById('msg-' + id)?.remove();
  if (state.messages.length === 0) renderMessages();
  updateUnreadBadge();
}

function updateUnreadBadge() {
  state.unreadCount = state.messages.filter(m => !m.is_read).length;
  const badge = document.getElementById('unreadBadge');
  if (state.unreadCount > 0) {
    badge.textContent = `${state.unreadCount} unread`;
    badge.classList.add('visible');
  } else {
    badge.classList.remove('visible');
  }
  const cnt = document.getElementById('msgTabCount');
  cnt.textContent = state.messages.length > 0 ? ` (${state.messages.length})` : '';
}

document.getElementById('msgSearch').addEventListener('input', () => loadMessages());
document.getElementById('unreadFilter').addEventListener('change', () => loadMessages());

document.getElementById('markAllBtn').addEventListener('click', async () => {
  await api('POST', '/messages/read-all').catch(e => toast(e.message, 'error'));
  await loadMessages();
  toast('All messages marked as read', 'success');
});

document.getElementById('clearAllBtn').addEventListener('click', async () => {
  if (!confirm('Delete all captured messages?')) return;
  await api('DELETE', '/messages').catch(e => toast(e.message, 'error'));
  state.messages = [];
  renderMessages();
  updateUnreadBadge();
  toast('All messages cleared', 'success');
});

/* ─── Keywords ──────────────────────────────────────────── */
async function loadKeywords() {
  state.keywords = await api('GET', '/keywords').catch(e => { toast(e.message, 'error'); return []; });
  renderKeywords();
}

function renderKeywords() {
  const list = document.getElementById('kwList');
  if (state.keywords.length === 0) {
    list.innerHTML = '<div class="empty"><div class="empty-icon">🔍</div>No keywords yet. Add one above.</div>';
    return;
  }
  list.innerHTML = state.keywords.map(k => `
  <div class="list-item" id="kw-${k.id}">
    <div>
      <div class="list-item-name">${escHtml(k.keyword)}</div>
      <div class="list-item-sub">${k.case_sensitive ? 'Case-sensitive' : 'Case-insensitive'}</div>
    </div>
    <label class="toggle">
      <input type="checkbox" ${k.is_active ? 'checked' : ''} data-toggle="${k.id}">
      <span class="toggle-track"></span>
      Active
    </label>
    <button class="btn btn-danger btn-sm btn-icon" data-kw-del="${k.id}" title="Delete">✕</button>
  </div>`).join('');

  list.querySelectorAll('[data-toggle]').forEach(cb => {
    cb.addEventListener('change', () => toggleKeyword(+cb.dataset.toggle, cb.checked));
  });
  list.querySelectorAll('[data-kw-del]').forEach(btn => {
    btn.addEventListener('click', () => deleteKeyword(+btn.dataset.kwDel));
  });
}

document.getElementById('kwAddBtn').addEventListener('click', addKeyword);
document.getElementById('kwInput').addEventListener('keydown', e => { if (e.key === 'Enter') addKeyword(); });

async function addKeyword() {
  const kw = document.getElementById('kwInput').value.trim();
  if (!kw) return;
  const cs = document.getElementById('kwCaseSensitive').checked;
  await api('POST', '/keywords', { keyword: kw, case_sensitive: cs })
    .then(() => { document.getElementById('kwInput').value = ''; toast(`Keyword "${kw}" added`, 'success'); })
    .catch(e => toast(e.message, 'error'));
  await loadKeywords();
}

async function toggleKeyword(id, active) {
  await api('PUT', `/keywords/${id}`, { is_active: active }).catch(e => toast(e.message, 'error'));
}

async function deleteKeyword(id) {
  await api('DELETE', `/keywords/${id}`).catch(e => { toast(e.message, 'error'); return; });
  state.keywords = state.keywords.filter(k => k.id !== id);
  document.getElementById('kw-' + id)?.remove();
  if (state.keywords.length === 0) renderKeywords();
  toast('Keyword removed', 'success');
}

/* ─── Links ─────────────────────────────────────────────── */
async function loadLinks() {
  state.links = await api('GET', '/links').catch(e => { toast(e.message, 'error'); return []; });
  renderLinks();
}

function renderLinks() {
  const list = document.getElementById('linkList');
  if (state.links.length === 0) {
    list.innerHTML = '<div class="empty"><div class="empty-icon">🔗</div>No links added yet.</div>';
    return;
  }
  list.innerHTML = state.links.map(l => {
    const statusMap = { active: 'Active', pending: 'Pending…', error: 'Error', invalid: 'Invalid', approval_required: 'Needs approval' };
    return `
  <div class="list-item" id="link-${l.id}">
    <div style="flex:1;min-width:0">
      <div class="list-item-name">${l.guild_name ? escHtml(l.guild_name) : escHtml(l.invite_url)}</div>
      <div class="list-item-sub">${escHtml(l.invite_url)}${l.error_message ? ' — ' + escHtml(l.error_message) : ''}</div>
    </div>
    <span class="status-badge ${l.status}">${statusMap[l.status] || l.status}</span>
    <button class="btn btn-ghost btn-sm" data-link-refresh="${l.id}" title="Re-check">↻</button>
    <button class="btn btn-danger btn-sm btn-icon" data-link-del="${l.id}" title="Remove">✕</button>
  </div>`;
  }).join('');

  list.querySelectorAll('[data-link-refresh]').forEach(btn => {
    btn.addEventListener('click', () => refreshLink(+btn.dataset.linkRefresh));
  });
  list.querySelectorAll('[data-link-del]').forEach(btn => {
    btn.addEventListener('click', () => deleteLink(+btn.dataset.linkDel));
  });
}

document.getElementById('linkAddBtn').addEventListener('click', addLink);
document.getElementById('linkInput').addEventListener('keydown', e => { if (e.key === 'Enter') addLink(); });

async function addLink() {
  const url = document.getElementById('linkInput').value.trim();
  if (!url) return;
  await api('POST', '/links', { invite_url: url })
    .then(() => { document.getElementById('linkInput').value = ''; toast('Link added — joining server…', 'info'); })
    .catch(e => toast(e.message, 'error'));
  await loadLinks();
}

async function refreshLink(id) {
  await api('POST', `/links/${id}/refresh`).catch(e => toast(e.message, 'error'));
  toast('Re-checking link…', 'info');
  await loadLinks();
}

async function deleteLink(id) {
  await api('DELETE', `/links/${id}`).catch(e => { toast(e.message, 'error'); return; });
  state.links = state.links.filter(l => l.id !== id);
  document.getElementById('link-' + id)?.remove();
  if (state.links.length === 0) renderLinks();
  toast('Link removed', 'success');
}

/* ─── Status ─────────────────────────────────────────────── */
async function loadStatus() {
  const s = await api('GET', '/status').catch(e => { toast(e.message, 'error'); return null; });
  if (!s) return;

  document.getElementById('statusDot').className = 'status-dot' + (s.connected ? ' connected' : '');
  document.getElementById('statusLabel').textContent = s.connected ? `${s.user}` : 'Disconnected';
  document.getElementById('statUser').textContent = s.user || '—';
  document.getElementById('statUptime').textContent = s.connected ? fmtUptime(s.uptime_seconds) : '—';
  document.getElementById('statGuilds').textContent = s.guilds.length;
  document.getElementById('statWsClients').textContent = s.websocket_clients;

  document.getElementById('disconnectBtn')?.addEventListener('click', disconnectToken);

  const gl = document.getElementById('guildList');
  if (s.guilds.length === 0) {
    gl.innerHTML = '<div class="empty" style="padding:24px">No servers connected</div>';
  } else {
    gl.innerHTML = s.guilds.map(g => `
    <div class="list-item">
      <div>
        <div class="list-item-name">${escHtml(g.name)}</div>
        <div class="list-item-sub">ID: ${g.id} · ${g.member_count ?? '?'} members</div>
      </div>
      <span class="status-badge active">Active</span>
    </div>`).join('');
  }
}

/* ─── WebSocket ─────────────────────────────────────────── */
function connectWs() {
  if (state.ws) { state.ws.close(); state.ws = null; }

  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  state.ws = new WebSocket(`${proto}://${location.host}/ws`);

  state.ws.onopen = () => {
    document.getElementById('wsStatus').textContent = 'WS: live';
    if (state.wsReconnectTimer) { clearTimeout(state.wsReconnectTimer); state.wsReconnectTimer = null; }
    // Ping every 25s to keep connection alive
    state.wsPingTimer = setInterval(() => {
      if (state.ws?.readyState === WebSocket.OPEN) state.ws.send('ping');
    }, 25000);
  };

  state.ws.onmessage = e => {
    try {
      const payload = JSON.parse(e.data);
      if (payload.event === 'new_message') {
        prependMessage(payload.data);
        toast(`New match from ${payload.data.author_name} in #${payload.data.channel_name}`, 'info');
      }
    } catch (_) {}
  };

  state.ws.onclose = () => {
    document.getElementById('wsStatus').textContent = 'WS: reconnecting…';
    clearInterval(state.wsPingTimer);
    state.wsReconnectTimer = setTimeout(connectWs, 3000);
  };

  state.ws.onerror = () => state.ws.close();
}

/* ─── Periodic status update ─────────────────────────────── */
async function pollStatus() {
  const s = await api('GET', '/status').catch(() => null);
  if (s) {
    document.getElementById('statusDot').className = 'status-dot' + (s.connected ? ' connected' : '');
    document.getElementById('statusLabel').textContent = s.connected ? s.user : 'Disconnected';
  }
}

/* ─── Setup overlay ─────────────────────────────────────── */
const setupOverlay = document.getElementById('setupOverlay');
const setupInput   = document.getElementById('setupTokenInput');
const setupError   = document.getElementById('setupError');
const setupBtn     = document.getElementById('setupConnectBtn');
const setupToggle  = document.getElementById('setupTokenToggle');

setupToggle.addEventListener('click', () => {
  const isPassword = setupInput.type === 'password';
  setupInput.type = isPassword ? 'text' : 'password';
  setupToggle.textContent = isPassword ? 'Hide' : 'Show';
});

setupInput.addEventListener('keydown', e => { if (e.key === 'Enter') submitToken(); });
setupBtn.addEventListener('click', submitToken);

async function submitToken() {
  const token = setupInput.value.trim();
  if (!token) return;

  setupBtn.disabled = true;
  setupBtn.textContent = 'Connecting…';
  setupError.style.display = 'none';

  try {
    const res = await fetch('/api/v1/auth/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    });
    const data = await res.json();
    if (!res.ok) {
      setupError.textContent = data.detail || 'Unknown error';
      setupError.style.display = 'block';
    } else {
      setupInput.value = '';
      hideSetup();
      toast(`Connected as ${data.user}`, 'success');
      await Promise.all([loadMessages(), loadKeywords(), loadLinks()]);
      connectWs();
      pollStatus();
      setInterval(pollStatus, 10000);
    }
  } catch (e) {
    setupError.textContent = 'Network error — is the server running?';
    setupError.style.display = 'block';
  } finally {
    setupBtn.disabled = false;
    setupBtn.textContent = 'Connect';
  }
}

function showSetup() { setupOverlay.style.display = 'flex'; }
function hideSetup() { setupOverlay.style.display = 'none'; }

async function disconnectToken() {
  if (!confirm('Disconnect from Discord and remove the saved token?')) return;
  await api('DELETE', '/auth/token').catch(e => toast(e.message, 'error'));
  toast('Disconnected', 'info');
  showSetup();
}

/* ─── Init ───────────────────────────────────────────────── */
(async () => {
  // Check if a token is already saved; if not, show setup screen
  const tokenStatus = await fetch('/api/v1/auth/token/status').then(r => r.json()).catch(() => ({ has_token: false }));
  if (!tokenStatus.has_token) {
    showSetup();
    return; // Don't load main app until connected
  }

  await Promise.all([loadMessages(), loadKeywords(), loadLinks()]);
  connectWs();
  pollStatus();
  setInterval(pollStatus, 10000);
})();
