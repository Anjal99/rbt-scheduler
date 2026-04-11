/**
 * Therapist list view + add/edit modal.
 */
const TherapistView = {
    therapists: [],
    assignments: [],

    async load() {
        [this.therapists, this.assignments] = await Promise.all([
            API.getTherapists(),
            API.getSchedule().catch(() => []),
        ]);
    },

    _weeklyHours() {
        const hours = {};
        this.assignments.forEach(a => {
            const s = ScheduleView.parseTime(a.Start);
            const e = ScheduleView.parseTime(a.End);
            if (!s || !e) return;
            hours[a.Therapist] = (hours[a.Therapist] || 0) + (ScheduleView.timeToMinutes(e) - ScheduleView.timeToMinutes(s)) / 60;
        });
        return hours;
    },

    _clientsForTherapist(name) {
        return [...new Set(this.assignments.filter(a => a.Therapist === name).map(a => a.Client))];
    },

    render(container) {
        if (!this.therapists.length) {
            container.innerHTML = '<div class="empty-state">No therapists loaded. Upload an Excel file from the Dashboard.</div>';
            return;
        }

        const weeklyHours = this._weeklyHours();

        let html = '<div class="table-wrapper"><table class="data-table">';
        html += '<thead><tr>';
        html += '<th>Name</th><th>Days</th><th>Hours Available</th>';
        html += '<th>In-Home</th><th>40h Eligible</th><th>Weekly Hours</th><th>Utilization</th><th>Clients</th>';
        html += '</tr></thead><tbody>';

        this.therapists.forEach(t => {
            const weekly = weeklyHours[t.name] || 0;
            const barPct = Math.min((weekly / 35) * 100, 100);
            const barClass = weekly >= 35 ? 'red' : weekly >= 30 ? 'yellow' : 'green';
            const clients = this._clientsForTherapist(t.name);
            const inHome = String(t.in_home || '').toLowerCase();
            const inHomeBadge = inHome === 'only' ? '<span class="badge badge-home">Only</span>'
                : inHome === 'yes' ? '<span class="badge badge-home">Yes</span>'
                : '<span class="badge badge-clinic">No</span>';
            const eligBadge = String(t.forty_hour_eligible || '').toLowerCase() === 'yes'
                ? '<span class="badge badge-home">Yes</span>'
                : '<span class="badge badge-clinic">No</span>';

            html += `<tr class="clickable-row" data-id="${t.id}">`;
            html += `<td><strong>${t.name}</strong></td>`;
            html += `<td>${t.days_available || '--'}</td>`;
            html += `<td class="text-sm">${t.hours_available || '--'}</td>`;
            html += `<td>${inHomeBadge}</td>`;
            html += `<td>${eligBadge}</td>`;
            html += `<td><strong>${weekly.toFixed(1)}h</strong></td>`;
            html += `<td><div class="hours-bar"><div class="hours-bar-fill ${barClass}" style="width:${barPct}%"></div></div></td>`;
            html += `<td class="text-sm text-muted">${clients.join(', ') || '--'}</td>`;
            html += '</tr>';
        });

        html += '</tbody></table></div>';
        container.innerHTML = html;

        // Bind row clicks
        container.querySelectorAll('.clickable-row').forEach(row => {
            row.addEventListener('click', () => {
                const id = parseInt(row.dataset.id);
                const t = this.therapists.find(th => th.id === id);
                if (t) TherapistModal.openEdit(t);
            });
        });
    }
};


/**
 * Therapist add/edit modal.
 */
