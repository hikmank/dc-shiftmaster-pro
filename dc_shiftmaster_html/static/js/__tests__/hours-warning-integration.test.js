/**
 * Integration tests for HoursWarningBanner — Override Modal integration
 * Feature: proactive-hours-warning
 * Validates: Requirements 4.1, 4.2, 4.3, 6.1, 6.2
 *
 * These tests simulate the Override Modal integration by testing the module's
 * public API (updateOverrideModal, clear) with a jsdom environment that includes
 * the relevant DOM elements (override modal, teammate checkboxes, hours-warning-container,
 * submit button).
 */
const fs = require('fs');
const path = require('path');

function loadWeeklySummary() {
    const src = fs.readFileSync(
        path.resolve(__dirname, '..', 'weekly-summary.js'),
        'utf-8'
    );
    const script = new Function('global', `
        with (global) {
            ${src}
            global.WeeklySummary = WeeklySummary;
        }
    `);
    script(global);
}

function loadHoursWarningBanner() {
    const src = fs.readFileSync(
        path.resolve(__dirname, '..', 'hours-warning-banner.js'),
        'utf-8'
    );
    const script = new Function('global', `
        with (global) {
            ${src}
            global.HoursWarningBanner = HoursWarningBanner;
        }
    `);
    script(global);
}

/**
 * Set up a minimal Override Modal DOM structure in the document body.
 * Returns references to key elements for test assertions.
 */
function setupOverrideModalDOM(teammateNames) {
    document.body.innerHTML = `
        <div id="override-modal" data-date="2025-01-15" hidden>
            <div id="override-teammate-list"></div>
            <select id="override-shift-type">
                <option value="day" selected>Day</option>
                <option value="night">Night</option>
            </select>
            <div id="hours-warning-container" class="hours-warning-banner-wrapper"></div>
            <button id="override-submit">Save Override</button>
            <button id="override-cancel">Cancel</button>
        </div>
    `;

    // Populate teammate checkboxes
    const listEl = document.getElementById('override-teammate-list');
    teammateNames.forEach(name => {
        const label = document.createElement('label');
        const cb = document.createElement('input');
        cb.type = 'checkbox';
        cb.value = name;
        label.appendChild(cb);
        label.appendChild(document.createTextNode(' ' + name));
        listEl.appendChild(label);
    });

    return {
        modal: document.getElementById('override-modal'),
        teammateList: document.getElementById('override-teammate-list'),
        shiftTypeSelect: document.getElementById('override-shift-type'),
        container: document.getElementById('hours-warning-container'),
        submitBtn: document.getElementById('override-submit'),
        cancelBtn: document.getElementById('override-cancel')
    };
}

/**
 * Helper: get selected names from checkboxes (simulates what dashboard.js does)
 */
function getSelectedNames() {
    const checkboxes = document.querySelectorAll('#override-teammate-list input[type="checkbox"]:checked');
    const names = [];
    checkboxes.forEach(cb => names.push(cb.value));
    return names;
}

/**
 * Helper: simulate checking/unchecking a teammate checkbox by name
 */
function setCheckboxState(name, checked) {
    const checkboxes = document.querySelectorAll('#override-teammate-list input[type="checkbox"]');
    checkboxes.forEach(cb => {
        if (cb.value === name) {
            cb.checked = checked;
        }
    });
}

