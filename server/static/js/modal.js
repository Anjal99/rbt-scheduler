/**
 * Assignment edit/add modal controller.
 */
const AssignmentModal = {
    _editingId: null,      // null = adding new, number = editing existing
    _therapists: [],
    _clients: [],

    async init() {
        // Cache therapists + clients for dropdowns
        [this._therapists, this._clients] = await Promise.all([
            API.getTherapists().catch(() => []),
            API.getClients().catch(() => []),
        ]);
        this._populateDropdowns();
        this._bindButtons();
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

    openEdit(assignment) {
        this._editingId = assignment.id;
        document.getElementById('modal-title').textContent = 'Edit Assignment';
        document.getElementById('modal-delete').style.display = '';

        // Populate fields
        document.getElementById('modal-client').value = assignment.Client || '';
        document.getElementById('modal-therapist').value = assignment.Therapist || '';
        document.getElementById('modal-day').value = assignment.Day || 'Mon';
        document.getElementById('modal-location').value = assignment.Location || 'Clinic';
        document.getElementById('modal-type').value = assignment.Type || 'Recurring';
        document.getElementById('modal-start').value = ScheduleView.toInputTime(assignment.Start);
        document.getElementById('modal-end').value = ScheduleView.toInputTime(assignment.End);

        this._clearValidation();
        this._show();
    },

    openAdd() {
        this._editingId = null;
        document.getElementById('modal-title').textContent = 'Add Assignment';
        document.getElementById('modal-delete').style.display = 'none';

        // Default to current day tab
        document.getElementById('modal-day').value = ScheduleView.currentDay;
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
    },

    _show() {
        document.getElementById('modal-overlay').style.display = '';
    },

    _getFormData() {
        return {
            client_name: document.getElementById('modal-client').value,
            therapist_name: document.getElementById('modal-therapist').value,
            day: document.getElementById('modal-day').value,
            start_time: document.getElementById('modal-start').value,
            end_time: document.getElementById('modal-end').value,
            location: document.getElementById('modal-location').value,
            assignment_type: document.getElementById('modal-type').value,
            notes: '',
        };
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

        const saveBtn = document.getElementById('modal-save');
        saveBtn.disabled = true;
        saveBtn.textContent = 'Saving...';

        try {
            if (this._editingId) {
                await API.updateAssignment(this._editingId, data);
            } else {
                await API.addAssignment(data);
            }

            // Validate after save
            const validation = await API.validateSchedule();
            const errors = validation.flags.filter(f => f.severity === 'Error' || f.severity === 'Critical');
            const warnings = validation.flags.filter(f => f.severity === 'Warning');

            if (errors.length > 0) {
                let msg = `<strong>Saved with ${errors.length} error(s):</strong><ul>`;
                errors.forEach(e => { msg += `<li>${e.who}: ${e.detail}</li>`; });
                msg += '</ul>';
                this._showValidation(msg, 'errors');
            } else if (warnings.length > 0) {
                App.toast(this._editingId ? 'Assignment updated' : 'Assignment added', 'success');
                this.close();
            } else {
                App.toast(this._editingId ? 'Assignment updated' : 'Assignment added', 'success');
                this.close();
            }

            // Refresh schedule view
            await ScheduleView.refresh();
            App.refreshDashboard();

        } catch (err) {
            this._showValidation('Save failed: ' + err.message, 'errors');
        } finally {
            saveBtn.disabled = false;
            saveBtn.textContent = 'Save';
        }
    },

    async _delete() {
        if (!this._editingId) return;
        if (!confirm('Delete this assignment?')) return;

        try {
            await API.deleteAssignment(this._editingId);
            App.toast('Assignment deleted', 'success');
            this.close();
            await ScheduleView.refresh();
            App.refreshDashboard();
        } catch (err) {
            this._showValidation('Delete failed: ' + err.message, 'errors');
        }
    },

    _showValidation(html, type) {
        const el = document.getElementById('modal-validation');
        el.style.display = '';
        el.className = 'modal-validation';
        if (type === 'errors') el.classList.add('has-errors');
        else if (type === 'warnings') el.classList.add('has-warnings');
        else el.classList.add('is-clean');
        el.innerHTML = html;
    },

    _clearValidation() {
        const el = document.getElementById('modal-validation');
        el.style.display = 'none';
        el.innerHTML = '';
    },
};
