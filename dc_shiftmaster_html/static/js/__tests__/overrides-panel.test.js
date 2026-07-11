/**
 * Unit/Integration tests for Override Panel
 * Feature: delete-schedule-overrides
 *
 * Tests grouped-by-month rendering, checkbox states, select-all behavior,
 * confirmation dialog integration, API payloads, and toast feedback.
 *
 * Validates: Requirements 6.1, 6.2, 6.3
 */
const fs = require('fs');
const path = require('path');

// ─── Module Loader ───────────────────────────────────────────────────────────

function setupGlobals() {
    global.AppState = {
        getYear: function () { return 2025; }
    };
    global.API = {
        getOverrides: jest.fn().mockResolvedValue([]),
        bulkDeleteOverrides: jest.fn().mockResolvedValue({ deleted_count: 0 }),
        previewBulkDelete: jest.fn().mockResolvedValue({ count: 0 })
    };
    global.Toast = {
        show: jest.fn()
    };
    global.Dashboard = {
        load: jest.fn()
    };
    global.ConfirmDialog = {
        show: jest.fn().mockReturnValue(true),
        close: jest.fn(),
        CONFIRMATION_PHRASE: 'DELETE ALL'
    };
}

function loadOverridesPanel() {
    const src = fs.readFileSync(
        path.resolve(__dirname, '..', 'overrides-panel.js'),
        'utf-8'
    );
    const script = new Function('global', `
        with (global) {
            ${src}
            global.OverridesPanel = OverridesPanel;
        }
    `);
    script(global);
}

function buildDOM() {
    document.body.innerHTML = '<div id="overrides-panel"></div>';
}

// Helper: flush microtasks
function flushPromises() {
    return new Promise(resolve => setTimeout(resolve, 0));
}

// ─── Test: Grouped-by-Month Rendering ────────────────────────────────────────

describe('Override Panel - Grouped-by-Month Rendering', () => {
    beforeEach(() => {
        buildDOM();
        setupGlobals();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        delete global.OverridesPanel;
        delete global.AppState;
        delete global.API;
        delete global.Toast;
        delete global.Dashboard;
        delete global.ConfirmDialog;
    });

    it('renders overrides grouped by month with correct headers', async () => {
        const overrides = [
            { date: '2025-01-10', shift_type: 'day', name: 'Alice' },
            { date: '2025-01-20', shift_type: 'night', name: 'Bob' },
            { date: '2025-03-05', shift_type: 'swing', name: 'Carol' }
        ];
        global.API.getOverrides.mockResolvedValue(overrides);
        loadOverridesPanel();
        global.OverridesPanel.init();
        await flushPromises();

        const monthGroups = document.querySelectorAll('.overrides-month-group');
        expect(monthGroups.length).toBe(2); // January and March

        const headers = document.querySelectorAll('.overrides-month-header');
        expect(headers[0].textContent).toBe('January 2025');
        expect(headers[1].textContent).toBe('March 2025');
    });

    it('renders correct number of override entries per month group', async () => {
        const overrides = [
            { date: '2025-02-01', shift_type: 'day', name: 'Alice' },
            { date: '2025-02-15', shift_type: 'night', name: 'Bob' },
            { date: '2025-02-28', shift_type: 'swing', name: 'Carol' },
            { date: '2025-04-10', shift_type: 'day', name: 'Dave' }
        ];
        global.API.getOverrides.mockResolvedValue(overrides);
        loadOverridesPanel();
        global.OverridesPanel.init();
        await flushPromises();

        const groups = document.querySelectorAll('.overrides-month-group');
        expect(groups.length).toBe(2);

        // February group should have 3 entries
        const febEntries = groups[0].querySelectorAll('.override-entry');
        expect(febEntries.length).toBe(3);

        // April group should have 1 entry
        const aprEntries = groups[1].querySelectorAll('.override-entry');
        expect(aprEntries.length).toBe(1);
    });

    it('displays date, shift type, and name for each override entry', async () => {
        const overrides = [
            { date: '2025-06-15', shift_type: 'night', name: 'TestPerson' }
        ];
        global.API.getOverrides.mockResolvedValue(overrides);
        loadOverridesPanel();
        global.OverridesPanel.init();
        await flushPromises();

        const entry = document.querySelector('.override-entry');
        expect(entry).not.toBeNull();
        expect(entry.querySelector('.override-date').textContent).toContain('Jun');
        expect(entry.querySelector('.override-date').textContent).toContain('15');
        expect(entry.querySelector('.override-shift').textContent).toBe('night');
        expect(entry.querySelector('.override-name').textContent).toBe('TestPerson');
    });

    it('shows empty message when no overrides exist', async () => {
        global.API.getOverrides.mockResolvedValue([]);
        loadOverridesPanel();
        global.OverridesPanel.init();
        await flushPromises();

        const emptyEl = document.getElementById('overrides-empty-message');
        expect(emptyEl.hidden).toBe(false);

        const listEl = document.getElementById('overrides-list');
        expect(listEl.innerHTML).toBe('');
    });

    it('hides empty message when overrides exist', async () => {
        const overrides = [
            { date: '2025-05-01', shift_type: 'day', name: 'Alice' }
        ];
        global.API.getOverrides.mockResolvedValue(overrides);
        loadOverridesPanel();
        global.OverridesPanel.init();
        await flushPromises();

        const emptyEl = document.getElementById('overrides-empty-message');
        expect(emptyEl.hidden).toBe(true);
    });
});

