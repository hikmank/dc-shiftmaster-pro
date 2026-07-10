/**
 * Unit tests for Custom Shift UI behavior in team.js
 * Feature: custom-schedule-shift
 *
 * Tests cover:
 * - SHIFT_TYPES array includes all five values
 * - Day selector visibility toggling based on dropdown value
 * - Checkboxes reset when switching to Custom
 * - Edit form pre-checks stored custom_days
 * - Custom group section renders with correct count
 * - Teammate row displays comma-separated day labels for Custom teammates
 *
 * Requirements: 1.1, 2.1, 2.4, 4.1, 4.2, 4.3
 */
const fs = require('fs');
const path = require('path');

/**
 * Build minimal DOM required by team.js DOMContentLoaded listener
 */
function buildDOM() {
    document.body.innerHTML = `
        <div id="team-list"></div>
        <div id="add-teammate-form" hidden></div>
        <button id="add-teammate-btn"></button>
        <button id="export-csv-btn"></button>
        <button id="import-csv-btn"></button>
        <input id="csv-file-input" type="file" />
        <div id="team-hours-warning-container"></div>
        <div id="toast-container"></div>
    `;
}

/**
 * Set up global stubs that team.js depends on
 */
function setupGlobals() {
    global.API = {
        getTeammates: function () { return Promise.resolve([]); },
        addTeammate: function () { return Promise.resolve(); },
        updateTeammate: function () { return Promise.resolve(); },
        deleteTeammate: function () { return Promise.resolve(); },
        importCsv: function () { return Promise.resolve({ imported_count: 0, skipped_rows: [] }); }
    };

    global.Toast = {
        show: function () {}
    };

    global.HoursWarningBanner = {
        updateTeamAssignment: function () {},
        clear: function () {}
    };
}

/**
 * Load team.js by evaluating its source in the current global scope.
 * The DOMContentLoaded listener within the IIFE will fire when we
 * dispatch the event manually, so we just need to make sure the DOM
 * elements exist first.
 */
function loadTeamModule() {
    const src = fs.readFileSync(
        path.resolve(__dirname, '..', 'team.js'),
        'utf-8'
    );

    const script = new Function('global', `
        with (global) {
            ${src}
            global.Team = Team;
        }
    `);
    script(global);

    // The DOMContentLoaded event may have already fired by the time the script runs,
    // so dispatch it manually to trigger the event listeners set up in team.js.
    document.dispatchEvent(new Event('DOMContentLoaded'));
}

// ─── Test Suite ───────────────────────────────────────────────────────────────

describe('Feature: custom-schedule-shift — SHIFT_TYPES constant', () => {
    beforeEach(() => {
        buildDOM();
        setupGlobals();
        loadTeamModule();
    });

    afterEach(() => {
        delete global.Team;
        delete global.API;
        delete global.Toast;
        delete global.HoursWarningBanner;
    });

    /**
     * **Validates: Requirements 1.1**
     *
     * SHIFT_TYPES array must include all five shift types: FHD, FHN, BHD, BHN, Custom
     */
    it('includes all five shift types (FHD, FHN, BHD, BHN, Custom)', () => {
        // The Add form renders options from SHIFT_TYPES — trigger the form and inspect the options
        document.getElementById('add-teammate-btn').click();
        const shiftSelect = document.getElementById('new-shift');
        expect(shiftSelect).not.toBeNull();

        const options = Array.from(shiftSelect.options).map(o => o.value);
        expect(options).toEqual(['FHD', 'FHN', 'BHD', 'BHN', 'Custom']);
    });
});


describe('Feature: custom-schedule-shift — Day selector visibility toggling', () => {
    beforeEach(() => {
        buildDOM();
        setupGlobals();
        loadTeamModule();
        // Open the add form to get the day selector in the DOM
        document.getElementById('add-teammate-btn').click();
    });

    afterEach(() => {
        delete global.Team;
        delete global.API;
        delete global.Toast;
        delete global.HoursWarningBanner;
    });

    /**
     * **Validates: Requirements 2.1**
     *
     * Day selector is visible (display != 'none') when dropdown value is 'Custom'
     */
    it('shows day selector when dropdown value is Custom', () => {
        const shiftSelect = document.getElementById('new-shift');
        shiftSelect.value = 'Custom';
        shiftSelect.dispatchEvent(new Event('change'));

        const daySelector = document.getElementById('new-day-selector');
        expect(daySelector).not.toBeNull();
        expect(daySelector.style.display).not.toBe('none');
    });

    /**
     * **Validates: Requirements 2.1**
     *
     * Day selector is hidden when dropdown value is not 'Custom'
     */
    it('hides day selector when dropdown value is a standard shift type', () => {
        const shiftSelect = document.getElementById('new-shift');

        // First switch to Custom to show it
        shiftSelect.value = 'Custom';
        shiftSelect.dispatchEvent(new Event('change'));

        // Then switch to FHD
        shiftSelect.value = 'FHD';
        shiftSelect.dispatchEvent(new Event('change'));

        const daySelector = document.getElementById('new-day-selector');
        expect(daySelector.style.display).toBe('none');
    });

    it('day selector starts hidden when initial shift type is FHD', () => {
        const daySelector = document.getElementById('new-day-selector');
        // First option is FHD, so day selector should be hidden initially
        // (toggleDaySelector is called with initial value on showAddForm)
        expect(daySelector.style.display).toBe('none');
    });
});


