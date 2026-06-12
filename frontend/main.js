/**
 * Main Oscilloscope Controller
 * Handles theme toggling, real-time metrics stream, and DLQ management.
 */

// --- 1. THEME & NAVBAR LOGIC ---
const navbarToggler = document.querySelector('.navbar-toggler');
const navbarCollapse = document.getElementById('navbarNav');
const themeToggle = document.getElementById('themeToggle');
const themeIcon = document.getElementById('themeIcon');
const htmlElement = document.documentElement;

// Navbar auto-close on link click
if (navbarToggler && navbarCollapse) {
    navbarToggler.addEventListener('click', () => navbarCollapse.classList.toggle('show'));
    navbarCollapse.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => navbarCollapse.classList.remove('show'));
    });
}

// Icons
const sunIcon = `<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>`;
const moonIcon = `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>`;

// Theme Initialization
const savedTheme = localStorage.getItem('bs-theme') || 'dark';
htmlElement.setAttribute('data-bs-theme', savedTheme);
themeIcon.innerHTML = savedTheme === 'light' ? moonIcon : sunIcon;

themeToggle.addEventListener('click', () => {
    const currentTheme = htmlElement.getAttribute('data-bs-theme');
    let nextTheme = currentTheme === 'light' ? 'dark' : 'light';
    htmlElement.setAttribute('data-bs-theme', nextTheme);
    themeIcon.innerHTML = nextTheme === 'light' ? sunIcon : moonIcon;
    localStorage.setItem('bs-theme', nextTheme);
});

// --- 2. BACKEND INTEGRATION ---
const API_BASE = "http://127.0.0.1:8000/api";

// Self-healing SSE connection
function connectSSE() {
    const eventSource = new EventSource(`${API_BASE}/sse/stream`);

    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if(data.error) return;
        
        for (const [status, count] of Object.entries(data)) {
            const el = document.getElementById(`count-${status}`);
            if (el) el.innerText = count;
        }
    };

    eventSource.onerror = function() {
        console.warn("SSE connection lost. Reconnecting in 5s...");
        eventSource.close();
        setTimeout(connectSSE, 5000);
    };
}

// WAT Timezone Converter
function formatWAT(utcString) {
    const date = new Date(utcString);
    return date.toLocaleString('en-NG', {
        timeZone: 'Africa/Lagos',
        hour12: true, 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit'
    });
}

// DLQ Fetch & Render
async function fetchDLQ() {
    try {
        const res = await fetch(`${API_BASE}/dlq`);
        const deadLetters = await res.json();
        const tbody = document.getElementById("dlq-body");
        tbody.innerHTML = ""; 

        if(deadLetters.length === 0) {
            tbody.innerHTML = `<tr><td colspan='5' class='text-center py-4 text-muted'>Queue is clean.</td></tr>`;
            return;
        }

        deadLetters.forEach(dlq => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td class="text-nowrap">${formatWAT(dlq.created_at)}</td>
                <td><code class="text-muted">${dlq.original_job_id}</code></td>
                <td><span class="badge bg-secondary">${dlq.type}</span></td>
                <td class="text-danger-custom fw-medium">${dlq.error_message || 'Unknown Error'}</td>
                <td class="text-end"><button class="btn btn-sm btn-green fw-bold shadow-sm" onclick="retryJob('${dlq.id}')">RETRY</button></td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Failed to fetch DLQ", err);
    }
}

// Action: Retry Job
window.retryJob = async function(dlqId) {
    try {
        await fetch(`${API_BASE}/dlq/${dlqId}/retry`, { method: "POST" });
        fetchDLQ(); 
    } catch (err) {
        console.error("Failed to retry job", err);
    }
}

// Init
connectSSE();
fetchDLQ();
setInterval(fetchDLQ, 5000);