// ─── Test: Checkbox States and Select-All ────────────────────────────────────

describe('Override Panel - Checkbox States and Select-All', () => {
    const overrides = [
        { date: '2025-01-10', shift_type: 'day', name: 'Alice' },
        { date: '2025-01-20', shift_type: 'night', name: 'Bob' },
        { date: '2025-03-05', shift_type: 'swing', name: 'Carol' }
    ];

    beforeEach(async () => {
        buildDOM();
        setupGlobals();
        global.API.getOverrides.mockResolvedValue(overrides);
        loadOverridesPanel();
        global.OverridesPanel.init();
        await flushPromises();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        delete global.OverridesPanel;
        delete global.AppState;
        delete global.API;
        delete global.Toast;
        delete global.Dashboard;
        delete global.ConfirmDialog;
    });

    it('each override entry has a checkbox', () => {
        const checkboxes = document.querySelectorAll('.override-checkbox');
        expect(checkboxes.length).toBe(3);
    });

    it('checkboxes are unchecked by default', () => {
        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes.forEach(cb => expect(cb.checked).toBe(false));
    });

    it('select-all checkbox checks all override checkboxes', () => {
        const selectAll = document.getElementById('overrides-select-all');
        selectAll.checked = true;
        selectAll.dispatchEvent(new Event('change'));

        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes.forEach(cb => expect(cb.checked).toBe(true));
    });

    it('unchecking select-all unchecks all override checkboxes', () => {
        // First check all
        const selectAll = document.getElementById('overrides-select-all');
        selectAll.checked = true;
        selectAll.dispatchEvent(new Event('change'));

        // Then uncheck all
        selectAll.checked = false;
        selectAll.dispatchEvent(new Event('change'));

        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes.forEach(cb => expect(cb.checked).toBe(false));
    });

    it('delete-selected button is disabled when no checkboxes are checked', () => {
        const btn = document.getElementById('overrides-delete-selected-btn');
        expect(btn.disabled).toBe(true);
    });

    it('delete-selected button is enabled when at least one checkbox is checked', () => {
        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes[0].checked = true;
        checkboxes[0].dispatchEvent(new Event('change'));

        const btn = document.getElementById('overrides-delete-selected-btn');
        expect(btn.disabled).toBe(false);
    });

    it('select-all reflects individual checkbox state when all are checked manually', () => {
        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes.forEach(cb => {
            cb.checked = true;
            cb.dispatchEvent(new Event('change'));
        });

        const selectAll = document.getElementById('overrides-select-all');
        expect(selectAll.checked).toBe(true);
    });
});

// ─── Test: Confirmation Dialog ───────────────────────────────────────────────

