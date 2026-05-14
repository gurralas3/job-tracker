/* ──────────────────────────────────────────────
   Job Tracker · Dashboard JS
   ────────────────────────────────────────────── */

const STATUSES = [
  'Applied', 'Under Review', 'Phone Screen',
  'Technical Interview', 'Final Interview',
  'Offer', 'Rejected', 'Withdrawn',
];

const STATUS_COLORS = {
  'Applied':               '#3b82f6',
  'Under Review':          '#0ea5e9',
  'Phone Screen':          '#8b5cf6',
  'Technical Interview':   '#6366f1',
  'Final Interview':       '#a855f7',
  'Offer':                 '#10b981',
  'Rejected':              '#f43f5e',
  'Withdrawn':             '#6b7280',
};

let applications = [];
let sortKey = 'applied_at';
let sortDir = -1; // -1 = desc
let resumeFolders = [];
let charts = {};
let debounceTimer = null;
let currentPage = 1;
const PAGE_SIZE = 50;

// ── Init ──────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  loadApplications();
  loadAnalytics();
  loadSyncStatus();
  loadUserInfo();
});

async function loadUserInfo() {
  try {
    const res = await fetch('/api/user');
    if (!res.ok) return;
    const user = await res.json();
    const avatar = document.getElementById('userAvatar');
    const name = document.getElementById('userName');
    if (user.picture) { avatar.src = user.picture; avatar.classList.remove('hidden'); }
    if (user.name) { name.textContent = user.name; name.classList.remove('hidden'); }
  } catch {}
}


// ── Data Loading ──────────────────────────────────────────────

async function loadApplications() {
  const params = new URLSearchParams();
  const search = document.getElementById('searchInput').value.trim();
  const status = document.getElementById('statusFilter').value;

  if (search) params.set('search', search);
  if (status) params.set('status', status);

  try {
    const res = await fetch(`/api/applications?${params}`);
    applications = await res.json();
    currentPage = 1;
    renderTable();
  } catch (e) {
    showToast('Failed to load applications', 'error');
  }
}

async function loadAnalytics() {
  try {
    const res = await fetch('/api/analytics');
    const data = await res.json();
    updateStats(data.stats);
    renderCharts(data);
  } catch (e) {
    console.error('Analytics error', e);
  }
}

async function loadSyncStatus() {
  try {
    const res = await fetch('/api/sync/status');
    const data = await res.json();
    if (data.synced_at) {
      const dt = new Date(data.synced_at);
      document.getElementById('lastSyncLabel').textContent =
        `Last sync: ${dt.toLocaleDateString()} ${dt.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}`;
    }
  } catch (e) {}
}

function debounceLoad() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(loadApplications, 300);
}

// ── Stats ─────────────────────────────────────────────────────

function updateStats(s) {
  document.getElementById('statToday').textContent     = s.today ?? 0;
  document.getElementById('statTotal').textContent     = s.total ?? 0;
  document.getElementById('statPending').textContent   = s.pending ?? 0;
  document.getElementById('statResponses').textContent = s.responses ?? 0;
  document.getElementById('statRejected').textContent  = s.rejected ?? 0;
  document.getElementById('statOffers').textContent    = s.offers ?? 0;
}

// ── Table Rendering ───────────────────────────────────────────

