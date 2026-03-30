/**
 * API wrapper - all fetch calls to the Flask backend.
 */
const API = {
    base: '',

    async _fetch(path, opts = {}) {
        const res = await fetch(this.base + path, opts);
        if (!res.ok) {
            const err = await res.json().catch(() => ({ error: res.statusText }));
            throw new Error(err.error || 'Request failed');
        }
        return res;
    },

    async getJSON(path) {
        const res = await this._fetch(path);
        return res.json();
    },

    async postJSON(path, body) {
        const res = await this._fetch(path, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        return res.json();
    },

    async uploadFile(path, file) {
        const form = new FormData();
        form.append('file', file);
        const res = await this._fetch(path, { method: 'POST', body: form });
        return res.json();
    },

    // Therapists
    getTherapists()       { return this.getJSON('/api/therapists'); },
    getTherapistCount()   { return this.getJSON('/api/therapists/count'); },
    importTherapists(f)   { return this.uploadFile('/api/therapists/import', f); },

    // Clients
    getClients()          { return this.getJSON('/api/clients'); },
    getClientCount()      { return this.getJSON('/api/clients/count'); },
    uploadClients(f)      { return this.uploadFile('/api/clients/upload', f); },

    // Schedule
    getSchedule()         { return this.getJSON('/api/schedule'); },
    generateSchedule()    { return this.postJSON('/api/schedule/generate'); },
    validateSchedule()    { return this.postJSON('/api/schedule/validate'); },
    getScheduleStats()    { return this.getJSON('/api/schedule/stats'); },

    // Assignment CRUD
    async addAssignment(data) {
        return this.postJSON('/api/schedule/assignment', data);
    },
    async updateAssignment(id, data) {
        const res = await this._fetch(`/api/schedule/assignment/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },
    async deleteAssignment(id) {
        const res = await this._fetch(`/api/schedule/assignment/${id}`, { method: 'DELETE' });
        return res.json();
    },

    // Export
    exportExcelURL()      { return '/api/export/excel'; },
    exportCSVURL()        { return '/api/export/csv'; },
};
