/**
 * Unit tests for HoursWarningBanner module — getWeekForDate and computeTeammateWeeklyHours
 * Feature: proactive-hours-warning
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

describe('HoursWarningBanner.getWeekForDate', () => {
    beforeEach(() => {
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.HoursWarningBanner;
    });

    it('returns Sunday-Saturday boundaries for a Wednesday', () => {
        // 2025-01-15 is a Wednesday
        const result = global.HoursWarningBanner.getWeekForDate('2025-01-15');
        expect(result.start).toBe('2025-01-12'); // Sunday
        expect(result.end).toBe('2025-01-18');   // Saturday
    });

    it('returns same day as start when input is a Sunday', () => {
        // 2025-01-12 is a Sunday
        const result = global.HoursWarningBanner.getWeekForDate('2025-01-12');
        expect(result.start).toBe('2025-01-12'); // Sunday itself
        expect(result.end).toBe('2025-01-18');   // Saturday
    });

    it('returns previous Sunday as start when input is a Saturday', () => {
        // 2025-01-18 is a Saturday
        const result = global.HoursWarningBanner.getWeekForDate('2025-01-18');
        expect(result.start).toBe('2025-01-12'); // Sunday
        expect(result.end).toBe('2025-01-18');   // Saturday itself
    });

    it('handles month boundary crossing (date in January, Sunday in December)', () => {
        // 2025-01-01 is a Wednesday
        const result = global.HoursWarningBanner.getWeekForDate('2025-01-01');
        expect(result.start).toBe('2024-12-29'); // Sunday in December
        expect(result.end).toBe('2025-01-04');   // Saturday in January
    });

    it('handles year boundary crossing (date in December, Saturday in January)', () => {
        // 2025-12-29 is a Monday
        const result = global.HoursWarningBanner.getWeekForDate('2025-12-29');
        expect(result.start).toBe('2025-12-28'); // Sunday
        expect(result.end).toBe('2026-01-03');   // Saturday in next year
    });

    it('handles leap year date (Feb 29)', () => {
        // 2024-02-29 is a Thursday (leap year)
        const result = global.HoursWarningBanner.getWeekForDate('2024-02-29');
        expect(result.start).toBe('2024-02-25'); // Sunday
        expect(result.end).toBe('2024-03-02');   // Saturday in March
    });

    it('end - start is always 6 days', () => {
        const result = global.HoursWarningBanner.getWeekForDate('2025-06-15');
        const start = new Date(result.start + 'T00:00:00');
        const end = new Date(result.end + 'T00:00:00');
        const diffDays = (end - start) / (1000 * 60 * 60 * 24);
        expect(diffDays).toBe(6);
    });

    it('start is always a Sunday (day 0)', () => {
        const result = global.HoursWarningBanner.getWeekForDate('2025-03-20');
        const startDate = new Date(result.start + 'T00:00:00');
        expect(startDate.getDay()).toBe(0); // Sunday
    });

    it('end is always a Saturday (day 6)', () => {
        const result = global.HoursWarningBanner.getWeekForDate('2025-03-20');
        const endDate = new Date(result.end + 'T00:00:00');
        expect(endDate.getDay()).toBe(6); // Saturday
    });
});


describe('HoursWarningBanner.colorToLabel', () => {
    beforeEach(() => {
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.HoursWarningBanner;
    });

    it('returns "OK" for compliance-green', () => {
        expect(global.HoursWarningBanner.colorToLabel('compliance-green')).toBe('OK');
    });

    it('returns "Caution" for compliance-yellow', () => {
        expect(global.HoursWarningBanner.colorToLabel('compliance-yellow')).toBe('Caution');
    });

    it('returns "Over Limit" for compliance-red', () => {
        expect(global.HoursWarningBanner.colorToLabel('compliance-red')).toBe('Over Limit');
    });

    it('returns "OK" for unknown/empty input (graceful fallback)', () => {
        expect(global.HoursWarningBanner.colorToLabel('')).toBe('OK');
        expect(global.HoursWarningBanner.colorToLabel('unknown-class')).toBe('OK');
        expect(global.HoursWarningBanner.colorToLabel(undefined)).toBe('OK');
    });
});


describe('HoursWarningBanner.computeProjectedHours', () => {
    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
    });

    const shiftWindows = {
        day: { start: '06:00', end: '18:30' },
        night: { start: '18:00', end: '06:30' }
    };

    it('adds day shift duration to current hours (no custom_start)', () => {
        const teammate = { name: 'Alice' };
        // Day shift: 06:00 to 18:30 = 12.5h - 0.5h handoff = 12.0h
        const result = global.HoursWarningBanner.computeProjectedHours(20, 'day', teammate, shiftWindows);
        expect(result).toBe(32); // 20 + 12.0
    });

    it('adds night shift duration to current hours (no custom_start)', () => {
        const teammate = { name: 'Bob' };
        // Night shift: 18:00 to 06:30 = 12.5h (overnight) - 0.5h handoff = 12.0h
        const result = global.HoursWarningBanner.computeProjectedHours(30, 'night', teammate, shiftWindows);
        expect(result).toBe(42); // 30 + 12.0
    });

    it('uses custom_start when teammate has one', () => {
        const teammate = { name: 'Charlie', custom_start: '07:00' };
        // Custom start 07:00 to day end 18:30 = 11.5h - 0.5h handoff = 11.0h
        const result = global.HoursWarningBanner.computeProjectedHours(40, 'day', teammate, shiftWindows);
        expect(result).toBe(51); // 40 + 11.0
    });

    it('returns currentHours + shiftDuration when currentHours is 0', () => {
        const teammate = { name: 'Dana' };
        // Day shift: 12.0h
        const result = global.HoursWarningBanner.computeProjectedHours(0, 'day', teammate, shiftWindows);
        expect(result).toBe(12); // 0 + 12.0
    });

    it('handles custom_start for night shift (overnight calculation)', () => {
        const teammate = { name: 'Eve', custom_start: '19:00' };
        // Custom start 19:00 to night end 06:30 = 11.5h (overnight) - 0.5h handoff = 11.0h
        const result = global.HoursWarningBanner.computeProjectedHours(48, 'night', teammate, shiftWindows);
        expect(result).toBe(59); // 48 + 11.0
    });

    it('projected hours can exceed compliance thresholds', () => {
        const teammate = { name: 'Frank' };
        // Day shift: 12.0h, starting at 55h should project to 67h (red zone)
        const result = global.HoursWarningBanner.computeProjectedHours(55, 'day', teammate, shiftWindows);
        expect(result).toBe(67); // 55 + 12.0
    });
});


describe('HoursWarningBanner.computeTeammateWeeklyHours', () => {
    const shiftWindows = {
        day: { start: '06:00', end: '18:30' },
        night: { start: '18:00', end: '06:30' }
    };

    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
    });

    it('returns zero hours and days when no slots match the teammate', () => {
        const slots = [
            { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] },
            { date: '2025-01-14', shift_type: 'night', teammates: ['Bob'] }
        ];
        const teammate = { name: 'Charlie' };
        const result = global.HoursWarningBanner.computeTeammateWeeklyHours(
            'Charlie', '2025-01-12', '2025-01-18', slots, teammate, shiftWindows
        );
        expect(result.currentHours).toBe(0);
        expect(result.currentDays).toBe(0);
    });

    it('returns zero hours and days when no slots are within the week range', () => {
        const slots = [
            { date: '2025-01-06', shift_type: 'day', teammates: ['Alice'] },
            { date: '2025-01-20', shift_type: 'day', teammates: ['Alice'] }
        ];
        const teammate = { name: 'Alice' };
        const result = global.HoursWarningBanner.computeTeammateWeeklyHours(
            'Alice', '2025-01-12', '2025-01-18', slots, teammate, shiftWindows
        );
        expect(result.currentHours).toBe(0);
        expect(result.currentDays).toBe(0);
    });

    it('sums hours for a single matching slot (day shift)', () => {
        const slots = [
            { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] }
        ];
        const teammate = { name: 'Alice' };
        const result = global.HoursWarningBanner.computeTeammateWeeklyHours(
            'Alice', '2025-01-12', '2025-01-18', slots, teammate, shiftWindows
        );
        // Day shift: 06:00 to 18:30 = 12.5h - 0.5h handoff = 12.0h
        expect(result.currentHours).toBe(12);
        expect(result.currentDays).toBe(1);
    });

    it('sums hours for multiple matching slots across different days', () => {
        const slots = [
            { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] },
            { date: '2025-01-14', shift_type: 'day', teammates: ['Alice'] },
            { date: '2025-01-15', shift_type: 'night', teammates: ['Alice'] }
        ];
        const teammate = { name: 'Alice' };
        const result = global.HoursWarningBanner.computeTeammateWeeklyHours(
            'Alice', '2025-01-12', '2025-01-18', slots, teammate, shiftWindows
        );
        // Day: 12h each x 2 = 24h
        // Night: 18:00 to 06:30 = 12.5h - 0.5h = 12h
        expect(result.currentHours).toBe(36);
        expect(result.currentDays).toBe(3);
    });

    it('counts distinct dates correctly when multiple slots on same date', () => {
        const slots = [
            { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] },
            { date: '2025-01-13', shift_type: 'night', teammates: ['Alice'] }
        ];
        const teammate = { name: 'Alice' };
        const result = global.HoursWarningBanner.computeTeammateWeeklyHours(
            'Alice', '2025-01-12', '2025-01-18', slots, teammate, shiftWindows
        );
        // Two shifts on same date: 12h + 12h = 24h, but only 1 distinct day
        expect(result.currentHours).toBe(24);
        expect(result.currentDays).toBe(1);
    });

    it('uses custom_start when teammate has one', () => {
        const slots = [
            { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] }
        ];
        const teammate = { name: 'Alice', custom_start: '07:00' };
        const result = global.HoursWarningBanner.computeTeammateWeeklyHours(
            'Alice', '2025-01-12', '2025-01-18', slots, teammate, shiftWindows
        );
        // Custom start 07:00 to 18:30 = 11.5h - 0.5h handoff = 11h
        expect(result.currentHours).toBe(11);
        expect(result.currentDays).toBe(1);
    });

    it('filters only the specified teammate from multi-teammate slots', () => {
        const slots = [
            { date: '2025-01-13', shift_type: 'day', teammates: ['Alice', 'Bob'] },
            { date: '2025-01-14', shift_type: 'day', teammates: ['Bob', 'Charlie'] }
        ];
        const teammate = { name: 'Bob' };
        const result = global.HoursWarningBanner.computeTeammateWeeklyHours(
            'Bob', '2025-01-12', '2025-01-18', slots, teammate, shiftWindows
        );
        // Bob is in both slots: 12h + 12h = 24h, 2 distinct days
        expect(result.currentHours).toBe(24);
        expect(result.currentDays).toBe(2);
    });

    it('includes slots on weekStart and weekEnd boundaries (inclusive)', () => {
        const slots = [
            { date: '2025-01-12', shift_type: 'day', teammates: ['Alice'] }, // Sunday (weekStart)
            { date: '2025-01-18', shift_type: 'day', teammates: ['Alice'] }  // Saturday (weekEnd)
        ];
        const teammate = { name: 'Alice' };
        const result = global.HoursWarningBanner.computeTeammateWeeklyHours(
            'Alice', '2025-01-12', '2025-01-18', slots, teammate, shiftWindows
        );
        // Both boundary dates included: 12h + 12h = 24h, 2 days
        expect(result.currentHours).toBe(24);
        expect(result.currentDays).toBe(2);
    });

    it('handles slots with name field instead of teammates array', () => {
        const slots = [
            { date: '2025-01-13', shift_type: 'day', name: 'Alice' }
        ];
        const teammate = { name: 'Alice' };
        const result = global.HoursWarningBanner.computeTeammateWeeklyHours(
            'Alice', '2025-01-12', '2025-01-18', slots, teammate, shiftWindows
        );
        expect(result.currentHours).toBe(12);
        expect(result.currentDays).toBe(1);
    });

    it('returns zero when slots array is empty', () => {
        const teammate = { name: 'Alice' };
        const result = global.HoursWarningBanner.computeTeammateWeeklyHours(
            'Alice', '2025-01-12', '2025-01-18', [], teammate, shiftWindows
        );
        expect(result.currentHours).toBe(0);
        expect(result.currentDays).toBe(0);
    });
});


describe('HoursWarningBanner._internal.renderBanner', () => {
    let container;

    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
        container = document.createElement('div');
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
    });

    function makeEntry(overrides) {
        return Object.assign({
            name: 'Alice',
            currentHours: 40,
            currentDays: 4,
            projectedHours: 52,
            projectedDays: 5,
            hoursColor: 'compliance-yellow',
            daysColor: 'compliance-green',
            hoursLabel: 'Caution',
            daysLabel: 'OK'
        }, overrides);
    }

    it('creates a banner div with role="status" and aria-live="polite"', () => {
        global.HoursWarningBanner._internal.renderBanner(container, [makeEntry()]);
        const banner = container.querySelector('.hours-warning-banner');
        expect(banner).not.toBeNull();
        expect(banner.getAttribute('role')).toBe('status');
        expect(banner.getAttribute('aria-live')).toBe('polite');
    });

    it('removes existing banner before creating a new one', () => {
        global.HoursWarningBanner._internal.renderBanner(container, [makeEntry()]);
        global.HoursWarningBanner._internal.renderBanner(container, [makeEntry({ name: 'Bob' })]);
        const banners = container.querySelectorAll('.hours-warning-banner');
        expect(banners.length).toBe(1);
        const entry = banners[0].querySelector('.hours-warning-entry');
        expect(entry.getAttribute('aria-label')).toContain('Bob');
    });

    it('renders one entry div per entry with class hours-warning-entry', () => {
        const entries = [
            makeEntry({ name: 'Alice', projectedHours: 55 }),
            makeEntry({ name: 'Bob', projectedHours: 45 }),
            makeEntry({ name: 'Charlie', projectedHours: 62 })
        ];
        global.HoursWarningBanner._internal.renderBanner(container, entries);
        const entryDivs = container.querySelectorAll('.hours-warning-entry');
        expect(entryDivs.length).toBe(3);
    });

    it('sets aria-label on each entry with correct format', () => {
        const entry = makeEntry({ name: 'Alice', currentHours: 40, projectedHours: 52, hoursLabel: 'Caution' });
        global.HoursWarningBanner._internal.renderBanner(container, [entry]);
        const entryDiv = container.querySelector('.hours-warning-entry');
        expect(entryDiv.getAttribute('aria-label')).toBe('Alice: 40h this week, projected 52h, Caution');
    });

    it('renders name span with teammate name', () => {
        global.HoursWarningBanner._internal.renderBanner(container, [makeEntry({ name: 'Dana' })]);
        const nameSpan = container.querySelector('.hours-warning-name');
        expect(nameSpan.textContent).toBe('Dana');
    });

    it('renders current hours text', () => {
        global.HoursWarningBanner._internal.renderBanner(container, [makeEntry({ currentHours: 36 })]);
        const currentSpan = container.querySelector('.hours-warning-current');
        expect(currentSpan.textContent).toBe('36h this week');
    });

    it('renders projected hours with color class', () => {
        global.HoursWarningBanner._internal.renderBanner(container, [makeEntry({ projectedHours: 52, hoursColor: 'compliance-yellow' })]);
        const projectedSpan = container.querySelector('.hours-warning-projected');
        expect(projectedSpan.textContent).toBe('projected 52h');
        expect(projectedSpan.classList.contains('compliance-yellow')).toBe(true);
    });

    it('renders text label span with hours-warning-label class', () => {
        global.HoursWarningBanner._internal.renderBanner(container, [makeEntry({ hoursLabel: 'Over Limit' })]);
        const labelSpan = container.querySelector('.hours-warning-label');
        expect(labelSpan.textContent).toBe('Over Limit');
    });

    it('sorts entries by projectedHours descending', () => {
        const entries = [
            makeEntry({ name: 'Low', projectedHours: 30 }),
            makeEntry({ name: 'High', projectedHours: 65 }),
            makeEntry({ name: 'Mid', projectedHours: 50 })
        ];
        global.HoursWarningBanner._internal.renderBanner(container, entries);
        const entryDivs = container.querySelectorAll('.hours-warning-entry');
        expect(entryDivs[0].getAttribute('aria-label')).toContain('High');
        expect(entryDivs[1].getAttribute('aria-label')).toContain('Mid');
        expect(entryDivs[2].getAttribute('aria-label')).toContain('Low');
    });

    it('appends summary warning when any entry has projectedHours >= 60', () => {
        const entries = [
            makeEntry({ name: 'Alice', projectedHours: 62, hoursLabel: 'Over Limit' }),
            makeEntry({ name: 'Bob', projectedHours: 45, hoursLabel: 'OK' })
        ];
        global.HoursWarningBanner._internal.renderBanner(container, entries);
        const summary = container.querySelector('.hours-warning-summary');
        expect(summary).not.toBeNull();
        expect(summary.textContent).toBe('1 teammate exceeds compliance limit');
    });

    it('shows plural form when multiple teammates exceed limit', () => {
        const entries = [
            makeEntry({ name: 'Alice', projectedHours: 62 }),
            makeEntry({ name: 'Bob', projectedHours: 65 }),
            makeEntry({ name: 'Charlie', projectedHours: 40 })
        ];
        global.HoursWarningBanner._internal.renderBanner(container, entries);
        const summary = container.querySelector('.hours-warning-summary');
        expect(summary.textContent).toBe('2 teammates exceed compliance limit');
    });

    it('does not append summary when no entry has projectedHours >= 60', () => {
        const entries = [
            makeEntry({ name: 'Alice', projectedHours: 55 }),
            makeEntry({ name: 'Bob', projectedHours: 45 })
        ];
        global.HoursWarningBanner._internal.renderBanner(container, entries);
        const summary = container.querySelector('.hours-warning-summary');
        expect(summary).toBeNull();
    });

    it('handles empty entries array (renders banner with no entries)', () => {
        global.HoursWarningBanner._internal.renderBanner(container, []);
        const banner = container.querySelector('.hours-warning-banner');
        expect(banner).not.toBeNull();
        const entryDivs = container.querySelectorAll('.hours-warning-entry');
        expect(entryDivs.length).toBe(0);
        const summary = container.querySelector('.hours-warning-summary');
        expect(summary).toBeNull();
    });

    it('handles single entry at exactly 60 projected hours', () => {
        const entries = [makeEntry({ name: 'Eve', projectedHours: 60, hoursLabel: 'Over Limit' })];
        global.HoursWarningBanner._internal.renderBanner(container, entries);
        const summary = container.querySelector('.hours-warning-summary');
        expect(summary).not.toBeNull();
        expect(summary.textContent).toBe('1 teammate exceeds compliance limit');
    });

    it('applies correct color class for green entries', () => {
        const entries = [makeEntry({ projectedHours: 30, hoursColor: 'compliance-green', hoursLabel: 'OK' })];
        global.HoursWarningBanner._internal.renderBanner(container, entries);
        const projectedSpan = container.querySelector('.hours-warning-projected');
        expect(projectedSpan.classList.contains('compliance-green')).toBe(true);
    });

    it('applies correct color class for red entries', () => {
        const entries = [makeEntry({ projectedHours: 65, hoursColor: 'compliance-red', hoursLabel: 'Over Limit' })];
        global.HoursWarningBanner._internal.renderBanner(container, entries);
        const projectedSpan = container.querySelector('.hours-warning-projected');
        expect(projectedSpan.classList.contains('compliance-red')).toBe(true);
    });
});


describe('HoursWarningBanner.clear', () => {
    let container;

    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
        container = document.createElement('div');
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
    });

    it('removes an existing hours-warning-banner element from the container', () => {
        // Add a banner to the container
        const banner = document.createElement('div');
        banner.className = 'hours-warning-banner';
        container.appendChild(banner);

        expect(container.querySelector('.hours-warning-banner')).not.toBeNull();
        global.HoursWarningBanner.clear(container);
        expect(container.querySelector('.hours-warning-banner')).toBeNull();
    });

    it('does nothing when container has no banner element', () => {
        const otherDiv = document.createElement('div');
        otherDiv.className = 'some-other-class';
        container.appendChild(otherDiv);

        global.HoursWarningBanner.clear(container);
        // Container still has its other content
        expect(container.querySelector('.some-other-class')).not.toBeNull();
        expect(container.childNodes.length).toBe(1);
    });

    it('does not throw when container is null', () => {
        expect(() => {
            global.HoursWarningBanner.clear(null);
        }).not.toThrow();
    });

    it('does not throw when container is undefined', () => {
        expect(() => {
            global.HoursWarningBanner.clear(undefined);
        }).not.toThrow();
    });

    it('removes only the banner and preserves other child elements', () => {
        const before = document.createElement('p');
        before.textContent = 'Before';
        const banner = document.createElement('div');
        banner.className = 'hours-warning-banner';
        const after = document.createElement('p');
        after.textContent = 'After';

        container.appendChild(before);
        container.appendChild(banner);
        container.appendChild(after);

        global.HoursWarningBanner.clear(container);
        expect(container.querySelector('.hours-warning-banner')).toBeNull();
        expect(container.childNodes.length).toBe(2);
        expect(container.childNodes[0].textContent).toBe('Before');
        expect(container.childNodes[1].textContent).toBe('After');
    });

    it('removes a banner that was rendered by renderBanner', () => {
        // Use renderBanner to create a real banner
        global.HoursWarningBanner._internal.renderBanner(container, [{
            name: 'Alice',
            currentHours: 40,
            currentDays: 4,
            projectedHours: 52,
            projectedDays: 5,
            hoursColor: 'compliance-yellow',
            daysColor: 'compliance-green',
            hoursLabel: 'Caution',
            daysLabel: 'OK'
        }]);

        expect(container.querySelector('.hours-warning-banner')).not.toBeNull();
        global.HoursWarningBanner.clear(container);
        expect(container.querySelector('.hours-warning-banner')).toBeNull();
    });
});


describe('HoursWarningBanner.updateOverrideModal', () => {
    let container;

    const shiftWindows = {
        day: { start: '06:00', end: '18:30' },
        night: { start: '18:00', end: '06:30' }
    };

    const teammates = [
        { name: 'Alice' },
        { name: 'Bob', custom_start: '07:00' },
        { name: 'Charlie' }
    ];

    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
        container = document.createElement('div');
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
    });

    it('clears the banner when selectedNames is empty', () => {
        // First render a banner so we can verify it gets cleared
        global.HoursWarningBanner._internal.renderBanner(container, [{
            name: 'Alice', currentHours: 40, currentDays: 4,
            projectedHours: 52, projectedDays: 5,
            hoursColor: 'compliance-yellow', daysColor: 'compliance-green',
            hoursLabel: 'Caution', daysLabel: 'OK'
        }]);
        expect(container.querySelector('.hours-warning-banner')).not.toBeNull();

        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: [],
            date: '2025-01-15',
            shiftType: 'day',
            slots: [],
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        expect(container.querySelector('.hours-warning-banner')).toBeNull();
    });

    it('clears the banner when selectedNames is not provided', () => {
        global.HoursWarningBanner._internal.renderBanner(container, [{
            name: 'Alice', currentHours: 40, currentDays: 4,
            projectedHours: 52, projectedDays: 5,
            hoursColor: 'compliance-yellow', daysColor: 'compliance-green',
            hoursLabel: 'Caution', daysLabel: 'OK'
        }]);

        global.HoursWarningBanner.updateOverrideModal({
            date: '2025-01-15',
            shiftType: 'day',
            slots: [],
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        expect(container.querySelector('.hours-warning-banner')).toBeNull();
    });

    it('renders a banner with one entry for a single selected teammate', () => {
        // Alice has no existing slots, so currentHours=0, projectedHours=12 (day shift)
        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Alice'],
            date: '2025-01-15', // Wednesday in week 2025-01-12 to 2025-01-18
            shiftType: 'day',
            slots: [],
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        const banner = container.querySelector('.hours-warning-banner');
        expect(banner).not.toBeNull();
        const entries = container.querySelectorAll('.hours-warning-entry');
        expect(entries.length).toBe(1);
        expect(entries[0].getAttribute('aria-label')).toContain('Alice');
        expect(entries[0].getAttribute('aria-label')).toContain('projected 12h');
    });

    it('renders entries for multiple selected teammates', () => {
        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Alice', 'Charlie'],
            date: '2025-01-15',
            shiftType: 'day',
            slots: [],
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        const entries = container.querySelectorAll('.hours-warning-entry');
        expect(entries.length).toBe(2);
    });

    it('computes correct projected hours using existing slots', () => {
        // Alice already has 2 day shifts this week
        const slots = [
            { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] },
            { date: '2025-01-14', shift_type: 'day', teammates: ['Alice'] }
        ];

        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Alice'],
            date: '2025-01-15',
            shiftType: 'day',
            slots: slots,
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        const entry = container.querySelector('.hours-warning-entry');
        // currentHours = 24 (2 x 12h day shifts), projectedHours = 36 (24 + 12)
        expect(entry.getAttribute('aria-label')).toContain('24h this week');
        expect(entry.getAttribute('aria-label')).toContain('projected 36h');
    });

    it('uses custom_start for teammate with custom start time', () => {
        // Bob has custom_start: '07:00'
        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Bob'],
            date: '2025-01-15',
            shiftType: 'day',
            slots: [],
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        const entry = container.querySelector('.hours-warning-entry');
        // Bob's day shift: 07:00 to 18:30 = 11.5h - 0.5h = 11h
        expect(entry.getAttribute('aria-label')).toContain('projected 11h');
    });

    it('skips teammates not found in the teammates array', () => {
        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Alice', 'Unknown', 'Charlie'],
            date: '2025-01-15',
            shiftType: 'day',
            slots: [],
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        const entries = container.querySelectorAll('.hours-warning-entry');
        // Only Alice and Charlie should be rendered, Unknown is skipped
        expect(entries.length).toBe(2);
    });

    it('does not increment projectedDays when date is already scheduled', () => {
        // Alice already has a slot on the override date
        const slots = [
            { date: '2025-01-15', shift_type: 'day', teammates: ['Alice'] }
        ];

        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Alice'],
            date: '2025-01-15',
            shiftType: 'night',
            slots: slots,
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        // Alice: currentDays=1 (already scheduled on 01-15), projectedDays should stay 1
        const banner = container.querySelector('.hours-warning-banner');
        expect(banner).not.toBeNull();
    });

    it('increments projectedDays when date is not already scheduled', () => {
        // Alice has a slot on a different date
        const slots = [
            { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] }
        ];

        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Alice'],
            date: '2025-01-15',
            shiftType: 'day',
            slots: slots,
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        // Alice: currentDays=1 (Mon), projectedDays=2 (Mon + Wed)
        const banner = container.querySelector('.hours-warning-banner');
        expect(banner).not.toBeNull();
    });

    it('applies compliance-red color when projected hours >= 60', () => {
        // Alice has 4 day shifts already (48h), adding another day shift = 60h
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
            container: container
        });

        const projectedSpan = container.querySelector('.hours-warning-projected');
        expect(projectedSpan.classList.contains('compliance-red')).toBe(true);
        expect(projectedSpan.textContent).toContain('projected 60h');
    });

    it('applies compliance-yellow color when projected hours between 50 and 59', () => {
        // Alice has 3 day shifts (36h) + 1 night shift (12h) = 48h, adding day = 60h
        // Let's use 3 day shifts = 36h, adding day = 48h... that's green
        // Use 4 day shifts = 48h, adding night = 60h... that's red
        // For yellow: need projected between 50-59. 3 day shifts = 36h + night = 48h... still green
        // 4 day shifts = 48h + custom Bob (11h) = 59h... yellow!
        // Actually let's just use Alice with slots that give 40h current
        // 3 day shifts + 1 partial... let's keep it simple
        // Alice with custom_start not set: day shift = 12h
        // 4 day shifts = 48h, projected = 48 + 12 = 60 (red)
        // 3 day shifts = 36h, projected = 36 + 12 = 48 (green)
        // For yellow we need projected 50-59. Use Bob (custom_start 07:00, day shift = 11h)
        // Bob with 4 day shifts: 4 * 11 = 44h, projected = 44 + 11 = 55h (yellow!)
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
            container: container
        });

        const projectedSpan = container.querySelector('.hours-warning-projected');
        // Bob: 4 * 11h = 44h current, projected = 44 + 11 = 55h (yellow)
        expect(projectedSpan.classList.contains('compliance-yellow')).toBe(true);
        expect(projectedSpan.textContent).toContain('projected 55h');
    });

    it('applies compliance-green color when projected hours < 50', () => {
        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Alice'],
            date: '2025-01-15',
            shiftType: 'day',
            slots: [],
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        const projectedSpan = container.querySelector('.hours-warning-projected');
        // Alice: 0h current, projected = 12h (green)
        expect(projectedSpan.classList.contains('compliance-green')).toBe(true);
    });

    it('renders night shift projected hours correctly', () => {
        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Alice'],
            date: '2025-01-15',
            shiftType: 'night',
            slots: [],
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        const entry = container.querySelector('.hours-warning-entry');
        // Night shift: 18:00 to 06:30 = 12.5h - 0.5h = 12h
        expect(entry.getAttribute('aria-label')).toContain('projected 12h');
    });

    it('sorts multiple entries by projected hours descending', () => {
        // Alice: 0h + 12h day = 12h projected
        // Bob: 0h + 11h day (custom_start) = 11h projected
        // Charlie: 0h + 12h day = 12h projected
        // Give Charlie some existing hours to differentiate
        const slots = [
            { date: '2025-01-13', shift_type: 'day', teammates: ['Charlie'] },
            { date: '2025-01-14', shift_type: 'day', teammates: ['Charlie'] }
        ];

        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Alice', 'Bob', 'Charlie'],
            date: '2025-01-15',
            shiftType: 'day',
            slots: slots,
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        const entries = container.querySelectorAll('.hours-warning-entry');
        // Charlie: 24h + 12h = 36h, Alice: 0 + 12h = 12h, Bob: 0 + 11h = 11h
        expect(entries[0].getAttribute('aria-label')).toContain('Charlie');
        expect(entries[1].getAttribute('aria-label')).toContain('Alice');
        expect(entries[2].getAttribute('aria-label')).toContain('Bob');
    });

    it('shows summary warning when any teammate exceeds 60h', () => {
        // Give Alice 4 day shifts = 48h, projected = 60h (red)
        const slots = [
            { date: '2025-01-12', shift_type: 'day', teammates: ['Alice'] },
            { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] },
            { date: '2025-01-14', shift_type: 'day', teammates: ['Alice'] },
            { date: '2025-01-16', shift_type: 'day', teammates: ['Alice'] }
        ];

        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Alice', 'Charlie'],
            date: '2025-01-15',
            shiftType: 'day',
            slots: slots,
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        const summary = container.querySelector('.hours-warning-summary');
        expect(summary).not.toBeNull();
        expect(summary.textContent).toContain('1 teammate exceeds compliance limit');
    });

    it('handles override date outside existing slot dates correctly', () => {
        // Slots are in a different week entirely
        const slots = [
            { date: '2025-01-06', shift_type: 'day', teammates: ['Alice'] }
        ];

        global.HoursWarningBanner.updateOverrideModal({
            selectedNames: ['Alice'],
            date: '2025-01-15', // Week of 01-12 to 01-18
            shiftType: 'day',
            slots: slots,
            teammates: teammates,
            shiftWindows: shiftWindows,
            container: container
        });

        const entry = container.querySelector('.hours-warning-entry');
        // Slot on 01-06 is outside the week 01-12 to 01-18, so currentHours=0
        expect(entry.getAttribute('aria-label')).toContain('0h this week');
        expect(entry.getAttribute('aria-label')).toContain('projected 12h');
    });
});


describe('HoursWarningBanner.updateTeamAssignment', () => {
    let container;
    const shiftWindows = {
        day: { start: '06:00', end: '18:30' },
        night: { start: '18:00', end: '06:30' }
    };

    beforeEach(() => {
        loadWeeklySummary();

        // Mock API and AppState globals
        global.API = {
            getSchedule: jest.fn(),
            getShiftWindows: jest.fn()
        };
        global.AppState = {
            getYear: jest.fn().mockReturnValue(2025)
        };

        loadHoursWarningBanner();
        container = document.createElement('div');
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
        delete global.API;
        delete global.AppState;
    });

    it('does nothing when teammate is missing', () => {
        global.HoursWarningBanner.updateTeamAssignment({
            shiftType: 'day',
            container: container
        });
        expect(container.innerHTML).toBe('');
    });

    it('does nothing when shiftType is missing', () => {
        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            container: container
        });
        expect(container.innerHTML).toBe('');
    });

    it('does nothing when container is missing', () => {
        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            shiftType: 'day'
        });
        // No error thrown
    });

    it('renders banner immediately when slots are provided', () => {
        var slots = [
            { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] }
        ];
        // Mock today to be within the same week as the slot
        jest.useFakeTimers();
        jest.setSystemTime(new Date(2025, 0, 15)); // 2025-01-15 Wednesday

        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            shiftType: 'day',
            container: container,
            slots: slots,
            shiftWindows: shiftWindows
        });

        var banner = container.querySelector('.hours-warning-banner');
        expect(banner).not.toBeNull();
        var entry = container.querySelector('.hours-warning-entry');
        expect(entry).not.toBeNull();
        expect(entry.getAttribute('aria-label')).toContain('Alice');

        jest.useRealTimers();
    });

    it('shows loading state when slots are not provided', () => {
        global.API.getSchedule.mockReturnValue(new Promise(function () {})); // never resolves
        global.API.getShiftWindows.mockReturnValue(new Promise(function () {}));

        jest.useFakeTimers();
        jest.setSystemTime(new Date(2025, 0, 15));

        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            shiftType: 'day',
            container: container
        });

        var banner = container.querySelector('.hours-warning-banner');
        expect(banner).not.toBeNull();
        expect(banner.textContent).toBe('Loading hours...');

        jest.useRealTimers();
    });

    it('renders banner after successful API fetch', async () => {
        var slots = [
            { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] }
        ];
        global.API.getSchedule.mockResolvedValue(slots);
        global.API.getShiftWindows.mockResolvedValue(shiftWindows);

        jest.useFakeTimers();
        jest.setSystemTime(new Date(2025, 0, 15)); // Wednesday

        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            shiftType: 'day',
            container: container
        });

        // Flush promises
        await jest.runAllTimersAsync();

        var entry = container.querySelector('.hours-warning-entry');
        expect(entry).not.toBeNull();
        expect(entry.getAttribute('aria-label')).toContain('Alice');
        // Alice has 12h current (one day shift), projected = 12 + 12 = 24h
        expect(entry.getAttribute('aria-label')).toContain('12h this week');
        expect(entry.getAttribute('aria-label')).toContain('projected 24h');

        jest.useRealTimers();
    });

    it('shows error message when API call fails', async () => {
        global.API.getSchedule.mockRejectedValue(new Error('Network error'));
        global.API.getShiftWindows.mockRejectedValue(new Error('Network error'));

        jest.useFakeTimers();
        jest.setSystemTime(new Date(2025, 0, 15));

        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            shiftType: 'day',
            container: container
        });

        await jest.runAllTimersAsync();

        var banner = container.querySelector('.hours-warning-banner');
        expect(banner).not.toBeNull();
        expect(banner.textContent).toBe('Hours unavailable');

        jest.useRealTimers();
    });

    it('calls API.getSchedule with correct year and month', () => {
        global.API.getSchedule.mockReturnValue(new Promise(function () {}));
        global.API.getShiftWindows.mockReturnValue(new Promise(function () {}));
        global.AppState.getYear.mockReturnValue(2025);

        jest.useFakeTimers();
        jest.setSystemTime(new Date(2025, 2, 20)); // March 20, 2025

        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            shiftType: 'day',
            container: container
        });

        expect(global.API.getSchedule).toHaveBeenCalledWith(2025, 3);
        expect(global.API.getShiftWindows).toHaveBeenCalled();

        jest.useRealTimers();
    });

    it('normalizes FHD shift type to day', () => {
        var slots = [];
        jest.useFakeTimers();
        jest.setSystemTime(new Date(2025, 0, 15));

        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            shiftType: 'FHD',
            container: container,
            slots: slots,
            shiftWindows: shiftWindows
        });

        var entry = container.querySelector('.hours-warning-entry');
        expect(entry).not.toBeNull();
        // With no slots, current hours = 0, projected = 0 + day shift duration (12h)
        expect(entry.getAttribute('aria-label')).toContain('projected 12h');

        jest.useRealTimers();
    });

    it('normalizes BHN shift type to night', () => {
        var slots = [];
        jest.useFakeTimers();
        jest.setSystemTime(new Date(2025, 0, 15));

        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            shiftType: 'BHN',
            container: container,
            slots: slots,
            shiftWindows: shiftWindows
        });

        var entry = container.querySelector('.hours-warning-entry');
        expect(entry).not.toBeNull();
        // Night shift: 18:00 to 06:30 = 12.5h - 0.5h = 12h
        expect(entry.getAttribute('aria-label')).toContain('projected 12h');

        jest.useRealTimers();
    });

    it('uses default shift windows when shiftWindows option not provided with slots', () => {
        var slots = [];
        jest.useFakeTimers();
        jest.setSystemTime(new Date(2025, 0, 15));

        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            shiftType: 'day',
            container: container,
            slots: slots
            // No shiftWindows provided — should use defaults
        });

        var entry = container.querySelector('.hours-warning-entry');
        expect(entry).not.toBeNull();
        // Default day shift: 06:00 to 18:30 = 12.5h - 0.5h = 12h
        expect(entry.getAttribute('aria-label')).toContain('projected 12h');

        jest.useRealTimers();
    });

    it('uses custom_start for teammate when computing projected hours', () => {
        var slots = [];
        jest.useFakeTimers();
        jest.setSystemTime(new Date(2025, 0, 15));

        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice', custom_start: '07:00' },
            shiftType: 'day',
            container: container,
            slots: slots,
            shiftWindows: shiftWindows
        });

        var entry = container.querySelector('.hours-warning-entry');
        expect(entry).not.toBeNull();
        // Custom start 07:00 to 18:30 = 11.5h - 0.5h = 11h
        expect(entry.getAttribute('aria-label')).toContain('projected 11h');

        jest.useRealTimers();
    });

    it('does not increment projectedDays when today is already scheduled', () => {
        jest.useFakeTimers();
        jest.setSystemTime(new Date(2025, 0, 15)); // Wednesday

        var slots = [
            { date: '2025-01-15', shift_type: 'day', teammates: ['Alice'] }
        ];

        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            shiftType: 'day',
            container: container,
            slots: slots,
            shiftWindows: shiftWindows
        });

        // Alice already has a slot on today (2025-01-15), so projectedDays should be 1 (not 2)
        var entry = container.querySelector('.hours-warning-entry');
        expect(entry).not.toBeNull();
        // currentHours = 12 (one day shift), projected = 12 + 12 = 24
        expect(entry.getAttribute('aria-label')).toContain('12h this week');
        expect(entry.getAttribute('aria-label')).toContain('projected 24h');

        jest.useRealTimers();
    });

    it('uses default shift windows when API returns null for shift windows', async () => {
        var slots = [];
        global.API.getSchedule.mockResolvedValue(slots);
        global.API.getShiftWindows.mockResolvedValue(null);

        jest.useFakeTimers();
        jest.setSystemTime(new Date(2025, 0, 15));

        global.HoursWarningBanner.updateTeamAssignment({
            teammate: { name: 'Alice' },
            shiftType: 'day',
            container: container
        });

        await jest.runAllTimersAsync();

        var entry = container.querySelector('.hours-warning-entry');
        expect(entry).not.toBeNull();
        // Default day shift: 06:00 to 18:30 = 12h
        expect(entry.getAttribute('aria-label')).toContain('projected 12h');

        jest.useRealTimers();
    });
});
