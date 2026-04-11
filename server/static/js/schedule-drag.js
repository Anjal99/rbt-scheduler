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
                filter: '.locked-hard',  // Prevent dragging hard-locked cards
                delay: 150,           // Long-press on mobile
                delayOnTouchOnly: true,
                touchStartThreshold: 3,
                onMove: (evt) => {
                    // Block dragging hard-locked items
                    if (evt.dragged && evt.dragged.dataset.lock === 'hard') return false;
                },
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

        // Block drag for hard-locked assignments
        if (assignment.LockType === 'hard') {
            App.toast('Cannot move a hard-locked assignment', 'error');
            await ScheduleView.refresh();
            return;
        }

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

            // Validate — only block on overlaps for the target therapist on this day
            const validation = await API.validateSchedule();
            const overlaps = validation.flags.filter(f =>
                f.rule === 'Overlap' &&
                f.who === newTherapist &&
                f.day === assignment.Day
            );
            const locationConflicts = validation.flags.filter(f =>
                f.severity === 'Critical' &&
                f.who === newTherapist &&
                f.day === assignment.Day
            );

            const blockers = [...overlaps, ...locationConflicts];

            if (blockers.length > 0) {
                // Revert — there's a real conflict
                await API.updateAssignment(assignmentId, { therapist_name: oldTherapist });
                this._undoStack.pop();

                const msg = blockers[0].rule === 'Overlap'
                    ? `Time conflict with another assignment on ${assignment.Day}`
                    : `Location conflict for ${newTherapist}`;
                App.toast(msg, 'error');

                await ScheduleView.refresh();
            } else {
                // Check for non-blocking warnings
                const warnings = validation.flags.filter(f =>
                    (f.severity === 'Warning' || f.severity === 'Info') &&
                    f.who === newTherapist
                );
                if (warnings.length > 0) {
                    App.toast(`Moved to ${newTherapist} (${warnings.length} warning${warnings.length > 1 ? 's' : ''})`, 'success');
                } else {
                    App.toast(`Moved ${assignment.Client} to ${newTherapist}`, 'success');
                }
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
