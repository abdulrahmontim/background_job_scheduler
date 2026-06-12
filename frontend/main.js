const API_BASE = "/api";

const sunIcon = `<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>`;
const moonIcon = `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>`;

const savedTheme = localStorage.getItem('bs-theme') || 'dark';
document.documentElement.setAttribute('data-bs-theme', savedTheme);
document.getElementById('themeIcon').innerHTML = savedTheme === 'light' ? moonIcon : sunIcon;

document.getElementById('themeToggle').addEventListener('click', () => {
    const cur = document.documentElement.getAttribute('data-bs-theme');
    const next = cur === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-bs-theme', next);
    document.getElementById('themeIcon').innerHTML = next === 'light' ? sunIcon : moonIcon;
    localStorage.setItem('bs-theme', next);
});

const navbarToggler = document.querySelector('.navbar-toggler');
const navbarCollapse = document.getElementById('navbarNav');
if (navbarToggler && navbarCollapse) {
    navbarToggler.addEventListener('click', () => navbarCollapse.classList.toggle('show'));
    navbarCollapse.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => navbarCollapse.classList.remove('show'));
    });
}

function formatWAT(utcString) {
    if (!utcString) return '-';
    const date = new Date(utcString);
    if (isNaN(date.getTime())) return '-';
    return date.toLocaleString('en-NG', {
        timeZone: 'Africa/Lagos', hour12: true,
        month: 'short', day: 'numeric',
        hour: '2-digit', minute: '2-digit', second: '2-digit'
    });
}

function statusBadge(status) {
    const map = {
        PENDING: 'bg-warning text-dark status-pending',
        PROCESSING: 'bg-primary status-processing',
        COMPLETED: 'bg-success status-completed',
        FAILED: 'bg-danger status-failed',
        CANCELLED: 'bg-secondary status-cancelled'
    };
    return `<span class="badge fs-6 px-3 py-2 ${map[status] || 'bg-secondary'}">${status}</span>`;
}

function intervalLabel(seconds) {
    if (!seconds) return '-';
    if (seconds === 60) return '1 min';
    if (seconds === 300) return '5 min';
    if (seconds === 3600) return '1 hr';
    if (seconds % 3600 === 0) return `${seconds / 3600} hr`;
    if (seconds % 60 === 0) return `${seconds / 60} min`;
    return `${seconds}s`;
}

function showToast(msg, type) {
    const toast = document.getElementById('toast');
    const body = document.getElementById('toastMessage');
    toast.className = `toast align-items-center border-0 text-bg-${type || 'success'}`;
    body.textContent = msg;
    bootstrap.Toast.getOrCreateInstance(toast).show();
}

let sseConnected = false;

function connectSSE() {
    const eventSource = new EventSource(`${API_BASE}/sse/stream`);

    eventSource.onopen = () => {
        sseConnected = true;
    };

    eventSource.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (data.error) return;
        for (const [status, count] of Object.entries(data)) {
            const el = document.getElementById(`count-${status}`);
            if (el) el.innerText = count;
        }
    };

    eventSource.onerror = function () {
        sseConnected = false;
        eventSource.close();
        for (const status of ['PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', 'CANCELLED']) {
            const el = document.getElementById(`count-${status}`);
            if (el) el.innerText = '0';
        }
        setTimeout(connectSSE, 5000);
    };
}

