/**
 * User management view (admin only).
 */
const UsersView = {
    users: [],

    async load() {
        try {
            this.users = await API.getJSON('/api/auth/users');
        } catch (e) {
            this.users = [];
        }
    },

    render(container) {
        if (!this.users.length) {
            container.innerHTML = '<div class="empty-state">No users found.</div>';
            return;
        }

        let html = '<div class="table-wrapper"><table class="data-table">';
        html += '<thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th>Actions</th></tr></thead><tbody>';

        this.users.forEach(u => {
            const roleBadge = u.role === 'admin'
                ? '<span class="badge badge-high">Admin</span>'
                : '<span class="badge badge-low">Staff</span>';
            const statusBadge = u.is_active
                ? '<span class="badge badge-clinic">Active</span>'
                : '<span class="badge badge-high">Inactive</span>';

            html += `<tr>`;
            html += `<td><strong>${u.name}</strong></td>`;
            html += `<td>${u.email}</td>`;
            html += `<td>${roleBadge}</td>`;
            html += `<td>${statusBadge}</td>`;
            html += `<td>`;
            html += `<button class="btn btn-sm btn-secondary user-reset-pw" data-id="${u.id}" data-name="${u.name}">Reset Password</button> `;
            html += `<button class="btn btn-sm btn-danger user-delete" data-id="${u.id}" data-name="${u.name}">Delete</button>`;
            html += `</td></tr>`;
        });

        html += '</tbody></table></div>';
        container.innerHTML = html;

        // Bind actions
        container.querySelectorAll('.user-reset-pw').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.dataset.id;
                const name = btn.dataset.name;
                if (!confirm(`Reset password for ${name}?`)) return;
                try {
                    const res = await API.postJSON(`/api/auth/users/${id}/reset-password`, {});
                    App.toast(`New temp password for ${name}: ${res.temp_password}`, 'success');
                    // Show it prominently
                    alert(`New temporary password for ${name}:\n\n${res.temp_password}\n\nShare this securely with them.`);
                } catch (e) {
                    App.toast('Reset failed: ' + e.message, 'error');
                }
            });
        });

        container.querySelectorAll('.user-delete').forEach(btn => {
            btn.addEventListener('click', async () => {
                const id = btn.dataset.id;
                const name = btn.dataset.name;
                if (!confirm(`Delete user ${name}? This cannot be undone.`)) return;
                try {
                    await fetch(`/api/auth/users/${id}`, { method: 'DELETE' });
                    App.toast(`${name} deleted`, 'success');
                    await this.load();
                    this.render(container);
                } catch (e) {
                    App.toast('Delete failed: ' + e.message, 'error');
                }
            });
        });
    }
};


/**
 * Invite user modal.
 */
const InviteModal = {
    init() {
        document.getElementById('invite-user-btn').addEventListener('click', () => this.open());
        document.getElementById('invite-modal-close').addEventListener('click', () => this.close());
        document.getElementById('invite-cancel').addEventListener('click', () => this.close());
        document.getElementById('invite-save').addEventListener('click', () => this._save());
        document.getElementById('invite-modal-overlay').addEventListener('click', (e) => {
            if (e.target.id === 'invite-modal-overlay') this.close();
        });
    },

    open() {
        document.getElementById('invite-name').value = '';
        document.getElementById('invite-email').value = '';
        document.getElementById('invite-role').value = 'staff';
        document.getElementById('invite-result').style.display = 'none';
        document.getElementById('invite-error').style.display = 'none';
        document.getElementById('invite-modal-overlay').style.display = '';
    },

    close() {
        document.getElementById('invite-modal-overlay').style.display = 'none';
    },

    async _save() {
        const name = document.getElementById('invite-name').value.trim();
        const email = document.getElementById('invite-email').value.trim();
        const role = document.getElementById('invite-role').value;

        if (!name || !email) {
            document.getElementById('invite-error').textContent = 'Name and email are required.';
            document.getElementById('invite-error').style.display = '';
            return;
        }

        const btn = document.getElementById('invite-save');
        btn.disabled = true;
        btn.textContent = 'Creating...';

        try {
            const res = await API.postJSON('/api/auth/users', { name, email, role });
            document.getElementById('invite-error').style.display = 'none';
            const resultEl = document.getElementById('invite-result');
            resultEl.style.display = '';
            resultEl.innerHTML = `<strong>Account created!</strong><br>
                Temporary password: <code style="background:#e2e8f0;padding:2px 8px;border-radius:4px;font-size:1rem;font-weight:700">${res.temp_password}</code><br>
                <small>Share this securely with ${name}. They should change it after first login.</small>`;

            App.toast(`User ${name} created`, 'success');
            await UsersView.load();
            UsersView.render(document.getElementById('users-content'));
        } catch (e) {
            document.getElementById('invite-error').textContent = 'Failed: ' + e.message;
            document.getElementById('invite-error').style.display = '';
        } finally {
            btn.disabled = false;
            btn.textContent = 'Create Account';
        }
    }
};