describe('Override Panel - Confirmation Dialog', () => {
    const overrides = [
        { date: '2025-01-10', shift_type: 'day', name: 'Alice' },
        { date: '2025-01-20', shift_type: 'night', name: 'Bob' },
        { date: '2025-03-05', shift_type: 'swing', name: 'Carol' }
    ];

    beforeEach(async () => {
        buildDOM();
        setupGlobals();
        global.API.getOverrides.mockResolvedValue(overrides);
        loadOverridesPanel();
        global.OverridesPanel.init();
        await flushPromises();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        delete global.OverridesPanel;
        delete global.AppState;
        delete global.API;
        delete global.Toast;
        delete global.Dashboard;
        delete global.ConfirmDialog;
    });

    it('shows confirmation dialog with correct count for delete-selected', async () => {
        global.API.previewBulkDelete.mockResolvedValue({ count: 2 });

        // Select two overrides
        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes[0].checked = true;
        checkboxes[0].dispatchEvent(new Event('change'));
        checkboxes[1].checked = true;
        checkboxes[1].dispatchEvent(new Event('change'));

        // Click delete selected
        document.getElementById('overrides-delete-selected-btn').click();
        await flushPromises();

        expect(global.ConfirmDialog.show).toHaveBeenCalledWith(
            expect.objectContaining({
                message: expect.stringContaining('2'),
                requirePhrase: false
            })
        );
    });

    it('shows confirmation dialog with requirePhrase for clear-all', async () => {
        global.API.previewBulkDelete.mockResolvedValue({ count: 3 });

        // Click clear all
        document.getElementById('overrides-clear-all-btn').click();
        await flushPromises();

        expect(global.ConfirmDialog.show).toHaveBeenCalledWith(
            expect.objectContaining({
                message: expect.stringContaining('3'),
                requirePhrase: true
            })
        );
    });

    it('shows confirmation dialog with count for date range delete', async () => {
        global.API.previewBulkDelete.mockResolvedValue({ count: 5 });

        // Set date range
        const startInput = document.getElementById('overrides-start-date');
        const endInput = document.getElementById('overrides-end-date');
        startInput.value = '2025-01-01';
        endInput.value = '2025-01-31';

        // Click delete by range
        document.getElementById('overrides-delete-range-btn').click();
        await flushPromises();

        expect(global.ConfirmDialog.show).toHaveBeenCalledWith(
            expect.objectContaining({
                message: expect.stringContaining('5'),
                requirePhrase: false
            })
        );
    });

    it('blocks deletion when ConfirmDialog fails to render', async () => {
        global.ConfirmDialog.show.mockReturnValue(false);
        global.API.previewBulkDelete.mockResolvedValue({ count: 2 });

        // Select overrides and try to delete
        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes[0].checked = true;
        checkboxes[0].dispatchEvent(new Event('change'));

        document.getElementById('overrides-delete-selected-btn').click();
        await flushPromises();

        // Should show error toast about blocked deletion
        expect(global.Toast.show).toHaveBeenCalledWith(
            expect.stringContaining('Unable to display confirmation dialog'),
            'error'
        );
        // Should NOT have called bulkDeleteOverrides
        expect(global.API.bulkDeleteOverrides).not.toHaveBeenCalled();
    });
});

// ─── Test: API Payloads ──────────────────────────────────────────────────────

describe('Override Panel - API Payloads', () => {
    const overrides = [
        { date: '2025-01-10', shift_type: 'day', name: 'Alice' },
        { date: '2025-01-20', shift_type: 'night', name: 'Bob' },
        { date: '2025-03-05', shift_type: 'swing', name: 'Carol' }
    ];

    beforeEach(async () => {
        buildDOM();
        setupGlobals();
        global.API.getOverrides.mockResolvedValue(overrides);
        // Make ConfirmDialog.show immediately invoke onConfirm
        global.ConfirmDialog.show.mockImplementation(function (opts) {
            if (opts.onConfirm) opts.onConfirm();
            return true;
        });
        loadOverridesPanel();
        global.OverridesPanel.init();
        await flushPromises();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        delete global.OverridesPanel;
        delete global.AppState;
        delete global.API;
        delete global.Toast;
        delete global.Dashboard;
        delete global.ConfirmDialog;
    });

    it('sends correct range payload for date range deletion', async () => {
        global.API.previewBulkDelete.mockResolvedValue({ count: 2 });
        global.API.bulkDeleteOverrides.mockResolvedValue({ deleted_count: 2 });

        const startInput = document.getElementById('overrides-start-date');
        const endInput = document.getElementById('overrides-end-date');
        startInput.value = '2025-01-01';
        endInput.value = '2025-01-31';

        document.getElementById('overrides-delete-range-btn').click();
        await flushPromises();

        expect(global.API.previewBulkDelete).toHaveBeenCalledWith({
            mode: 'range',
            start_date: '2025-01-01',
            end_date: '2025-01-31'
        });
        expect(global.API.bulkDeleteOverrides).toHaveBeenCalledWith({
            mode: 'range',
            start_date: '2025-01-01',
            end_date: '2025-01-31'
        });
    });

    it('sends correct keys payload for selected override deletion', async () => {
        global.API.previewBulkDelete.mockResolvedValue({ count: 2 });
        global.API.bulkDeleteOverrides.mockResolvedValue({ deleted_count: 2 });

        // Select first two overrides
        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes[0].checked = true;
        checkboxes[0].dispatchEvent(new Event('change'));
        checkboxes[1].checked = true;
        checkboxes[1].dispatchEvent(new Event('change'));

        document.getElementById('overrides-delete-selected-btn').click();
        await flushPromises();

        const expectedPayload = {
            mode: 'keys',
            keys: [
                { date: '2025-01-10', shift_type: 'day' },
                { date: '2025-01-20', shift_type: 'night' }
            ]
        };
        expect(global.API.previewBulkDelete).toHaveBeenCalledWith(expectedPayload);
        expect(global.API.bulkDeleteOverrides).toHaveBeenCalledWith(expectedPayload);
    });

    it('sends correct year payload for clear-all deletion', async () => {
        global.API.previewBulkDelete.mockResolvedValue({ count: 3 });
        global.API.bulkDeleteOverrides.mockResolvedValue({ deleted_count: 3 });

        document.getElementById('overrides-clear-all-btn').click();
        await flushPromises();

        expect(global.API.previewBulkDelete).toHaveBeenCalledWith({
            mode: 'year',
            year: 2025
        });
        expect(global.API.bulkDeleteOverrides).toHaveBeenCalledWith({
            mode: 'year',
            year: 2025
        });
    });
});