async function fetchJobs() {
    try {
        const res = await fetch(`${API_BASE}/jobs`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const jobs = await res.json();
        const tbody = document.getElementById('jobs-body');
        tbody.innerHTML = '';

        if (jobs.length === 0) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center py-4 text-muted">No jobs found.</td></tr>`;
            return;
        }

        jobs.forEach(job => {
            const tr = document.createElement('tr');
            const canCancel = job.status === 'PENDING' || job.status === 'PROCESSING';
            tr.innerHTML = `
                <td><a href="#" class="text-decoration-none font-monospace small job-id-link" onclick="viewJobDetails('${job.id}')" title="Click to view details">${job.id.substring(0, 8)}...</a></td>
                <td><span class="badge bg-secondary">${job.type}</span></td>
                <td>${job.priority}</td>
                <td>${statusBadge(job.status)}</td>
                <td>${job.retry_count}</td>
                <td class="text-nowrap">${formatWAT(job.scheduled_at)}</td>
                <td>${intervalLabel(job.interval)}</td>
                <td class="text-nowrap">${formatWAT(job.created_at)}</td>
                <td class="text-end">${canCancel ? `<button class="btn btn-sm btn-outline-danger fw-bold" onclick="cancelJob('${job.id}')">Cancel</button>` : '-'}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error('Failed to fetch jobs', err);
    }
}

window.cancelJob = async function (jobId) {
    try {
        const res = await fetch(`${API_BASE}/jobs/${jobId}/cancel`, { method: 'POST' });
        if (!res.ok) {
            const err = await res.json();
            showToast(err.detail || 'Failed to cancel', 'danger');
            return;
        }
        showToast('Job cancelled successfully', 'warning');
        fetchJobs();
    } catch (err) {
        console.error('Failed to cancel job', err);
        showToast('Failed to cancel job', 'danger');
    }
};

window.submitJob = async function () {
    const type = document.getElementById('job-type').value;
    const priority = parseInt(document.querySelector('input[name="job-priority"]:checked')?.value || '2');
    const payloadRaw = document.getElementById('job-payload').value;
    const interval = document.getElementById('job-interval').value;
    const scheduledRaw = document.getElementById('job-scheduled').value;
    const depsRaw = document.getElementById('job-dependencies').value;

    if (!type || !payloadRaw || !scheduledRaw) {
        showToast('Please fill in Type, Payload, and Scheduled Time.', 'danger');
        return;
    }

    let payload;
    try {
        payload = JSON.parse(payloadRaw);
    } catch {
        showToast('Payload must be valid JSON.', 'danger');
        return;
    }

    const scheduledAt = new Date(scheduledRaw).toISOString();

    const dependencies = depsRaw
        .split(',')
        .map(s => s.trim())
        .filter(s => s.length > 0);

    const body = { type, priority, payload, scheduled_at: scheduledAt, dependencies };
    if (interval) body.interval = parseInt(interval);

    try {
        const res = await fetch(`${API_BASE}/jobs`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        if (!res.ok) {
            const err = await res.json();
            showToast(err.detail || 'Failed to create job', 'danger');
            return;
        }
        showToast('Job created successfully!', 'success');
        bootstrap.Modal.getInstance(document.getElementById('createJobModal')).hide();
        document.getElementById('createJobForm').reset();
        fetchJobs();
    } catch (err) {
        console.error('Failed to create job', err);
        showToast('Failed to create job', 'danger');
    }
};

async function fetchDLQ() {
    try {
        const res = await fetch(`${API_BASE}/dlq`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const deadLetters = await res.json();
        const tbody = document.getElementById('dlq-body');
        tbody.innerHTML = '';

        if (deadLetters.length === 0) {
            tbody.innerHTML = `<tr><td colspan="5" class="text-center py-4 text-muted">Queue is clean.</td></tr>`;
            return;
        }

        deadLetters.forEach(dlq => {
            const tr = document.createElement('tr');
            const errMsg = dlq.error_message || 'Unknown Error';
            tr.innerHTML = `
                <td class="text-nowrap">${formatWAT(dlq.failed_at)}</td>
                <td><code class="text-muted">${dlq.original_job_id.substring(0, 8)}...</code></td>
                <td><span class="badge bg-secondary">${dlq.type}</span></td>
                <td><span class="error-cell" title="${errMsg.replace(/"/g, '&quot;')}">${errMsg.length > 80 ? errMsg.substring(0, 80) + '...' : errMsg}</span></td>
                <td class="text-end"><button class="btn btn-sm btn-green fw-bold shadow-sm" onclick="retryJob('${dlq.id}')">RETRY</button></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error('Failed to fetch DLQ', err);
    }
}