function renderTable() {
  const tbody = document.getElementById('appTable');
  document.getElementById('appCount').textContent = applications.length;

  const sorted = [...applications].sort((a, b) => {
    const av = a[sortKey] ?? '';
    const bv = b[sortKey] ?? '';
    return av < bv ? sortDir : av > bv ? -sortDir : 0;
  });

  if (!sorted.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center py-16 text-gray-500">
      No applications found. Sync your emails or add manually.
    </td></tr>`;
    renderPagination(0);
    return;
  }

  const totalPages = Math.ceil(sorted.length / PAGE_SIZE);
  if (currentPage > totalPages) currentPage = totalPages;
  const start = (currentPage - 1) * PAGE_SIZE;
  const page = sorted.slice(start, start + PAGE_SIZE);

  tbody.innerHTML = page.map((app, idx) => `
    <tr data-id="${app.id}">
      <td class="text-gray-500">${start + idx + 1}</td>
      <td class="font-semibold text-white max-w-[140px] truncate" title="${esc(app.company)}">${esc(app.company)}</td>
      <td class="max-w-[180px] truncate ${app.job_title === 'Unknown Position' ? 'text-orange-400 font-medium' : 'text-gray-300'}" title="${app.job_title === 'Unknown Position' ? 'Click ✏️ to fix this title' : esc(app.job_title)}">${esc(app.job_title)}${app.job_title === 'Unknown Position' ? ' <span class="text-xs cursor-pointer hover:text-orange-300" onclick="openEditModal('+app.id+')">✏️</span>' : ''}</td>
      <td class="text-gray-400 text-xs whitespace-nowrap">${formatDatetime(app.applied_at)}</td>
      <td>${statusSelect(app)}</td>
      <td class="text-xs">${resumeCell(app)}</td>
      <td class="text-center">
        <div class="flex items-center justify-center gap-2">
          <button onclick="openEditModal(${app.id})" class="text-gray-400 hover:text-blue-400 transition text-base" title="Edit">✏</button>
          <button onclick="deleteApp(${app.id})" class="text-gray-500 hover:text-rose-400 transition text-base" title="Delete">🗑</button>
        </div>
      </td>
    </tr>
  `).join('');

  renderPagination(totalPages);
}

function renderPagination(totalPages) {
  let el = document.getElementById('paginationBar');
  if (!el) {
    el = document.createElement('div');
    el.id = 'paginationBar';
    el.className = 'px-6 pb-4 flex items-center gap-3 text-sm text-gray-400';
    document.querySelector('#appTable').closest('section').after(el);
  }
  if (totalPages <= 1) { el.innerHTML = ''; return; }
  el.innerHTML = `
    <button onclick="goPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}
      class="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition">← Prev</button>
    <span>Page <strong class="text-white">${currentPage}</strong> of ${totalPages}</span>
    <button onclick="goPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}
      class="px-3 py-1 rounded bg-gray-800 hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed transition">Next →</button>
    <span class="ml-2 text-gray-600">(${applications.length} total)</span>
  `;
}

function goPage(page) {
  currentPage = page;
  renderTable();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function statusSelect(app) {
  const opts = STATUSES.map(s =>
    `<option value="${s}" ${s === app.status ? 'selected' : ''}>${s}</option>`
  ).join('');
  return `<select class="status-select ${badgeClass(app.status)}"
    onchange="updateStatus(${app.id}, this.value)">${opts}</select>`;
}

function resumeCell(app) {
  if (app.resume_folder) {
    return `<button onclick="openResume('${esc(app.resume_folder)}')" class="text-blue-400 hover:text-blue-300 font-mono underline text-xs transition" title="Click to open resume">${esc(app.resume_folder)}</button>`;
  }
  return `<button onclick="assignResume(${app.id})" class="text-xs text-gray-500 hover:text-gray-300 underline">Assign folder</button>`;
}

async function openResume(name) {
  const res = await fetch('/api/open-resume', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name }),
  });
  const data = await res.json();
  if (!data.success) showToast(data.error || 'Could not open file', 'error');
}

function badgeClass(status) {
  const map = {
    'Applied': 'text-blue-300',
    'Under Review': 'text-sky-300',
    'Phone Screen': 'text-violet-300',
    'Technical Interview': 'text-indigo-300',
    'Final Interview': 'text-purple-300',
    'Offer': 'text-emerald-300',
    'Rejected': 'text-rose-400',
    'Withdrawn': 'text-gray-400',
  };
  return map[status] || 'text-gray-300';
}

function formatDatetime(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  const day   = String(d.getDate()).padStart(2, '0');
  const month = d.toLocaleString('en-GB', {month: 'short'});
  const year  = d.getFullYear();
  const hh    = String(d.getHours()).padStart(2, '0');
  const mm    = String(d.getMinutes()).padStart(2, '0');
  return `${day} ${month} ${year}, ${hh}:${mm}`;
}

function esc(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function sortBy(key) {
  if (sortKey === key) sortDir *= -1;
  else { sortKey = key; sortDir = -1; }
  renderTable();
}

function clearFilters() {
  document.getElementById('searchInput').value = '';
  document.getElementById('statusFilter').value = '';
  loadApplications();
}

// ── Status Update ─────────────────────────────────────────────

async function updateStatus(id, status) {
  await fetch(`/api/applications/${id}`, {
    method: 'PUT',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({status}),
  });
  loadAnalytics();
}

// ── Delete ────────────────────────────────────────────────────

async function deleteApp(id) {
  if (!confirm('Delete this application?')) return;
  await fetch(`/api/applications/${id}`, {method:'DELETE'});
  await loadApplications();
  await loadAnalytics();
  showToast('Application deleted');
}

// ── Add / Edit Modal ──────────────────────────────────────────

function openAddModal() {
  document.getElementById('modalTitle').textContent = 'Add Application';
  document.getElementById('appForm').reset();
  document.getElementById('formId').value = '';
  document.getElementById('formAppliedAt').value = localDatetimeNow();
  openModal('appModal');
}

function openEditModal(id) {
  const app = applications.find(a => a.id === id);
  if (!app) return;
  document.getElementById('modalTitle').textContent = 'Edit Application';
  document.getElementById('formId').value = app.id;
  document.getElementById('formCompany').value = app.company || '';
  document.getElementById('formTitle').value = app.job_title || '';
  document.getElementById('formLocation').value = app.location || '';
  document.getElementById('formSource').value = app.source || '';
  document.getElementById('formStatus').value = app.status || 'Applied';
  document.getElementById('formResume').value = app.resume_folder || '';
  document.getElementById('formUrl').value = app.job_url || '';
  document.getElementById('formNotes').value = app.notes || '';
  if (app.applied_at) {
    try {
      document.getElementById('formAppliedAt').value = new Date(app.applied_at).toISOString().slice(0,16);
    } catch(e) {}
  }
  openModal('appModal');
}

async function saveApplication(e) {
  e.preventDefault();
  const id = document.getElementById('formId').value;
  const data = {
    company:       document.getElementById('formCompany').value.trim(),
    job_title:     document.getElementById('formTitle').value.trim(),
    location:      document.getElementById('formLocation').value.trim() || 'Not specified',
    source:        document.getElementById('formSource').value,
    status:        document.getElementById('formStatus').value,
    resume_folder: document.getElementById('formResume').value.trim(),
    job_url:       document.getElementById('formUrl').value.trim(),
    notes:         document.getElementById('formNotes').value.trim(),
    applied_at:    document.getElementById('formAppliedAt').value
                     ? new Date(document.getElementById('formAppliedAt').value).toISOString()
                     : new Date().toISOString(),
  };

  const method = id ? 'PUT' : 'POST';
  const url    = id ? `/api/applications/${id}` : '/api/applications';

  const res = await fetch(url, {
    method,
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(data),
  });
  const json = await res.json();

  if (json.success === false && !id) {
    showToast('Duplicate entry or error', 'error');
    return;
  }
  closeModal('appModal');
  await loadApplications();
  await loadAnalytics();
  showToast(id ? 'Application updated' : 'Application added', 'success');
}

// ── Resume Folder Picker ──────────────────────────────────────

let folderPickTarget = null; // 'form' | app_id

async function openFolderPicker(appId = 'form') {
  folderPickTarget = appId;
  const res = await fetch('/api/resume-folders');
  resumeFolders = await res.json();
  renderFolderList(resumeFolders);
  document.getElementById('folderSearch').value = '';
  openModal('folderModal');
}

function assignResume(id) { openFolderPicker(id); }

function renderFolderList(folders) {
  const list = document.getElementById('folderList');
  if (!folders.length) {
    list.innerHTML = '<p class="text-gray-500 text-xs p-2">No folders found. Configure your resume folder path in Setup.</p>';
    return;
  }
  list.innerHTML = folders.map(f =>
    `<div class="folder-item" onclick="pickFolder('${esc(f)}')">${esc(f)}</div>`
  ).join('');
}

function filterFolders() {
  const q = document.getElementById('folderSearch').value.toLowerCase();
  renderFolderList(resumeFolders.filter(f => f.toLowerCase().includes(q)));
}

async function pickFolder(name) {
  if (folderPickTarget === 'form') {
    document.getElementById('formResume').value = name;
  } else {
    await fetch(`/api/applications/${folderPickTarget}`, {
      method: 'PUT',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({resume_folder: name}),
    });
    await loadApplications();
    showToast(`Resume folder assigned: ${name}`, 'success');
  }
  closeModal('folderModal');
}

// ── Email Sync ────────────────────────────────────────────────

async function autoAssignResumes() {
  showToast('Auto-assigning resumes…', 'info');
  try {
    const res = await fetch('/api/auto-assign-resumes', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      showToast(`Assigned ${data.assigned} resume(s) to applications`, 'success');
      loadApplications();
    } else {
      showToast(data.error || 'Auto-assign failed', 'error');
    }
  } catch (e) {
    showToast('Auto-assign failed', 'error');
  }
}

async function syncEmails(force = false) {
  const btn = document.getElementById('syncBtn');
  const icon = document.getElementById('syncIcon');
  btn.disabled = true;
  icon.textContent = '⟳';
  icon.style.animation = 'spin 1s linear infinite';
  btn.classList.add('opacity-70');
  if (force) showToast('Full resync started — scanning all emails…', 'warning');

  try {
    const res = await fetch('/api/sync', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({force}),
    });
    const data = await res.json();

    if (data.setup_required) {
      openSetup();
      showSetupTab('gmail');
      showToast('Gmail not set up yet — see setup guide', 'warning');
      return;
    }
    if (data.reauth_required) {
      showToast('Gmail session expired — redirecting to sign in again…', 'warning');
      setTimeout(() => { window.location.href = '/logout'; }, 2000);
      return;
    }
    if (data.error) {
      showToast(`Sync error: ${data.error}`, 'error');
      return;
    }

    const parts = [];
    if (data.new_applications) parts.push(`${data.new_applications} new`);
    if (data.status_updates)   parts.push(`${data.status_updates} status update${data.status_updates !== 1 ? 's' : ''}`);
    const summary = parts.length ? parts.join(', ') : 'no new changes';
    showToast(`Sync complete — ${summary}`, 'success');
    await loadApplications();
    await loadAnalytics();
    loadSyncStatus();
  } catch (e) {
    showToast('Sync failed — check server logs', 'error');
  } finally {
    btn.disabled = false;
    icon.style.animation = '';
    icon.textContent = '⟳';
    btn.classList.remove('opacity-70');
  }
}

// ── Setup Modal ───────────────────────────────────────────────

async function openSetup() {
  // Load current config
  const res = await fetch('/api/config');
  const cfg = await res.json();
  document.getElementById('cfgResume').value = cfg.resume_folder || '';
  document.getElementById('cfgDays').value   = cfg.sync_days_back || 90;

  // Check credentials
  const credsRes = await fetch('/api/credentials-check');
  const creds = await credsRes.json();
  const credIcon = document.getElementById('credIcon');
  const credText = document.getElementById('credText');
  if (creds.token_saved) {
    credIcon.textContent = '✅';
    credText.textContent = 'Gmail authenticated — ready to sync';
    credText.className = 'text-emerald-400';
  } else if (creds.credentials_json) {
    credIcon.textContent = '🔑';
    credText.textContent = 'credentials.json found — click Sync to authenticate';
    credText.className = 'text-amber-400';
  } else {
    credIcon.textContent = '❌';
    credText.textContent = 'credentials.json missing — see Gmail Setup Guide tab';
    credText.className = 'text-rose-400';
  }

  showSetupTab('config');
  openModal('setupModal');
}

async function saveConfig() {
  const data = {
    resume_folder:  document.getElementById('cfgResume').value.trim(),
    sync_days_back: parseInt(document.getElementById('cfgDays').value) || 90,
  };
  await fetch('/api/config', {
    method: 'PUT',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify(data),
  });
  closeModal('setupModal');
  showToast('Configuration saved', 'success');
}

function showSetupTab(tab) {
  ['config','gmail'].forEach(t => {
    document.getElementById(`setup-${t}`).classList.toggle('hidden', t !== tab);
    document.getElementById(`tab-${t}`).classList.toggle('active', t === tab);
  });
}

// ── Charts ────────────────────────────────────────────────────

function renderCharts(data) {
  renderDailyChart(data.daily);
  renderStatusChart(data.status);
}

const chartDefaults = {
  color: '#9ca3af',
  plugins: {
    legend: { labels: { color: '#9ca3af', font: { size: 11 } } },
    tooltip: { backgroundColor: '#1f2937', titleColor: '#f9fafb', bodyColor: '#d1d5db' },
  },
  scales: {
    x: { ticks: { color: '#6b7280', font: {size:10} }, grid: { color: '#1f2937' } },
    y: { ticks: { color: '#6b7280', font: {size:10} }, grid: { color: '#1f2937' }, beginAtZero: true },
  },
};

function destroyChart(id) {
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
}

function renderDailyChart(daily) {
  destroyChart('daily');
  const map = {};
  daily.forEach(d => { map[d.date] = d.count; });
  const labels = [], values = [];
  for (let i = 29; i >= 0; i--) {
    const iso = new Date(Date.now() - i * 864e5).toISOString().slice(0, 10);
    const d = new Date(iso + 'T00:00:00');
    labels.push(d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }));
    values.push(map[iso] || 0);
  }
  charts.daily = new Chart(document.getElementById('dailyChart'), {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Applications',
        data: values,
        backgroundColor: '#3b82f680',
        borderColor: '#3b82f6',
        borderWidth: 1,
        borderRadius: 4,
        barPercentage: 0.85,
        categoryPercentage: 0.9,
      }],
    },
    options: {
      ...chartDefaults,
      plugins: { ...chartDefaults.plugins, legend: { display: false } },
      scales: {
        x: {
          ticks: {
            color: '#d1d5db',
            font: { size: 11 },
            maxRotation: 45,
            autoSkip: true,
            maxTicksLimit: 15,
          },
          grid: { color: '#1f2937' },
        },
        y: {
          ticks: {
            color: '#d1d5db',
            font: { size: 11 },
            stepSize: 1,
            precision: 0,
          },
          grid: { color: '#374151' },
          beginAtZero: true,
        },
      },
    },
  });
}

function renderStatusChart(status) {
  destroyChart('status');
  const labels = status.map(s => s.status);
  const values = status.map(s => s.count);
  const colors = labels.map(l => STATUS_COLORS[l] || '#6b7280');
  charts.status = new Chart(document.getElementById('statusChart'), {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderColor: '#111827', borderWidth: 2 }],
    },
    options: {
      plugins: chartDefaults.plugins,
      cutout: '60%',
    },
  });
}


// ── Modal helpers ─────────────────────────────────────────────

function openModal(id) {
  document.getElementById(id).classList.remove('hidden');
  document.body.style.overflow = 'hidden';
}

function closeModal(id) {
  document.getElementById(id).classList.add('hidden');
  document.body.style.overflow = '';
}

// Close on overlay click
document.querySelectorAll('.modal-overlay').forEach(el => {
  el.addEventListener('click', e => {
    if (e.target === el) closeModal(el.id);
  });
});

// ── Toast ─────────────────────────────────────────────────────

let toastTimer = null;
function showToast(msg, type = 'success') {
  clearTimeout(toastTimer);
  const el = document.getElementById('toast');
  const inner = document.getElementById('toastInner');
  const colors = { success: 'bg-emerald-700', error: 'bg-rose-700', warning: 'bg-amber-700' };
  inner.className = `px-5 py-3 rounded-xl shadow-xl text-sm font-medium text-white ${colors[type] || 'bg-gray-700'}`;
  inner.textContent = msg;
  el.classList.remove('hidden');
  toastTimer = setTimeout(() => el.classList.add('hidden'), 3500);
}

// ── Utilities ─────────────────────────────────────────────────

function localDatetimeNow() {
  const d = new Date();
  d.setMinutes(d.getMinutes() - d.getTimezoneOffset());
  return d.toISOString().slice(0,16);
}

// ── CSS animation for sync spinner ───────────────────────────

const style = document.createElement('style');
style.textContent = `@keyframes spin { to { transform: rotate(360deg); } }`;
document.head.appendChild(style);