const TherapistModal = {
    _editingId: null,

    init() {
        document.getElementById('add-therapist-btn').addEventListener('click', () => this.openAdd());
        document.getElementById('therapist-modal-close').addEventListener('click', () => this.close());
        document.getElementById('tm-cancel').addEventListener('click', () => this.close());
        document.getElementById('tm-save').addEventListener('click', () => this._save());
        document.getElementById('tm-delete').addEventListener('click', () => this._delete());
        document.getElementById('therapist-modal-overlay').addEventListener('click', (e) => {
            if (e.target.id === 'therapist-modal-overlay') this.close();
        });
    },

    /** Parse a days string like "Mon - Fri" or "Mon, Tue, Wed" into a Set of day abbreviations. */
    _parseDaysString(str) {
        if (!str) return new Set(['Mon', 'Tue', 'Wed', 'Thu', 'Fri']);
        const allDays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        const s = str.trim();
        // Handle range format: "Mon - Fri"
        const rangeMatch = s.match(/^(\w{3})\s*-\s*(\w{3})$/);
        if (rangeMatch) {
            const startIdx = allDays.indexOf(rangeMatch[1]);
            const endIdx = allDays.indexOf(rangeMatch[2]);
            if (startIdx >= 0 && endIdx >= 0) {
                return new Set(allDays.slice(startIdx, endIdx + 1));
            }
        }
        // Handle comma-separated: "Mon, Tue, Fri"
        const days = new Set();
        allDays.forEach(d => {
            if (s.includes(d)) days.add(d);
        });
        return days.size ? days : new Set(['Mon', 'Tue', 'Wed', 'Thu', 'Fri']);
    },

    /** Set day checkboxes from a Set of day abbreviations. */
    _setDayCheckboxes(days) {
        document.querySelectorAll('#tm-days-checks input[type="checkbox"]').forEach(cb => {
            cb.checked = days.has(cb.value);
        });
    },

    /** Get selected days as a comma-separated string. */
    _getDaysFromCheckboxes() {
        const checked = [...document.querySelectorAll('#tm-days-checks input:checked')];
        return checked.map(cb => cb.value).join(', ');
    },

    openAdd() {
        this._editingId = null;
        document.getElementById('therapist-modal-title').textContent = 'Add Therapist';
        document.getElementById('tm-delete').style.display = 'none';
        document.getElementById('tm-name').value = '';
        this._setDayCheckboxes(new Set(['Mon', 'Tue', 'Wed', 'Thu', 'Fri']));
        document.getElementById('tm-hours').value = '8am - 5pm';
        document.getElementById('tm-inhome').value = 'Yes';
        document.getElementById('tm-forty').value = 'yes';
        document.getElementById('tm-prefmax').value = '';
        document.getElementById('tm-notes').value = '';
        this._clearError();
        this._show();
    },

    openEdit(t) {
        this._editingId = t.id;
        document.getElementById('therapist-modal-title').textContent = 'Edit Therapist';
        document.getElementById('tm-delete').style.display = '';
        document.getElementById('tm-name').value = t.name || '';
        this._setDayCheckboxes(this._parseDaysString(t.days_available));
        document.getElementById('tm-hours').value = t.hours_available || '8am - 5pm';
        document.getElementById('tm-inhome').value = (t.in_home || 'No');
        document.getElementById('tm-forty').value = (t.forty_hour_eligible || 'No');
        document.getElementById('tm-prefmax').value = t.preferred_max_hours || '';
        document.getElementById('tm-notes').value = t.notes || '';
        this._clearError();
        this._show();
    },

    close() {
        document.getElementById('therapist-modal-overlay').style.display = 'none';
    },

    _show() {
        document.getElementById('therapist-modal-overlay').style.display = '';
    },

    async _save() {
        const name = document.getElementById('tm-name').value.trim();
        if (!name) {
            this._showError('Name is required.');
            return;
        }

        const data = {
            name: name,
            days_available: this._getDaysFromCheckboxes(),
            hours_available: document.getElementById('tm-hours').value.trim(),
            in_home: document.getElementById('tm-inhome').value,
            forty_hour_eligible: document.getElementById('tm-forty').value,
            preferred_max_hours: document.getElementById('tm-prefmax').value ? parseFloat(document.getElementById('tm-prefmax').value) : null,
            notes: document.getElementById('tm-notes').value.trim(),
        };

        const btn = document.getElementById('tm-save');
        btn.disabled = true;
        btn.textContent = 'Saving...';

        try {
            if (this._editingId) {
                await API.updateTherapist(this._editingId, data);
                App.toast('Therapist updated', 'success');
            } else {
                await API.postJSON('/api/therapists', data);
                App.toast('Therapist added', 'success');
            }
            this.close();
            await TherapistView.load();
            TherapistView.render(document.getElementById('therapists-content'));
            AssignmentModal.refreshData();
        } catch (err) {
            this._showError('Save failed: ' + err.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Save';
        }
    },

    async _delete() {
        if (!this._editingId) return;
        if (!confirm('Delete this therapist? This cannot be undone.')) return;

        try {
            await API.deleteTherapist(this._editingId);
            App.toast('Therapist deleted', 'success');
            this.close();
            await TherapistView.load();
            TherapistView.render(document.getElementById('therapists-content'));
            AssignmentModal.refreshData();
        } catch (err) {
            this._showError('Delete failed: ' + err.message);
        }
    },

    _showError(msg) {
        const el = document.getElementById('therapist-modal-error');
        el.style.display = '';
        el.textContent = msg;
    },

    _clearError() {
        const el = document.getElementById('therapist-modal-error');
        el.style.display = 'none';
        el.textContent = '';
    },
};
