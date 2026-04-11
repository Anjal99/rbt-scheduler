/**
 * Assignment edit/add modal controller.
 * Supports multi-day add, edit, and delete.
 */
const AssignmentModal = {
    _editingId: null,      // null = adding new, number = editing existing
    _therapists: [],
    _clients: [],
    _siblings: [],         // Related assignments across days (same client+therapist+time)
    _bound: false,         // Guard so listeners are only attached once

    async init() {
        await this.refreshData();
        if (!this._bound) {
            this._bindButtons();
            this._bound = true;
        }
    },

    async refreshData() {
        [this._therapists, this._clients] = await Promise.all([
            API.getTherapists().catch(() => []),
            API.getClients().catch(() => []),
        ]);
        this._populateDropdowns();
    },

    _populateDropdowns() {
        const tSelect = document.getElementById('modal-therapist');
        const cSelect = document.getElementById('modal-client');

        tSelect.innerHTML = this._therapists
            .map(t => `<option value="${t.name}">${t.name}</option>`)
            .join('');

        cSelect.innerHTML = this._clients
            .map(c => `<option value="${c.name}">${c.name}</option>`)
            .join('');
    },

    _bindButtons() {
        document.getElementById('modal-close').addEventListener('click', () => this.close());
        document.getElementById('modal-cancel').addEventListener('click', () => this.close());
        document.getElementById('modal-save').addEventListener('click', () => this._save());
        document.getElementById('modal-delete').addEventListener('click', () => this._delete());

        // Close on overlay click
        document.getElementById('modal-overlay').addEventListener('click', (e) => {
            if (e.target.id === 'modal-overlay') this.close();
        });

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this._isOpen()) this.close();
        });

        // Add assignment button
        document.getElementById('add-assignment-btn').addEventListener('click', () => this.openAdd());
    },

    _isOpen() {
        return document.getElementById('modal-overlay').style.display !== 'none';
    },

    _editingLockType: null,

    /**
     * Find sibling assignments: same client + therapist + start + end on other days.
     */
    _findSiblings(assignment) {
        const startNorm = ScheduleView.toInputTime(assignment.Start);
        const endNorm = ScheduleView.toInputTime(assignment.End);
        return ScheduleView.assignments.filter(a =>
            a.Client === assignment.Client &&
            a.Therapist === assignment.Therapist &&
            ScheduleView.toInputTime(a.Start) === startNorm &&
            ScheduleView.toInputTime(a.End) === endNorm
        );
    },

    openEdit(assignment) {
        this._editingId = assignment.id;
        this._editingLockType = assignment.LockType || null;
        document.getElementById('modal-title').textContent = 'Edit Assignment';
        document.getElementById('modal-delete').style.display = '';

        // Find sibling assignments across days
        this._siblings = this._findSiblings(assignment);

        // Show multi-day checkboxes (same as add mode) so user can manage days
        document.getElementById('modal-day').style.display = 'none';
        const multiContainer = document.getElementById('modal-days-multi');
        multiContainer.style.display = '';
        const siblingDays = new Set(this._siblings.map(a => a.Day));
        multiContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.checked = siblingDays.has(cb.value);
        });

        // Populate fields
        document.getElementById('modal-client').value = assignment.Client || '';
        document.getElementById('modal-therapist').value = assignment.Therapist || '';
        document.getElementById('modal-location').value = assignment.Location || 'Clinic';
        document.getElementById('modal-type').value = assignment.Type || 'Recurring';
        document.getElementById('modal-start').value = ScheduleView.toInputTime(assignment.Start);
        document.getElementById('modal-end').value = ScheduleView.toInputTime(assignment.End);

        this._clearValidation();
        this._applyLockState();
        this._show();
    },

    _applyLockState() {
        const fields = ['modal-client', 'modal-therapist',
                        'modal-location', 'modal-type', 'modal-start', 'modal-end'];
        const saveBtn = document.getElementById('modal-save');

        if (this._editingLockType === 'hard') {
            fields.forEach(id => { document.getElementById(id).disabled = true; });
            document.querySelectorAll('#modal-days-multi input').forEach(cb => { cb.disabled = true; });
            saveBtn.style.display = 'none';
            this._showValidation(
                '<strong>Hard-locked.</strong> Unlock from the schedule view to make changes.',
                'info'
            );
        } else if (this._editingLockType === 'soft') {
            fields.forEach(id => { document.getElementById(id).disabled = false; });
            document.querySelectorAll('#modal-days-multi input').forEach(cb => { cb.disabled = false; });
            saveBtn.style.display = '';
            this._showValidation(
                '<strong>Soft-locked.</strong> Editing will remove the soft lock.',
                'warnings'
            );
        } else {
            fields.forEach(id => { document.getElementById(id).disabled = false; });
            document.querySelectorAll('#modal-days-multi input').forEach(cb => { cb.disabled = false; });
            saveBtn.style.display = '';
        }
    },

    openAdd() {
        this._editingId = null;
        this._editingLockType = null;
        this._siblings = [];
        document.getElementById('modal-title').textContent = 'Add Assignment';
        document.getElementById('modal-delete').style.display = 'none';
        document.getElementById('modal-save').style.display = '';

        // Show multi-day checkboxes
        document.getElementById('modal-day').style.display = 'none';
        const multiContainer = document.getElementById('modal-days-multi');
        multiContainer.style.display = '';
        multiContainer.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.checked = (cb.value === ScheduleView.currentDay);
            cb.disabled = false;
        });

        document.getElementById('modal-client').selectedIndex = 0;
        document.getElementById('modal-therapist').selectedIndex = 0;
        document.getElementById('modal-location').value = 'Clinic';
        document.getElementById('modal-type').value = 'Recurring';
        document.getElementById('modal-start').value = '09:00';
        document.getElementById('modal-end').value = '12:00';

        this._clearValidation();
        this._show();
    },

    close() {
        document.getElementById('modal-overlay').style.display = 'none';
        this._siblings = [];
        // Re-enable fields in case they were disabled by hard lock
        ['modal-client', 'modal-therapist',
         'modal-location', 'modal-type', 'modal-start', 'modal-end'].forEach(id => {
            document.getElementById(id).disabled = false;
        });
        document.querySelectorAll('#modal-days-multi input').forEach(cb => { cb.disabled = false; });
        // Reset day controls to default state
        document.getElementById('modal-day').style.display = '';
        document.getElementById('modal-days-multi').style.display = 'none';
    },

    _show() {
        document.getElementById('modal-overlay').style.display = '';
    },

    _getFormData() {
        const base = {
            client_name: document.getElementById('modal-client').value,
            therapist_name: document.getElementById('modal-therapist').value,
            start_time: document.getElementById('modal-start').value,
            end_time: document.getElementById('modal-end').value,
            location: document.getElementById('modal-location').value,
            assignment_type: document.getElementById('modal-type').value,
            notes: '',
        };
        const checked = [...document.querySelectorAll('#modal-days-multi input:checked')];
        base.days = checked.map(cb => cb.value);
        return base;
    },

    async _save() {
        const data = this._getFormData();

        // Basic form validation
        if (!data.client_name || !data.therapist_name || !data.start_time || !data.end_time) {
            this._showValidation('Please fill in all fields.', 'errors');
            return;
        }
        if (data.start_time >= data.end_time) {
            this._showValidation('End time must be after start time.', 'errors');
            return;
        }
        if (!data.days || data.days.length === 0) {
            this._showValidation('Please select at least one day.', 'errors');
            return;
        }

        const saveBtn = document.getElementById('modal-save');
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';

        try {
            const checkedDays = new Set(data.days);
            const assignmentData = {
                client_name: data.client_name,
                therapist_name: data.therapist_name,
                start_time: data.start_time,
                end_time: data.end_time,
                location: data.location,
                assignment_type: data.assignment_type,
                notes: data.notes,
            };

            let created = 0, updated = 0, removed = 0;

            if (this._editingId) {
                // Multi-day edit: update/create/delete siblings
                const siblingByDay = {};
                this._siblings.forEach(s => { siblingByDay[s.Day] = s; });

                // Update existing or create new for each checked day
                for (const day of checkedDays) {
                    if (siblingByDay[day]) {
                        const updateData = { ...assignmentData, day };
                        // Clear soft lock on edit
                        if (siblingByDay[day].LockType === 'soft') {
                            updateData.lock_type = null;
                        }
                        // Skip hard-locked siblings
                        if (siblingByDay[day].LockType === 'hard') continue;
                        await API.updateAssignment(siblingByDay[day].id, updateData);
                        updated++;
                    } else {
                        await API.addAssignment({ ...assignmentData, day });
                        created++;
                    }
                }

                // Delete unchecked days (skip hard-locked)
                for (const sibling of this._siblings) {
                    if (!checkedDays.has(sibling.Day) && sibling.LockType !== 'hard') {
                        await API.deleteAssignment(sibling.id);
                        removed++;
                    }
                }
            } else {
                // Add mode: create for each selected day
                for (const day of checkedDays) {
                    await API.addAssignment({ ...assignmentData, day });
                    created++;
                }
            }

            // Build feedback message
            const parts = [];
            if (created) parts.push(`${created} added`);
            if (updated) parts.push(`${updated} updated`);
            if (removed) parts.push(`${removed} removed`);
            const summary = parts.join(', ');

            // Always close and show success
            App.toast(`Assignment${checkedDays.size > 1 ? 's' : ''}: ${summary}`, 'success');
            this.close();

            // Refresh schedule view
            await ScheduleView.refresh();
            App.refreshDashboard();

            // Check for validation issues and show as a separate warning
            try {
                const validation = await API.validateSchedule();
                const issues = validation.flags.filter(f =>
                    (f.severity === 'Error' || f.severity === 'Critical') &&
                    (f.who === data.client_name || f.who === data.therapist_name)
                );
                if (issues.length > 0) {
                    App.toast(`${issues.length} issue${issues.length > 1 ? 's' : ''} — check Validation`, 'error');
                }
            } catch (_) {}

        } catch (err) {
            this._showValidation('Save failed: ' + err.message, 'errors');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save';
        }
    },

    async _delete() {
        if (!this._editingId) return;

        const siblings = this._siblings.filter(s => s.LockType !== 'hard');
        if (!siblings.length) {
            this._showValidation('All assignments are hard-locked and cannot be deleted.', 'info');
            return;
        }

        const days = siblings.map(s => s.Day).join(', ');
        const msg = siblings.length > 1
            ? `Delete this assignment on ${siblings.length} days (${days})?`
            : 'Delete this assignment?';
        if (!confirm(msg)) return;

        try {
            for (const sibling of siblings) {
                await API.deleteAssignment(sibling.id);
            }
            App.toast(`Deleted ${siblings.length} assignment${siblings.length > 1 ? 's' : ''}`, 'success');
            this.close();
            await ScheduleView.refresh();
            App.refreshDashboard();
        } catch (err) {
            this._showValidation('Delete failed: ' + err.message, 'errors');
        }
    },

    /** Convert a validation flag into a short, human-readable message. */
    _friendlyError(flag) {
        switch (flag.rule) {
            case 'Overlap':
                return `${flag.who} has a time conflict on ${flag.day}`;
            case '4h Break':
                return `${flag.who} needs a 30-min break on ${flag.day}`;
            case 'Workload':
            case '40h':
            case 'Pref Max':
                return `${flag.who} is over their hour limit`;
            case 'Location Conflict':
                return `${flag.who} can't work at that location`;
            case 'Coverage':
            case 'Coverage Gap':
                return `${flag.who} missing coverage on ${flag.day}`;
            case 'Unscheduled':
                return `${flag.who} has no assignments`;
            default:
                return flag.detail;
        }
    },

    _showValidation(html, type) {
        const el = document.getElementById('modal-validation');
        el.style.display = '';
        el.className = 'modal-validation';
        if (type === 'errors') el.classList.add('has-errors');
        else if (type === 'warnings') el.classList.add('has-warnings');
        else if (type === 'info') el.classList.add('is-info');
        else el.classList.add('is-clean');
        el.innerHTML = html;
    },

    _clearValidation() {
        const el = document.getElementById('modal-validation');
        el.style.display = 'none';
        el.innerHTML = '';
    },
};
