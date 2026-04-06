/**
 * Schedule view — clean daily planner layout with editable cards.
 */
const ScheduleView = {
    assignments: [],
    currentDay: 'Mon',
    clientColors: {},
    colorIndex: 0,
    _viewMode: 'therapist',

    COLORS: [
        '#3b82f6', '#8b5cf6', '#ec4899', '#f59e0b', '#10b981',
        '#06b6d4', '#ef4444', '#84cc16', '#f97316', '#6366f1',
        '#14b8a6', '#d946ef', '#0ea5e9', '#e11d48', '#a855f7',
        '#65a30d', '#0891b2', '#dc2626', '#7c3aed', '#059669',
    ],

    getClientColor(client) {
        if (!this.clientColors[client]) {
            this.clientColors[client] = this.COLORS[this.colorIndex % this.COLORS.length];
            this.colorIndex++;
        }
        return this.clientColors[client];
    },

    parseTime(val) {
        if (!val) return null;
        const s = String(val);
        const m = s.match(/^(\d{1,2}):(\d{2})/);
        if (m) return { h: parseInt(m[1]), m: parseInt(m[2]) };
        return null;
    },

    timeToMinutes(t) { return t ? t.h * 60 + t.m : 0; },

    formatTime(t) {
        if (!t) return '';
        let h = t.h, ampm = 'am';
        if (h >= 12) { ampm = 'pm'; if (h > 12) h -= 12; }
        if (h === 0) h = 12;
        return t.m === 0 ? `${h}${ampm}` : `${h}:${String(t.m).padStart(2, '0')}${ampm}`;
    },

    // HH:MM string for time inputs
    toInputTime(val) {
        const t = this.parseTime(val);
        if (!t) return '';
        return `${String(t.h).padStart(2,'0')}:${String(t.m).padStart(2,'0')}`;
    },

    async load() {
        try { this.assignments = await API.getSchedule(); }
        catch (e) { this.assignments = []; }
    },

    filterTherapist: '',
    filterClient: '',

    render(container) {
        if (!this.assignments.length) {
            container.innerHTML = '<div class="schedule-empty">No schedule generated yet. Go to Dashboard to generate.</div>';
            document.getElementById('hours-sidebar').style.display = 'none';
            return;
        }

        const allClients = [...new Set(this.assignments.map(a => a.Client))].sort();
        allClients.forEach(c => this.getClientColor(c));

        // Populate filter dropdowns
        this._populateFilters();

        // Apply filters
        let dayAssignments = this.assignments.filter(a => a.Day === this.currentDay);
        if (this.filterTherapist) {
            dayAssignments = dayAssignments.filter(a => a.Therapist === this.filterTherapist);
        }
        if (this.filterClient) {
            dayAssignments = dayAssignments.filter(a => a.Client === this.filterClient);
        }

        const weeklyHours = this._calcWeeklyHours();

        let html = '';

        // Color legend
        html += this._renderLegend(allClients);

        html += `<div class="view-toggle">
            <button class="view-btn ${this._viewMode === 'therapist' ? 'active' : ''}" data-view="therapist">By Therapist</button>
            <button class="view-btn ${this._viewMode === 'client' ? 'active' : ''}" data-view="client">By Client</button>
        </div>`;

        if (this._viewMode === 'client') {
            html += this._renderByClient(dayAssignments, weeklyHours);
        } else {
            html += this._renderByTherapist(dayAssignments, weeklyHours);
        }

        container.innerHTML = html;
        this._bindEvents(container);
        this._renderHoursSidebar(weeklyHours);

        // Initialize drag-and-drop
        if (typeof ScheduleDrag !== 'undefined') {
            ScheduleDrag.init(container);
        }
    },

    _populateFilters() {
        const tSelect = document.getElementById('filter-therapist');
        const cSelect = document.getElementById('filter-client');
        if (!tSelect || !cSelect) return;

        const therapists = [...new Set(this.assignments.map(a => a.Therapist))].sort();
        const clients = [...new Set(this.assignments.map(a => a.Client))].sort();

        // Only repopulate if options changed
        if (tSelect.options.length !== therapists.length + 1) {
            const curT = this.filterTherapist;
            tSelect.innerHTML = '<option value="">All Therapists</option>' +
                therapists.map(t => `<option value="${t}"${t === curT ? ' selected' : ''}>${t}</option>`).join('');
        }
        if (cSelect.options.length !== clients.length + 1) {
            const curC = this.filterClient;
            cSelect.innerHTML = '<option value="">All Clients</option>' +
                clients.map(c => `<option value="${c}"${c === curC ? ' selected' : ''}>${c}</option>`).join('');
        }

        // Restore selected values
        tSelect.value = this.filterTherapist;
        cSelect.value = this.filterClient;
    },

    _bindEvents(container) {
        // View toggle
        container.querySelectorAll('.view-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this._viewMode = btn.dataset.view;
                this.render(container);
            });
        });
        // Lock toggle buttons
        container.querySelectorAll('.lock-toggle-btn').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation(); // Don't open modal
                const id = parseInt(btn.dataset.assignmentId);
                const nextLock = btn.dataset.nextLock || null;
                try {
                    await API.setLockType(id, nextLock);
                    const label = nextLock === 'soft' ? 'Soft locked' : nextLock === 'hard' ? 'Hard locked' : 'Unlocked';
                    App.toast(label, 'success');
                    await this.refresh();
                } catch (err) {
                    App.toast('Lock failed: ' + err.message, 'error');
                }
            });
        });
        // Card clicks → edit
        container.querySelectorAll('.planner-card[data-id]').forEach(card => {
            card.addEventListener('click', () => {
                const id = parseInt(card.dataset.id);
                const assignment = this.assignments.find(a => a.id === id);
                if (assignment) AssignmentModal.openEdit(assignment);
            });
        });
    },

    _renderByTherapist(dayAssignments, weeklyHours) {
        const byTherapist = {};
        dayAssignments.forEach(a => {
            if (!byTherapist[a.Therapist]) byTherapist[a.Therapist] = [];
            byTherapist[a.Therapist].push(a);
        });
        const therapists = Object.keys(byTherapist).sort();

        if (!therapists.length) {
            return '<div class="schedule-empty">No assignments for ' + this.currentDay + '</div>';
        }

        let html = '<div class="planner-list">';
        therapists.forEach(therapist => {
            const assignments = byTherapist[therapist].sort((a, b) =>
                this.timeToMinutes(this.parseTime(a.Start)) - this.timeToMinutes(this.parseTime(b.Start))
            );
            const weekly = weeklyHours[therapist] || 0;
            const dayHours = this._calcDayHours(assignments);
            const statusClass = weekly >= 35 ? 'status-over' : weekly >= 30 ? 'status-warn' : 'status-ok';

            html += `<div class="planner-row">`;
            html += `<div class="planner-header">`;
            html += `<div class="planner-name">${therapist}</div>`;
            html += `<div class="planner-meta">`;
            html += `<span class="planner-day-hours">${dayHours.toFixed(1)}h today</span>`;
            html += `<span class="planner-weekly ${statusClass}">${weekly.toFixed(1)}h/wk</span>`;
            html += `</div></div>`;
            html += `<div class="planner-cards">`;
            assignments.forEach(a => { html += this._renderCard(a, 'client'); });
            html += `</div></div>`;
        });
        html += '</div>';
        return html;
    },

    _renderByClient(dayAssignments, weeklyHours) {
        const byClient = {};
        dayAssignments.forEach(a => {
            if (!byClient[a.Client]) byClient[a.Client] = [];
            byClient[a.Client].push(a);
        });
        const clients = Object.keys(byClient).sort();

        if (!clients.length) {
            return '<div class="schedule-empty">No assignments for ' + this.currentDay + '</div>';
        }

        let html = '<div class="planner-list">';
        clients.forEach(client => {
            const assignments = byClient[client].sort((a, b) =>
                this.timeToMinutes(this.parseTime(a.Start)) - this.timeToMinutes(this.parseTime(b.Start))
            );
            const color = this.getClientColor(client);
            const dayHours = this._calcDayHours(assignments);
            const therapists = [...new Set(assignments.map(a => a.Therapist))];

            html += `<div class="planner-row">`;
            html += `<div class="planner-header">`;
            html += `<div class="planner-name" style="color:${color}">${client}</div>`;
            html += `<div class="planner-meta">`;
            html += `<span class="planner-day-hours">${dayHours.toFixed(1)}h today</span>`;
            html += `<span class="text-muted">${therapists.length} therapist${therapists.length > 1 ? 's' : ''}</span>`;
            html += `</div></div>`;
            html += `<div class="planner-cards">`;
            assignments.forEach(a => { html += this._renderCard(a, 'therapist'); });
            html += `</div></div>`;
        });
        html += '</div>';
        return html;
    },

    _lockIcon(lockType) {
        if (lockType === 'hard') {
            return '<svg class="card-lock card-lock-hard" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>';
        }
        if (lockType === 'soft') {
            return '<svg class="card-lock card-lock-soft" viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>';
        }
        return '';
    },

    _renderCard(a, showField) {
        const start = this.parseTime(a.Start);
        const end = this.parseTime(a.End);
        const color = this.getClientColor(a.Client);
        const duration = start && end ? ((this.timeToMinutes(end) - this.timeToMinutes(start)) / 60).toFixed(1) : '?';
        const locIcon = (a.Location || '').toLowerCase().includes('home') ? 'H' : 'C';
        const locClass = locIcon === 'H' ? 'loc-home' : 'loc-clinic';
        const label = showField === 'client' ? a.Client : a.Therapist;
        const labelStyle = showField === 'client' ? ` style="color:${color}"` : '';
        const lockType = a.LockType || '';
        const lockedClass = lockType === 'hard' ? ' locked-hard' : lockType === 'soft' ? ' locked-soft' : '';

        let html = `<div class="planner-card${lockedClass}" data-id="${a.id || ''}" data-lock="${lockType}" style="border-left: 4px solid ${color}">`;
        html += `<div class="card-top">`;
        html += `<span class="${showField === 'client' ? 'card-client' : 'card-therapist'}"${labelStyle}>${label}</span>`;
        html += `<div class="card-top-right">`;
        html += this._lockIcon(lockType);
        html += `<span class="card-loc ${locClass}">${locIcon}</span>`;
        if (a.id) {
            const nextLock = !lockType ? 'soft' : lockType === 'soft' ? 'hard' : null;
            const btnTitle = !lockType ? 'Lock (soft)' : lockType === 'soft' ? 'Lock (hard)' : 'Unlock';
            const btnIcon = !lockType ? '&#128275;' : lockType === 'soft' ? '&#128274;' : '&#128275;';
            html += `<button class="lock-toggle-btn" data-assignment-id="${a.id}" data-next-lock="${nextLock || ''}" title="${btnTitle}">${btnIcon}</button>`;
        }
        html += `</div></div>`;
        html += `<div class="card-time">${this.formatTime(start)} - ${this.formatTime(end)}</div>`;
        html += `<div class="card-detail">${duration}h &middot; ${a.Type || 'Recurring'}</div>`;
        html += `</div>`;
        return html;
    },

    _renderLegend(clients) {
        if (!clients.length) return '';
        let html = '<div class="color-legend">';
        clients.forEach(c => {
            const color = this.getClientColor(c);
            html += `<div class="legend-item"><div class="legend-dot" style="background:${color}"></div>${c}</div>`;
        });
        html += '</div>';
        return html;
    },

    _calcDayHours(assignments) {
        let total = 0;
        assignments.forEach(a => {
            const s = this.parseTime(a.Start);
            const e = this.parseTime(a.End);
            if (s && e) total += (this.timeToMinutes(e) - this.timeToMinutes(s)) / 60;
        });
        return total;
    },

    _calcWeeklyHours() {
        const hours = {};
        this.assignments.forEach(a => {
            const s = this.parseTime(a.Start);
            const e = this.parseTime(a.End);
            if (s && e) hours[a.Therapist] = (hours[a.Therapist] || 0) + (this.timeToMinutes(e) - this.timeToMinutes(s)) / 60;
        });
        return hours;
    },

    _renderHoursSidebar(weeklyHours) {
        const sidebar = document.getElementById('hours-sidebar');
        const list = document.getElementById('hours-list');
        if (!this.assignments.length) { sidebar.style.display = 'none'; return; }
        sidebar.style.display = '';

        const sorted = Object.entries(weeklyHours).sort((a, b) => b[1] - a[1]);
        let html = '';
        sorted.forEach(([name, hrs]) => {
            const cls = hrs >= 35 ? 'red' : hrs >= 30 ? 'yellow' : 'green';
            const pct = Math.min((hrs / 35) * 100, 100);
            html += `<div class="hours-item">`;
            html += `<span class="hours-item-name" title="${name}">${name}</span>`;
            html += `<div class="hours-item-bar"><div class="hours-item-bar-fill ${cls}" style="width:${pct}%"></div></div>`;
            html += `<span class="hours-item-value ${cls}">${hrs.toFixed(1)}h</span>`;
            html += `</div>`;
        });
        list.innerHTML = html;
    },

    setDay(day) {
        this.currentDay = day;
        this.render(document.getElementById('schedule-container'));
    },

    async refresh() {
        await this.load();
        this.render(document.getElementById('schedule-container'));
    },
};
