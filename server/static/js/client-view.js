/**
 * Client list view with assigned therapists and coverage.
 */
const ClientView = {
    clients: [],
    assignments: [],

    async load() {
        [this.clients, this.assignments] = await Promise.all([
            API.getClients(),
            API.getSchedule().catch(() => []),
        ]);
    },

    _therapistsForClient(name) {
        const therapists = new Set();
        this.assignments.filter(a => a.Client === name).forEach(a => therapists.add(a.Therapist));
        return [...therapists];
    },

    _weeklyHoursForClient(name) {
        let total = 0;
        this.assignments.filter(a => a.Client === name).forEach(a => {
            const s = ScheduleView.parseTime(a.Start);
            const e = ScheduleView.parseTime(a.End);
            if (s && e) total += (ScheduleView.timeToMinutes(e) - ScheduleView.timeToMinutes(s)) / 60;
        });
        return total;
    },

    _daysAssigned(name) {
        return [...new Set(this.assignments.filter(a => a.Client === name).map(a => a.Day))];
    },

    render(container) {
        if (!this.clients.length) {
            container.innerHTML = '<div class="empty-state">No clients loaded. Upload an Excel file from the Dashboard.</div>';
            return;
        }

        let html = '<div class="table-wrapper"><table class="data-table">';
        html += '<thead><tr>';
        html += '<th>Name</th><th>Schedule Needed</th><th>Days</th>';
        html += '<th>Location</th><th>Intensity</th><th>Assigned Hours</th><th>Therapists</th>';
        html += '</tr></thead><tbody>';

        this.clients.forEach(c => {
            const name = c.name || c.Name || '';
            const therapists = this._therapistsForClient(name);
            const hours = this._weeklyHoursForClient(name);
            const assignedDays = this._daysAssigned(name);

            const location = c.in_home || c['In-Home'] || 'Clinic';
            let locBadge = '<span class="badge badge-clinic">Clinic</span>';
            if (location.toLowerCase().includes('home') && !location.toLowerCase().includes('hybrid')) {
                locBadge = '<span class="badge badge-home">Home</span>';
            } else if (location.toLowerCase().includes('hybrid')) {
                locBadge = '<span class="badge badge-hybrid">Hybrid</span>';
            }

            const intensity = c.intensity || c.Intensity || 'Low';
            const intBadge = intensity.toLowerCase() === 'high'
                ? '<span class="badge badge-high">High</span>'
                : '<span class="badge badge-low">Low</span>';

            const schedule = c.schedule_needed || c['Schedule Needed'] || '--';
            const days = c.days || c.Days || '--';

            html += `<tr class="clickable-row" data-id="${c.id}">`;
            html += `<td><strong>${name}</strong></td>`;
            html += `<td class="text-sm">${schedule}</td>`;
            html += `<td>${days}</td>`;
            html += `<td>${locBadge}</td>`;
            html += `<td>${intBadge}</td>`;
            html += `<td><strong>${hours.toFixed(1)}h</strong> <span class="text-muted text-sm">(${assignedDays.length} days)</span></td>`;
            html += `<td class="text-sm">${therapists.join(', ') || '<span class="text-muted">Unassigned</span>'}</td>`;
            html += '</tr>';
        });

        html += '</tbody></table></div>';
        container.innerHTML = html;

        // Bind row clicks for editing
        container.querySelectorAll('.clickable-row').forEach(row => {
            row.addEventListener('click', () => {
                const id = parseInt(row.dataset.id);
                const c = this.clients.find(cl => (cl.id || cl.Id) === id);
                if (c) ClientModal.openEdit(c);
            });
        });
    }
};


/**
 * Client edit modal.
 */
const ClientModal = {
    _editingId: null,

    init() {
        document.getElementById('cm-close').addEventListener('click', () => this.close());
        document.getElementById('cm-cancel').addEventListener('click', () => this.close());
        document.getElementById('cm-save').addEventListener('click', () => this._save());
        document.getElementById('client-modal-overlay').addEventListener('click', (e) => {
            if (e.target.id === 'client-modal-overlay') this.close();
        });
    },

    /** Parse a days string into a Set of day abbreviations. */
    _parseDaysString(str) {
        if (!str) return new Set(['Mon', 'Tue', 'Wed', 'Thu', 'Fri']);
        const allDays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
        const s = str.trim();
        const rangeMatch = s.match(/^(\w{3})\s*-\s*(\w{3})$/);
        if (rangeMatch) {
            const startIdx = allDays.indexOf(rangeMatch[1]);
            const endIdx = allDays.indexOf(rangeMatch[2]);
            if (startIdx >= 0 && endIdx >= 0) {
                return new Set(allDays.slice(startIdx, endIdx + 1));
            }
        }
        const days = new Set();
        allDays.forEach(d => { if (s.includes(d)) days.add(d); });
        return days.size ? days : new Set(['Mon', 'Tue', 'Wed', 'Thu', 'Fri']);
    },

    _setDayCheckboxes(days) {
        document.querySelectorAll('#cm-days-checks input[type="checkbox"]').forEach(cb => {
            cb.checked = days.has(cb.value);
        });
    },

    _getDaysFromCheckboxes() {
        const checked = [...document.querySelectorAll('#cm-days-checks input:checked')];
        return checked.map(cb => cb.value).join(', ');
    },

    openEdit(c) {
        this._editingId = c.id;
        document.getElementById('client-modal-title').textContent = 'Edit Client';
        document.getElementById('cm-name').value = c.name || c.Name || '';
        document.getElementById('cm-schedule').value = c.schedule_needed || c['Schedule Needed'] || '';
        this._setDayCheckboxes(this._parseDaysString(c.days || c.Days));

        const location = c.in_home || c['In-Home'] || 'Clinic';
        if (location.toLowerCase().includes('hybrid')) {
            document.getElementById('cm-location').value = 'Hybrid';
        } else if (location.toLowerCase().includes('home')) {
            document.getElementById('cm-location').value = 'Home';
        } else {
            document.getElementById('cm-location').value = 'Clinic';
        }

        document.getElementById('cm-intensity').value = (c.intensity || c.Intensity || 'Low');
        document.getElementById('cm-notes').value = c.notes || c.Notes || '';
        this._clearError();
        this._show();
    },

    close() {
        document.getElementById('client-modal-overlay').style.display = 'none';
    },

    _show() {
        document.getElementById('client-modal-overlay').style.display = '';
    },

    async _save() {
        const data = {
            schedule_needed: document.getElementById('cm-schedule').value.trim(),
            days: this._getDaysFromCheckboxes(),
            in_home: document.getElementById('cm-location').value,
            intensity: document.getElementById('cm-intensity').value,
            notes: document.getElementById('cm-notes').value.trim(),
        };

        const btn = document.getElementById('cm-save');
        btn.disabled = true;
        btn.textContent = 'Saving...';

        try {
            await API.updateClient(this._editingId, data);
            App.toast('Client updated', 'success');
            this.close();
            await ClientView.load();
            ClientView.render(document.getElementById('clients-content'));
        } catch (err) {
            this._showError('Save failed: ' + err.message);
        } finally {
            btn.disabled = false;
            btn.textContent = 'Save';
        }
    },

    _showError(msg) {
        const el = document.getElementById('client-modal-error');
        el.style.display = '';
        el.textContent = msg;
    },

    _clearError() {
        const el = document.getElementById('client-modal-error');
        el.style.display = 'none';
        el.textContent = '';
    },
};