describe('Override Modal Integration — HoursWarningBanner', () => {
    const shiftWindows = {
        day: { start: '06:00', end: '18:30' },
        night: { start: '18:00', end: '06:30' }
    };

    const teammates = [
        { name: 'Alice' },
        { name: 'Bob', custom_start: '07:00' },
        { name: 'Charlie' }
    ];

    let dom;

    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
        dom = setupOverrideModalDOM(['Alice', 'Bob', 'Charlie']);
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
        document.body.innerHTML = '';
    });

    describe('Checkbox change triggers banner update (Req 4.1, 4.2)', () => {
        it('checking a teammate checkbox and calling updateOverrideModal renders the banner', () => {
            setCheckboxState('Alice', true);
            const selectedNames = getSelectedNames();

            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: selectedNames,
                date: dom.modal.getAttribute('data-date'),
                shiftType: dom.shiftTypeSelect.value,
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            const banner = dom.container.querySelector('.hours-warning-banner');
            expect(banner).not.toBeNull();
            const entries = dom.container.querySelectorAll('.hours-warning-entry');
            expect(entries.length).toBe(1);
            expect(entries[0].getAttribute('aria-label')).toContain('Alice');
        });

        it('checking multiple teammates renders one entry per teammate', () => {
            setCheckboxState('Alice', true);
            setCheckboxState('Charlie', true);
            const selectedNames = getSelectedNames();

            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: selectedNames,
                date: dom.modal.getAttribute('data-date'),
                shiftType: dom.shiftTypeSelect.value,
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            const entries = dom.container.querySelectorAll('.hours-warning-entry');
            expect(entries.length).toBe(2);
        });

        it('checking a second teammate updates the banner with both entries', () => {
            // First check Alice
            setCheckboxState('Alice', true);
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: getSelectedNames(),
                date: dom.modal.getAttribute('data-date'),
                shiftType: dom.shiftTypeSelect.value,
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            expect(dom.container.querySelectorAll('.hours-warning-entry').length).toBe(1);

            // Now also check Bob
            setCheckboxState('Bob', true);
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: getSelectedNames(),
                date: dom.modal.getAttribute('data-date'),
                shiftType: dom.shiftTypeSelect.value,
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            const entries = dom.container.querySelectorAll('.hours-warning-entry');
            expect(entries.length).toBe(2);
        });
    });

    describe('Unchecking removes teammate from banner (Req 4.2)', () => {
        it('unchecking a teammate removes their entry from the banner', () => {
            // Check Alice and Bob
            setCheckboxState('Alice', true);
            setCheckboxState('Bob', true);
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: getSelectedNames(),
                date: dom.modal.getAttribute('data-date'),
                shiftType: dom.shiftTypeSelect.value,
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            expect(dom.container.querySelectorAll('.hours-warning-entry').length).toBe(2);

            // Uncheck Bob
            setCheckboxState('Bob', false);
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: getSelectedNames(),
                date: dom.modal.getAttribute('data-date'),
                shiftType: dom.shiftTypeSelect.value,
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            const entries = dom.container.querySelectorAll('.hours-warning-entry');
            expect(entries.length).toBe(1);
            expect(entries[0].getAttribute('aria-label')).toContain('Alice');
            expect(entries[0].getAttribute('aria-label')).not.toContain('Bob');
        });

        it('unchecking all but one teammate shows only that teammate', () => {
            setCheckboxState('Alice', true);
            setCheckboxState('Bob', true);
            setCheckboxState('Charlie', true);
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: getSelectedNames(),
                date: dom.modal.getAttribute('data-date'),
                shiftType: dom.shiftTypeSelect.value,
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            expect(dom.container.querySelectorAll('.hours-warning-entry').length).toBe(3);

            // Uncheck Alice and Bob
            setCheckboxState('Alice', false);
            setCheckboxState('Bob', false);
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: getSelectedNames(),
                date: dom.modal.getAttribute('data-date'),
                shiftType: dom.shiftTypeSelect.value,
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            const entries = dom.container.querySelectorAll('.hours-warning-entry');
            expect(entries.length).toBe(1);
            expect(entries[0].getAttribute('aria-label')).toContain('Charlie');
        });
    });

    describe('Empty selection hides banner (Req 4.3)', () => {
        it('unchecking all teammates clears the banner completely', () => {
            // First render a banner
            setCheckboxState('Alice', true);
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: getSelectedNames(),
                date: dom.modal.getAttribute('data-date'),
                shiftType: dom.shiftTypeSelect.value,
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            expect(dom.container.querySelector('.hours-warning-banner')).not.toBeNull();

            // Uncheck all
            setCheckboxState('Alice', false);
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: getSelectedNames(),
                date: dom.modal.getAttribute('data-date'),
                shiftType: dom.shiftTypeSelect.value,
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            expect(dom.container.querySelector('.hours-warning-banner')).toBeNull();
        });

        it('calling updateOverrideModal with empty selectedNames hides the banner', () => {
            // Render a banner first
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: ['Alice'],
                date: '2025-01-15',
                shiftType: 'day',
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            expect(dom.container.querySelector('.hours-warning-banner')).not.toBeNull();

            // Now call with empty selection
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: [],
                date: '2025-01-15',
                shiftType: 'day',
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            expect(dom.container.querySelector('.hours-warning-banner')).toBeNull();
        });

        it('no banner entries or summary remain after clearing', () => {
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: ['Alice', 'Bob'],
                date: '2025-01-15',
                shiftType: 'day',
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            // Clear
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: [],
                date: '2025-01-15',
                shiftType: 'day',
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            expect(dom.container.querySelectorAll('.hours-warning-entry').length).toBe(0);
            expect(dom.container.querySelector('.hours-warning-summary')).toBeNull();
            expect(dom.container.innerHTML).toBe('');
        });
    });

    describe('Modal close clears banner (Req 4.3, 6.4)', () => {
        it('calling clear() removes the banner from the container', () => {
            // Render a banner
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: ['Alice', 'Charlie'],
                date: '2025-01-15',
                shiftType: 'day',
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            expect(dom.container.querySelector('.hours-warning-banner')).not.toBeNull();

            // Simulate modal close by calling clear (as dashboard.js does on cancel/close)
            global.HoursWarningBanner.clear(dom.container);

            expect(dom.container.querySelector('.hours-warning-banner')).toBeNull();
        });

        it('clear() preserves other content in the container', () => {
            // Add some other content to the container
            const otherEl = document.createElement('p');
            otherEl.className = 'other-content';
            otherEl.textContent = 'Some other content';
            dom.container.appendChild(otherEl);

            // Render a banner
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: ['Alice'],
                date: '2025-01-15',
                shiftType: 'day',
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            // Clear the banner
            global.HoursWarningBanner.clear(dom.container);

            expect(dom.container.querySelector('.hours-warning-banner')).toBeNull();
            expect(dom.container.querySelector('.other-content')).not.toBeNull();
        });

        it('clear() is safe to call when no banner exists', () => {
            expect(() => {
                global.HoursWarningBanner.clear(dom.container);
            }).not.toThrow();
            expect(dom.container.querySelector('.hours-warning-banner')).toBeNull();
        });
    });

    describe('Submit button remains enabled with red-threshold banner (Req 6.1, 6.2)', () => {
        it('submit button is not disabled when banner shows green status', () => {
            // Alice with no existing hours: projected 12h (green)
            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: ['Alice'],
                date: '2025-01-15',
                shiftType: 'day',
                slots: [],
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            const submitBtn = document.getElementById('override-submit');
            expect(submitBtn.disabled).toBe(false);
        });

        it('submit button is not disabled when banner shows yellow status', () => {
            // Bob (custom_start 07:00, day shift = 11h) with 4 existing shifts = 44h
            // projected = 44 + 11 = 55h (yellow)
            const slots = [
                { date: '2025-01-12', shift_type: 'day', teammates: ['Bob'] },
                { date: '2025-01-13', shift_type: 'day', teammates: ['Bob'] },
                { date: '2025-01-14', shift_type: 'day', teammates: ['Bob'] },
                { date: '2025-01-16', shift_type: 'day', teammates: ['Bob'] }
            ];

            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: ['Bob'],
                date: '2025-01-15',
                shiftType: 'day',
                slots: slots,
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            const projectedSpan = dom.container.querySelector('.hours-warning-projected');
            expect(projectedSpan.classList.contains('compliance-yellow')).toBe(true);

            const submitBtn = document.getElementById('override-submit');
            expect(submitBtn.disabled).toBe(false);
        });

        it('submit button is not disabled when banner shows red status (≥60h)', () => {
            // Alice with 4 day shifts = 48h, adding day shift = 60h (red)
            const slots = [
                { date: '2025-01-12', shift_type: 'day', teammates: ['Alice'] },
                { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] },
                { date: '2025-01-14', shift_type: 'day', teammates: ['Alice'] },
                { date: '2025-01-16', shift_type: 'day', teammates: ['Alice'] }
            ];

            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: ['Alice'],
                date: '2025-01-15',
                shiftType: 'day',
                slots: slots,
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            // Verify the banner is showing red
            const projectedSpan = dom.container.querySelector('.hours-warning-projected');
            expect(projectedSpan.classList.contains('compliance-red')).toBe(true);
            expect(projectedSpan.textContent).toContain('projected 60h');

            // Verify the summary warning is shown
            const summary = dom.container.querySelector('.hours-warning-summary');
            expect(summary).not.toBeNull();
            expect(summary.textContent).toContain('exceeds compliance limit');

            // CRITICAL: Submit button must remain enabled (Req 6.1, 6.2)
            const submitBtn = document.getElementById('override-submit');
            expect(submitBtn.disabled).toBe(false);
        });

        it('submit button is not disabled when multiple teammates exceed red threshold', () => {
            // Alice: 4 day shifts = 48h + 12h = 60h (red)
            // Charlie: 4 day shifts = 48h + 12h = 60h (red)
            const slots = [
                { date: '2025-01-12', shift_type: 'day', teammates: ['Alice', 'Charlie'] },
                { date: '2025-01-13', shift_type: 'day', teammates: ['Alice', 'Charlie'] },
                { date: '2025-01-14', shift_type: 'day', teammates: ['Alice', 'Charlie'] },
                { date: '2025-01-16', shift_type: 'day', teammates: ['Alice', 'Charlie'] }
            ];

            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: ['Alice', 'Charlie'],
                date: '2025-01-15',
                shiftType: 'day',
                slots: slots,
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            // Verify multiple red entries
            const summary = dom.container.querySelector('.hours-warning-summary');
            expect(summary).not.toBeNull();
            expect(summary.textContent).toContain('2 teammates exceed compliance limit');

            // Submit button must still be enabled
            const submitBtn = document.getElementById('override-submit');
            expect(submitBtn.disabled).toBe(false);
        });

        it('submit button has no disabled attribute set by the banner module', () => {
            // Render a red-threshold banner
            const slots = [
                { date: '2025-01-12', shift_type: 'day', teammates: ['Alice'] },
                { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] },
                { date: '2025-01-14', shift_type: 'day', teammates: ['Alice'] },
                { date: '2025-01-16', shift_type: 'day', teammates: ['Alice'] },
                { date: '2025-01-17', shift_type: 'day', teammates: ['Alice'] }
            ];

            global.HoursWarningBanner.updateOverrideModal({
                selectedNames: ['Alice'],
                date: '2025-01-15',
                shiftType: 'day',
                slots: slots,
                teammates: teammates,
                shiftWindows: shiftWindows,
                container: dom.container
            });

            // projected = 60h + 12h = 72h (well into red)
            const projectedSpan = dom.container.querySelector('.hours-warning-projected');
            expect(projectedSpan.classList.contains('compliance-red')).toBe(true);

            // The submit button must not have a disabled attribute
            const submitBtn = document.getElementById('override-submit');
            expect(submitBtn.hasAttribute('disabled')).toBe(false);
        });
    });
});
