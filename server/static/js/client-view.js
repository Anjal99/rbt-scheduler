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

            html += '<tr>';
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
    }
};
