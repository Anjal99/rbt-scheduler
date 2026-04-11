/**
 * Validation view - displays schedule rule violations with user-friendly messages.
 */
const ValidationView = {
    flags: [],
    counts: {},

    async runValidation() {
        const data = await API.validateSchedule();
        this.flags = data.flags || [];
        this.counts = data.counts || {};
        return data;
    },

    /** Convert a validation flag into a short, friendly description. */
    _friendlyMessage(flag) {
        switch (flag.rule) {
            case 'Overlap':
                return 'Has overlapping assignments — two sessions at the same time';
            case '4h Break':
                return 'Working too long without a break (needs 30 min after 4h)';
            case 'Workload':
                return 'Over the weekly hour limit';
            case '40h':
                return 'At 40+ hours — verify a 2-hour mid-day break is scheduled';
            case 'Pref Max':
                return 'Exceeding their preferred max hours';
            case 'Location Conflict':
                return 'Assigned to a location they can\'t work at';
            case 'Unscheduled':
                return 'Has no assignments at all';
            case 'Coverage':
                return 'Missing sessions on required days';
            case 'Coverage Gap':
                return 'Not enough hours assigned for their needs';
            default:
                return flag.detail;
        }
    },

    render(statsContainer, contentContainer) {
        // Stats cards
        let statsHtml = '';
        const items = [
            { label: 'Errors', value: this.counts.errors || 0, cls: (this.counts.errors || 0) > 0 ? 'error' : 'success' },
            { label: 'Critical', value: this.counts.critical || 0, cls: (this.counts.critical || 0) > 0 ? 'error' : 'success' },
            { label: 'Warnings', value: this.counts.warnings || 0, cls: (this.counts.warnings || 0) > 0 ? 'warning' : 'success' },
            { label: 'Info', value: this.counts.info || 0, cls: 'info' },
        ];
        items.forEach(item => {
            statsHtml += `<div class="stat-card ${item.cls}">`;
            statsHtml += `<div class="stat-value">${item.value}</div>`;
            statsHtml += `<div class="stat-label">${item.label}</div>`;
            statsHtml += `</div>`;
        });
        statsContainer.innerHTML = statsHtml;

        // Flags grouped by severity
        if (!this.flags.length) {
            contentContainer.innerHTML = '<div class="empty-state">No validation issues found. Schedule looks good!</div>';
            return;
        }

        const groups = { Critical: [], Error: [], Warning: [], Info: [] };
        this.flags.forEach(f => {
            const sev = f.severity || 'Info';
            if (groups[sev]) groups[sev].push(f);
        });

        let html = '';
        const sevLabels = {
            Critical: 'Needs Immediate Attention',
            Error: 'Conflicts',
            Warning: 'Heads Up',
            Info: 'Notes'
        };
        const order = ['Critical', 'Error', 'Warning', 'Info'];
        order.forEach(sev => {
            const items = groups[sev];
            if (!items.length) return;

            const clsMap = { Critical: 'critical', Error: 'errors', Warning: 'warnings', Info: 'info' };
            html += `<div class="flag-group">`;
            html += `<div class="flag-group-header ${clsMap[sev]}">${sevLabels[sev]} (${items.length})</div>`;

            items.forEach(f => {
                const itemCls = sev.toLowerCase();
                html += `<div class="warning-item ${itemCls}">`;
                html += `<div class="warning-dot"></div>`;
                html += `<div><strong>${f.who}</strong>`;
                if (f.day) html += ` &middot; ${f.day}`;
                html += `<br><span class="text-sm">${this._friendlyMessage(f)}</span>`;
                html += `</div></div>`;
            });

            html += `</div>`;
        });

        contentContainer.innerHTML = html;
    }
};
