/**
 * Drag-and-drop for schedule cards using SortableJS.
 * Cards can be dragged between therapist rows to reassign.
 */
const ScheduleDrag = {
    _sortables: [],
    _undoStack: [],
    MAX_UNDO: 15,

    init(container) {
        this.destroy();

        // Only enable drag in "By Therapist" view
        if (ScheduleView._viewMode !== 'therapist') return;

        const cardContainers = container.querySelectorAll('.planner-cards');
        cardContainers.forEach(el => {
            const sortable = Sortable.create(el, {
                group: 'schedule',
                animation: 150,
                ghostClass: 'drag-ghost',
                chosenClass: 'drag-chosen',
                dragClass: 'drag-active',
                delay: 150,           // Long-press on mobile
                delayOnTouchOnly: true,
                touchStartThreshold: 3,
                onEnd: (evt) => this._onDrop(evt),
            });
            this._sortables.push(sortable);
        });
    },

    destroy() {
        this._sortables.forEach(s => s.destroy());
        this._sortables = [];
    },

    async _onDrop(evt) {
        const card = evt.item;
        const assignmentId = parseInt(card.dataset.id);
        if (!assignmentId) return;

        const fromRow = evt.from.closest('.planner-row');
        const toRow = evt.to.closest('.planner-row');

        if (!toRow) return;

        // Get new therapist name from the row header
        const newTherapist = toRow.querySelector('.planner-name')?.textContent?.trim();
        if (!newTherapist) return;

        // Find original assignment
        const assignment = ScheduleView.assignments.find(a => a.id === assignmentId);
        if (!assignment) return;

        const oldTherapist = assignment.Therapist;

        // Same row = just reorder, nothing to do
        if (oldTherapist === newTherapist) return;

        // Save undo state
        this._pushUndo({
            id: assignmentId,
            field: 'therapist_name',
            oldValue: oldTherapist,
            newValue: newTherapist,
        });

        // Show saving indicator
        card.classList.add('drag-saving');

        try {
            // Update via API
            await API.updateAssignment(assignmentId, { therapist_name: newTherapist });

            // Validate
            const validation = await API.validateSchedule();
            const errors = validation.flags.filter(f =>
                f.severity === 'Error' || f.severity === 'Critical'
            );

            // Check for new errors involving this therapist
            const relevantErrors = errors.filter(f =>
                f.who === newTherapist || f.who === oldTherapist
            );

            if (relevantErrors.length > 0) {
                // Revert
                await API.updateAssignment(assignmentId, { therapist_name: oldTherapist });
                this._undoStack.pop(); // Remove the undo entry

                const msgs = relevantErrors.map(e => `${e.detail}`).join('; ');
                App.toast(`Can't move: ${msgs}`, 'error');

                // Refresh to snap back
                await ScheduleView.refresh();
            } else {
                App.toast(`Moved ${assignment.Client} to ${newTherapist}`, 'success');
                await ScheduleView.refresh();
            }
        } catch (err) {
            // Revert on error
            try { await API.updateAssignment(assignmentId, { therapist_name: oldTherapist }); }
            catch (_) {}
            App.toast('Move failed: ' + err.message, 'error');
            await ScheduleView.refresh();
        }
    },

    _pushUndo(action) {
        this._undoStack.push(action);
        if (this._undoStack.length > this.MAX_UNDO) {
            this._undoStack.shift();
        }
    },

    async undo() {
        const action = this._undoStack.pop();
        if (!action) {
            App.toast('Nothing to undo', '');
            return;
        }

        try {
            await API.updateAssignment(action.id, { [action.field]: action.oldValue });
            App.toast('Undone', 'success');
            await ScheduleView.refresh();
        } catch (err) {
            App.toast('Undo failed: ' + err.message, 'error');
        }
    },
};

// Ctrl+Z / Cmd+Z for undo
document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'z') {
        e.preventDefault();
        ScheduleDrag.undo();
    }
});