// ─── Test: Toast Feedback ────────────────────────────────────────────────────

describe('Override Panel - Toast Feedback', () => {
    const overrides = [
        { date: '2025-01-10', shift_type: 'day', name: 'Alice' },
        { date: '2025-02-15', shift_type: 'night', name: 'Bob' }
    ];

    beforeEach(async () => {
        buildDOM();
        setupGlobals();
        global.API.getOverrides.mockResolvedValue(overrides);
        // Make ConfirmDialog.show immediately invoke onConfirm
        global.ConfirmDialog.show.mockImplementation(function (opts) {
            if (opts.onConfirm) opts.onConfirm();
            return true;
        });
        loadOverridesPanel();
        global.OverridesPanel.init();
        await flushPromises();
    });

    afterEach(() => {
        document.body.innerHTML = '';
        delete global.OverridesPanel;
        delete global.AppState;
        delete global.API;
        delete global.Toast;
        delete global.Dashboard;
        delete global.ConfirmDialog;
    });

    it('shows success toast with deleted count on successful deletion', async () => {
        global.API.previewBulkDelete.mockResolvedValue({ count: 2 });
        global.API.bulkDeleteOverrides.mockResolvedValue({ deleted_count: 2 });

        // Select and delete
        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes[0].checked = true;
        checkboxes[0].dispatchEvent(new Event('change'));

        document.getElementById('overrides-delete-selected-btn').click();
        await flushPromises();
        await flushPromises(); // Extra flush for the delete promise chain

        expect(global.Toast.show).toHaveBeenCalledWith(
            '2 override(s) removed.',
            'success'
        );
    });

    it('shows success toast with zero count when no overrides matched', async () => {
        global.API.previewBulkDelete.mockResolvedValue({ count: 1 });
        global.API.bulkDeleteOverrides.mockResolvedValue({ deleted_count: 0 });

        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes[0].checked = true;
        checkboxes[0].dispatchEvent(new Event('change'));

        document.getElementById('overrides-delete-selected-btn').click();
        await flushPromises();
        await flushPromises();

        expect(global.Toast.show).toHaveBeenCalledWith(
            '0 override(s) removed.',
            'success'
        );
    });

    it('shows error toast when bulk delete API fails', async () => {
        global.API.previewBulkDelete.mockResolvedValue({ count: 1 });
        global.API.bulkDeleteOverrides.mockRejectedValue(new Error('Server error'));

        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes[0].checked = true;
        checkboxes[0].dispatchEvent(new Event('change'));

        document.getElementById('overrides-delete-selected-btn').click();
        await flushPromises();
        await flushPromises();

        expect(global.Toast.show).toHaveBeenCalledWith(
            expect.stringContaining('Delete failed'),
            'error'
        );
    });

    it('shows error toast when preview API fails', async () => {
        global.API.previewBulkDelete.mockRejectedValue(new Error('Network error'));

        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes[0].checked = true;
        checkboxes[0].dispatchEvent(new Event('change'));

        document.getElementById('overrides-delete-selected-btn').click();
        await flushPromises();

        expect(global.Toast.show).toHaveBeenCalledWith(
            expect.stringContaining('Preview failed'),
            'error'
        );
    });

    it('refreshes dashboard after successful deletion', async () => {
        global.API.previewBulkDelete.mockResolvedValue({ count: 1 });
        global.API.bulkDeleteOverrides.mockResolvedValue({ deleted_count: 1 });

        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes[0].checked = true;
        checkboxes[0].dispatchEvent(new Event('change'));

        document.getElementById('overrides-delete-selected-btn').click();
        await flushPromises();
        await flushPromises();

        expect(global.Dashboard.load).toHaveBeenCalled();
    });

    it('refreshes override list after successful deletion', async () => {
        global.API.previewBulkDelete.mockResolvedValue({ count: 1 });
        global.API.bulkDeleteOverrides.mockResolvedValue({ deleted_count: 1 });

        // Clear initial call count from init
        global.API.getOverrides.mockClear();
        global.API.getOverrides.mockResolvedValue([]);

        const checkboxes = document.querySelectorAll('.override-checkbox');
        checkboxes[0].checked = true;
        checkboxes[0].dispatchEvent(new Event('change'));

        document.getElementById('overrides-delete-selected-btn').click();
        await flushPromises();
        await flushPromises();

        // Should have called getOverrides again to refresh the list
        expect(global.API.getOverrides).toHaveBeenCalledWith(2025);
    });
});
