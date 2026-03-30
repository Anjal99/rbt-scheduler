/**
 * Main app - routing, event handlers, page switching.
 */
const App = {
    currentPage: 'dashboard',
    scheduleData: null,

    currentUser: null,

    async init() {
        // Check auth first
        try {
            const res = await fetch('/api/auth/me');
            if (!res.ok) {
                window.location.href = '/login';
                return;
            }
            this.currentUser = await res.json();
        } catch (e) {
            window.location.href = '/login';
            return;
        }

        // Show user info in nav
        this._setupUserNav();

        this._setupNav();
        this._setupDayTabs();
        this._setupDashboard();
        this._setupSchedulePage();
        this._setupValidation();

        // Init modals
        AssignmentModal.init();
        TherapistModal.init();

        // Handle initial hash
        const hash = location.hash.replace('#', '') || 'dashboard';
        this.navigate(hash);

        // Load dashboard data
        this.refreshDashboard();
    },

    _setupUserNav() {
        const userEl = document.getElementById('nav-user');
        if (userEl && this.currentUser) {
            userEl.innerHTML = `<span class="nav-user-name">${this.currentUser.name}</span>`;
            if (this.currentUser.role === 'admin') {
                userEl.innerHTML += `<a href="#users" class="nav-link" data-page="users" style="font-size:.75rem">Users</a>`;
            }
            userEl.innerHTML += `<button class="nav-logout" id="logout-btn">Logout</button>`;
            document.getElementById('logout-btn').addEventListener('click', async () => {
                await fetch('/api/auth/logout', { method: 'POST' });
                window.location.href = '/login';
            });
        }
    },

    // --- Navigation ---
    _setupNav() {
        document.querySelectorAll('[data-page]').forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                this.navigate(link.dataset.page);
            });
        });
        window.addEventListener('hashchange', () => {
            const hash = location.hash.replace('#', '') || 'dashboard';
            this.navigate(hash);
        });
    },

    navigate(page) {
        this.currentPage = page;
        location.hash = page;

        // Update nav links
        document.querySelectorAll('.nav-link, .bottom-link').forEach(l => {
            l.classList.toggle('active', l.dataset.page === page);
        });

        // Show page
        document.querySelectorAll('.page').forEach(p => {
            p.classList.toggle('active', p.id === `page-${page}`);
        });

        // Load page data
        if (page === 'schedule') this._loadSchedule();
        if (page === 'therapists') this._loadTherapists();
        if (page === 'clients') this._loadClients();
        if (page === 'validation') this._loadValidation();
    },

    // --- Dashboard ---
    _setupDashboard() {
        // Upload button
        document.getElementById('upload-file').addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            this.showLoading('Importing data...');
            const statusEl = document.getElementById('upload-status');
            try {
                const [tResult, cResult] = await Promise.all([
                    API.importTherapists(file),
                    API.uploadClients(file),
                ]);

                statusEl.style.display = '';
                statusEl.className = 'upload-status success';
                statusEl.innerHTML = `<strong>Import complete:</strong> ${tResult.added} new therapists (${tResult.total} total), ${cResult.added} clients loaded`;

                this.toast(`Imported ${tResult.added} therapists, ${cResult.added} clients`, 'success');
                this.refreshDashboard();
                // Refresh modal dropdowns
                AssignmentModal.init();
            } catch (err) {
                statusEl.style.display = '';
                statusEl.className = 'upload-status error';
                statusEl.innerHTML = `<strong>Import failed:</strong> ${err.message}`;
                this.toast('Upload failed: ' + err.message, 'error');
            } finally {
                this.hideLoading();
                e.target.value = '';
            }
        });

        // Reset button
        document.getElementById('reset-btn').addEventListener('click', async () => {
            if (!confirm('This will delete ALL therapists, clients, and schedule data. Are you sure?')) return;

            this.showLoading('Resetting...');
            try {
                await API.postJSON('/api/schedule/reset');
                document.getElementById('upload-status').style.display = 'none';
                this.toast('All data cleared', 'success');
                this.refreshDashboard();
                AssignmentModal.init();
            } catch (err) {
                this.toast('Reset failed: ' + err.message, 'error');
            } finally {
                this.hideLoading();
            }
        });

        // Generate button
        document.getElementById('generate-btn').addEventListener('click', async () => {
            this.showLoading('Generating schedule...');
            try {
                const data = await API.generateSchedule();
                this.scheduleData = data;
                this._updateDashboardStats(data.stats);
                this._updateDashboardWarnings(data.warnings);
                this.toast(`Generated ${data.stats.total_assignments} assignments (${data.stats.coverage_pct.toFixed(1)}% coverage)`, 'success');
            } catch (err) {
                this.toast('Generation failed: ' + err.message, 'error');
            } finally {
                this.hideLoading();
            }
        });
    },

    async refreshDashboard() {
        try {
            const [tCount, cCount, stats] = await Promise.all([
                API.getTherapistCount(),
                API.getClientCount(),
                API.getScheduleStats().catch(() => null),
            ]);
            document.getElementById('stat-therapists').textContent = tCount.count;
            document.getElementById('stat-clients').textContent = cCount.count;

            if (stats && stats.total_assignments > 0) {
                document.getElementById('stat-assignments').textContent = stats.total_assignments;
                document.getElementById('stat-hours').textContent = stats.total_hours + 'h';
                document.getElementById('stat-coverage').textContent = '--';

                // Run validation for warning count
                try {
                    const val = await API.validateSchedule();
                    const warnCount = (val.counts.errors || 0) + (val.counts.critical || 0) + (val.counts.warnings || 0);
                    document.getElementById('stat-warnings').textContent = warnCount;
                    const card = document.getElementById('stat-warnings-card');
                    card.className = 'stat-card' + (warnCount > 0 ? ' warning' : ' success');
                } catch(e) {}
            } else {
                document.getElementById('stat-assignments').textContent = '0';
                document.getElementById('stat-hours').textContent = '--';
                document.getElementById('stat-coverage').textContent = '--';
                document.getElementById('stat-warnings').textContent = '--';
            }
        } catch (e) {
            console.error('Dashboard refresh failed:', e);
        }
    },

    _updateDashboardStats(stats) {
        if (!stats) return;
        document.getElementById('stat-therapists').textContent = stats.total_therapists;
        document.getElementById('stat-clients').textContent = stats.total_clients;
        document.getElementById('stat-assignments').textContent = stats.total_assignments;
        document.getElementById('stat-hours').textContent = stats.total_hours_assigned.toFixed(0) + 'h';
        document.getElementById('stat-coverage').textContent = stats.coverage_pct.toFixed(1) + '%';
        document.getElementById('stat-warnings').textContent = stats.warnings_count;
        const card = document.getElementById('stat-warnings-card');
        card.className = 'stat-card' + (stats.warnings_count > 0 ? ' warning' : ' success');
    },

    _updateDashboardWarnings(warnings) {
        const panel = document.getElementById('dashboard-warnings');
        const list = document.getElementById('warnings-list');
        if (!warnings || !warnings.length) {
            panel.style.display = 'none';
            return;
        }
        panel.style.display = '';
        let html = '';
        warnings.forEach(w => {
            let cls = 'info';
            if (w.toLowerCase().includes('critical')) cls = 'critical';
            else if (w.toLowerCase().includes('high workload')) cls = 'warning';
            else if (w.toLowerCase().includes('coverage gap')) cls = 'error';
            html += `<div class="warning-item ${cls}"><div class="warning-dot"></div><div>${w}</div></div>`;
        });
        list.innerHTML = html;
    },

    // --- Schedule Page ---
    _setupSchedulePage() {
        document.getElementById('export-excel-btn').addEventListener('click', () => {
            window.location.href = API.exportExcelURL();
        });

        // Filter dropdowns
        document.getElementById('filter-therapist').addEventListener('change', (e) => {
            ScheduleView.filterTherapist = e.target.value;
            ScheduleView.render(document.getElementById('schedule-container'));
        });
        document.getElementById('filter-client').addEventListener('change', (e) => {
            ScheduleView.filterClient = e.target.value;
            ScheduleView.render(document.getElementById('schedule-container'));
        });
    },

    _setupDayTabs() {
        document.querySelectorAll('.day-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.day-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                ScheduleView.setDay(tab.dataset.day);
            });
        });
    },

    async _loadSchedule() {
        await ScheduleView.load();
        ScheduleView.render(document.getElementById('schedule-container'));
    },

    // --- Therapists Page ---
    async _loadTherapists() {
        await TherapistView.load();
        TherapistView.render(document.getElementById('therapists-content'));
    },

    // --- Clients Page ---
    async _loadClients() {
        await ClientView.load();
        ClientView.render(document.getElementById('clients-content'));
    },

    // --- Validation Page ---
    _setupValidation() {
        document.getElementById('validate-btn').addEventListener('click', async () => {
            await this._loadValidation();
        });
    },

    async _loadValidation() {
        try {
            await ValidationView.runValidation();
            ValidationView.render(
                document.getElementById('validation-stats'),
                document.getElementById('validation-content')
            );
        } catch (e) {
            document.getElementById('validation-content').innerHTML =
                '<div class="empty-state">No schedule to validate. Generate a schedule first.</div>';
        }
    },

    // --- Utilities ---
    showLoading(text) {
        const el = document.getElementById('loading');
        el.querySelector('.loading-text').textContent = text || 'Loading...';
        el.style.display = '';
    },

    hideLoading() {
        document.getElementById('loading').style.display = 'none';
    },

    toast(message, type = '') {
        const container = document.getElementById('toast-container');
        const el = document.createElement('div');
        el.className = `toast ${type}`;
        el.textContent = message;
        container.appendChild(el);
        setTimeout(() => { el.remove(); }, 4000);
    },
};

// Boot
document.addEventListener('DOMContentLoaded', () => App.init());