describe('Feature: custom-schedule-shift — Checkboxes reset when switching to Custom', () => {
    beforeEach(() => {
        buildDOM();
        setupGlobals();
        loadTeamModule();
        document.getElementById('add-teammate-btn').click();
    });

    afterEach(() => {
        delete global.Team;
        delete global.API;
        delete global.Toast;
        delete global.HoursWarningBanner;
    });

    /**
     * **Validates: Requirements 2.4**
     *
     * All checkboxes are unchecked when switching TO Custom
     */
    it('resets all day checkboxes to unchecked when switching to Custom', () => {
        const shiftSelect = document.getElementById('new-shift');

        // Switch to Custom first, check some boxes
        shiftSelect.value = 'Custom';
        shiftSelect.dispatchEvent(new Event('change'));

        const checkboxes = document.querySelectorAll('#new-day-selector .day-checkbox');
        checkboxes[0].checked = true; // Mon
        checkboxes[2].checked = true; // Wed

        // Switch away from Custom
        shiftSelect.value = 'BHN';
        shiftSelect.dispatchEvent(new Event('change'));

        // Switch back to Custom — checkboxes should all be unchecked
        shiftSelect.value = 'Custom';
        shiftSelect.dispatchEvent(new Event('change'));

        const resetCheckboxes = document.querySelectorAll('#new-day-selector .day-checkbox');
        const anyChecked = Array.from(resetCheckboxes).some(cb => cb.checked);
        expect(anyChecked).toBe(false);
    });

    it('all seven day checkboxes are present (Mon through Sun)', () => {
        const shiftSelect = document.getElementById('new-shift');
        shiftSelect.value = 'Custom';
        shiftSelect.dispatchEvent(new Event('change'));

        const checkboxes = document.querySelectorAll('#new-day-selector .day-checkbox');
        expect(checkboxes.length).toBe(7);

        const values = Array.from(checkboxes).map(cb => cb.value);
        expect(values).toEqual(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']);
    });
});


describe('Feature: custom-schedule-shift — Edit form pre-checks stored custom_days', () => {
    beforeEach(() => {
        buildDOM();
        setupGlobals();
        loadTeamModule();
    });

    afterEach(() => {
        delete global.Team;
        delete global.API;
        delete global.Toast;
        delete global.HoursWarningBanner;
    });

    /**
     * **Validates: Requirements 1.3, 3.3**
     *
     * When editing a Custom teammate, checkboxes matching t.custom_days are pre-checked
     */
    it('pre-checks checkboxes matching stored custom_days when editing a Custom teammate', async () => {
        const customTeammate = {
            id: 1,
            name: 'Alice',
            shift_type: 'Custom',
            custom_start: '',
            custom_days: ['Mon', 'Wed', 'Fri']
        };

        // Mock API to return the custom teammate
        global.API.getTeammates = function () { return Promise.resolve([customTeammate]); };

        // Load the team list
        global.Team.load();
        await new Promise(r => setTimeout(r, 0));

        // Click the Edit button on Alice's row
        const editBtn = document.querySelector('.teammate-row[data-id="1"] .btn');
        expect(editBtn).not.toBeNull();
        editBtn.click();

        // Check that the day selector is visible and correct days are checked
        const daySelector = document.getElementById('edit-day-selector');
        expect(daySelector).not.toBeNull();
        expect(daySelector.style.display).not.toBe('none');

        const checkboxes = daySelector.querySelectorAll('.day-checkbox');
        const checkedValues = Array.from(checkboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);

        expect(checkedValues.sort()).toEqual(['Fri', 'Mon', 'Wed']);
    });

    it('does not show day selector when editing a standard shift type teammate', async () => {
        const standardTeammate = {
            id: 2,
            name: 'Bob',
            shift_type: 'FHD',
            custom_start: '',
            custom_days: []
        };

        global.API.getTeammates = function () { return Promise.resolve([standardTeammate]); };

        global.Team.load();
        await new Promise(r => setTimeout(r, 0));

        const editBtn = document.querySelector('.teammate-row[data-id="2"] .btn');
        expect(editBtn).not.toBeNull();
        editBtn.click();

        const daySelector = document.getElementById('edit-day-selector');
        // Day selector should either not exist or be hidden for standard shift types
        if (daySelector) {
            expect(daySelector.style.display).toBe('none');
        }
    });
});


describe('Feature: custom-schedule-shift — Custom group section rendering', () => {
    beforeEach(() => {
        buildDOM();
        setupGlobals();
        loadTeamModule();
    });

    afterEach(() => {
        delete global.Team;
        delete global.API;
        delete global.Toast;
        delete global.HoursWarningBanner;
    });

    /**
     * **Validates: Requirements 4.1, 4.3**
     *
     * Custom group section renders with "Custom (N)" heading when Custom teammates exist
     */
    it('renders Custom group section with correct count in heading', async () => {
        const teammates = [
            { id: 1, name: 'Alice', shift_type: 'Custom', custom_start: '', custom_days: ['Mon', 'Wed'] },
            { id: 2, name: 'Bob', shift_type: 'Custom', custom_start: '', custom_days: ['Tue', 'Thu'] },
            { id: 3, name: 'Charlie', shift_type: 'FHD', custom_start: '', custom_days: [] }
        ];

        global.API.getTeammates = function () { return Promise.resolve(teammates); };

        global.Team.load();
        await new Promise(r => setTimeout(r, 0));

        const groupTitles = document.querySelectorAll('.shift-group-title');
        const customTitle = Array.from(groupTitles).find(t => t.textContent.includes('Custom'));
        expect(customTitle).not.toBeNull();
        expect(customTitle.textContent).toBe('Custom (2)');
    });

    /**
     * **Validates: Requirements 4.1**
     *
     * Custom group section is NOT rendered when no Custom teammates exist
     */
    it('does not render Custom group section when no Custom teammates exist', async () => {
        const teammates = [
            { id: 1, name: 'Alice', shift_type: 'FHD', custom_start: '', custom_days: [] },
            { id: 2, name: 'Bob', shift_type: 'BHN', custom_start: '', custom_days: [] }
        ];

        global.API.getTeammates = function () { return Promise.resolve(teammates); };

        global.Team.load();
        await new Promise(r => setTimeout(r, 0));

        const groupTitles = document.querySelectorAll('.shift-group-title');
        const customTitle = Array.from(groupTitles).find(t => t.textContent.includes('Custom'));
        expect(customTitle).toBeUndefined();
    });
});


describe('Feature: custom-schedule-shift — Custom teammate row day labels', () => {
    beforeEach(() => {
        buildDOM();
        setupGlobals();
        loadTeamModule();
    });

    afterEach(() => {
        delete global.Team;
        delete global.API;
        delete global.Toast;
        delete global.HoursWarningBanner;
    });

    /**
     * **Validates: Requirements 4.2**
     *
     * Custom teammate row shows comma-separated day labels (e.g., "Mon, Wed, Fri")
     */
    it('displays comma-separated day labels for Custom teammates', async () => {
        const teammates = [
            { id: 1, name: 'Alice', shift_type: 'Custom', custom_start: '', custom_days: ['Mon', 'Wed', 'Fri'] }
        ];

        global.API.getTeammates = function () { return Promise.resolve(teammates); };

        global.Team.load();
        await new Promise(r => setTimeout(r, 0));

        const daysSpan = document.querySelector('.teammate-row[data-id="1"] .custom-days');
        expect(daysSpan).not.toBeNull();
        expect(daysSpan.textContent).toBe('Mon, Wed, Fri');
    });

    it('does not display days span for standard shift type teammates', async () => {
        const teammates = [
            { id: 1, name: 'Bob', shift_type: 'FHD', custom_start: '', custom_days: [] }
        ];

        global.API.getTeammates = function () { return Promise.resolve(teammates); };

        global.Team.load();
        await new Promise(r => setTimeout(r, 0));

        const daysSpan = document.querySelector('.teammate-row[data-id="1"] .custom-days');
        expect(daysSpan).toBeNull();
    });

    it('displays single day correctly', async () => {
        const teammates = [
            { id: 1, name: 'Carol', shift_type: 'Custom', custom_start: '', custom_days: ['Sat'] }
        ];

        global.API.getTeammates = function () { return Promise.resolve(teammates); };

        global.Team.load();
        await new Promise(r => setTimeout(r, 0));

        const daysSpan = document.querySelector('.teammate-row[data-id="1"] .custom-days');
        expect(daysSpan).not.toBeNull();
        expect(daysSpan.textContent).toBe('Sat');
    });
});
