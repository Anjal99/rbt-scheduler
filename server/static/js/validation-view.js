/**
 * Validation view - displays schedule rule violations.
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
        const order = ['Critical', 'Error', 'Warning', 'Info'];
        order.forEach(sev => {
            const items = groups[sev];
            if (!items.length) return;

            const clsMap = { Critical: 'critical', Error: 'errors', Warning: 'warnings', Info: 'info' };
            html += `<div class="flag-group">`;
            html += `<div class="flag-group-header ${clsMap[sev]}">${sev} (${items.length})</div>`;

            items.forEach(f => {
                const itemCls = sev.toLowerCase();
                html += `<div class="warning-item ${itemCls}">`;
                html += `<div class="warning-dot"></div>`;
                html += `<div><strong>${f.who}</strong>`;
                if (f.day) html += ` on ${f.day}`;
                html += ` - ${f.detail}`;
                html += ` <span class="text-muted text-sm">[${f.rule}]</span>`;
                html += `</div></div>`;
            });

            html += `</div>`;
        });

        contentContainer.innerHTML = html;
    }
};