window.retryJob = async function (dlqId) {
    try {
        const res = await fetch(`${API_BASE}/dlq/${dlqId}/retry`, { method: 'POST' });
        if (!res.ok) {
            const err = await res.json();
            showToast(err.detail || 'Failed to retry', 'danger');
            return;
        }
        showToast('Job re-queued from DLQ', 'success');
        fetchDLQ();
        fetchJobs();
    } catch (err) {
        console.error('Failed to retry job', err);
    }
};

window.viewJobDetails = async function (jobId) {
    const body = document.getElementById('jobDetailBody');
    body.innerHTML = '<div class="text-center py-4 text-muted">Loading...</div>';
    const modal = new bootstrap.Modal(document.getElementById('jobDetailModal'));
    modal.show();
    try {
        const res = await fetch(`${API_BASE}/jobs/${jobId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const job = await res.json();
        body.innerHTML = `
            <div class="row g-3">
                <div class="col-md-6">
                    <div class="card bg-body-tertiary border p-3 h-100">
                        <h6 class="fw-bold text-muted text-uppercase small mb-2">Identity</h6>
                        <p class="mb-1"><strong>ID:</strong> <code>${job.id}</code></p>
                        <p class="mb-1"><strong>Type:</strong> <span class="badge bg-secondary">${job.type}</span></p>
                        <p class="mb-1"><strong>Status:</strong> ${statusBadge(job.status)}</p>
                        <p class="mb-0"><strong>Interval:</strong> ${intervalLabel(job.interval) || 'None (one-off)'}</p>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card bg-body-tertiary border p-3 h-100">
                        <h6 class="fw-bold text-muted text-uppercase small mb-2">Priority & Scheduling</h6>
                        <p class="mb-1"><strong>Priority:</strong> ${job.priority} ${['(Lowest)', '', '(Highest)'][job.priority - 1] || ''}</p>
                        <p class="mb-1"><strong>Effective Priority:</strong> ${job.effective_priority}</p>
                        <p class="mb-1"><strong>Scheduled:</strong> ${formatWAT(job.scheduled_at)}</p>
                        <p class="mb-0"><strong>Created:</strong> ${formatWAT(job.created_at)}</p>
                    </div>
                </div>
                <div class="col-12">
                    <div class="card bg-body-tertiary border p-3">
                        <h6 class="fw-bold text-muted text-uppercase small mb-2">Retries</h6>
                        <p class="mb-0"><strong>Retry Count:</strong> ${job.retry_count} / 3</p>
                    </div>
                </div>
                <div class="col-12">
                    <div class="card bg-body-tertiary border p-3">
                        <h6 class="fw-bold text-muted text-uppercase small mb-2">Payload</h6>
                        <pre class="mb-0 font-monospace small" style="max-height: 200px; overflow-y: auto;">${JSON.stringify(job.payload, null, 2)}</pre>
                    </div>
                </div>
                ${job.dependencies && job.dependencies.length ? `
                <div class="col-12">
                    <div class="card bg-body-tertiary border p-3">
                        <h6 class="fw-bold text-muted text-uppercase small mb-2">Dependencies</h6>
                        <p class="mb-0 small">${job.dependencies.map(d => `<code>${d}</code>`).join(', ')}</p>
                    </div>
                </div>` : ''}
                ${job.error_message ? `
                <div class="col-12">
                    <div class="card bg-danger bg-opacity-10 border-danger p-3">
                        <h6 class="fw-bold text-danger text-uppercase small mb-2">Error</h6>
                        <pre class="mb-0 font-monospace small text-danger">${job.error_message}</pre>
                    </div>
                </div>` : ''}
            </div>
        `;
    } catch (err) {
        body.innerHTML = `<div class="alert alert-danger mb-0">Failed to load job details: ${err.message}</div>`;
    }
};

connectSSE();
fetchJobs();
fetchDLQ();
setInterval(fetchJobs, 5000);
setInterval(fetchDLQ, 5000);
