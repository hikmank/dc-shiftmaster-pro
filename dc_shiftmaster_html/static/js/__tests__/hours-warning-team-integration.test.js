/**
 * Unit tests for HoursWarningBanner — Team Assignment integration
 * Feature: proactive-hours-warning
 * Task: 8.2
 * Requirements: 5.1, 5.3, 5.4
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

describe('HoursWarningBanner.updateTeamAssignment — Team Assignment Integration', () => {
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
        jest.useRealTimers();
    });

    // Requirement 5.1: Shift assignment action triggers banner with current week
    describe('shift assignment triggers banner with current week', () => {
        it('renders a banner entry for the teammate using the current week boundaries', () => {
            jest.useFakeTimers();
            jest.setSystemTime(new Date(2025, 0, 15)); // Wednesday 2025-01-15

            // Slot within the current week (Sun 01-12 to Sat 01-18)
            var slots = [
                { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] },
                { date: '2025-01-14', shift_type: 'day', teammates: ['Alice'] }
            ];

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
            // 2 day shifts = 24h current, projected = 24 + 12 = 36h
            expect(entry.getAttribute('aria-label')).toContain('24h this week');
            expect(entry.getAttribute('aria-label')).toContain('projected 36h');
        });

        it('excludes slots outside the current week from computation', () => {
            jest.useFakeTimers();
            jest.setSystemTime(new Date(2025, 0, 15)); // Wednesday, week is 01-12 to 01-18

            // Slot outside the current week
            var slots = [
                { date: '2025-01-06', shift_type: 'day', teammates: ['Alice'] }, // previous week
                { date: '2025-01-20', shift_type: 'day', teammates: ['Alice'] }  // next week
            ];

            global.HoursWarningBanner.updateTeamAssignment({
                teammate: { name: 'Alice' },
                shiftType: 'day',
                container: container,
                slots: slots,
                shiftWindows: shiftWindows
            });

            var entry = container.querySelector('.hours-warning-entry');
            expect(entry).not.toBeNull();
            // No slots in current week, so currentHours = 0, projected = 12h
            expect(entry.getAttribute('aria-label')).toContain('0h this week');
            expect(entry.getAttribute('aria-label')).toContain('projected 12h');
        });
    });

    // Requirement 5.3: Loading state appears when data not cached
    describe('loading state when data not cached', () => {
        it('displays "Loading hours..." when slots are not provided and API is pending', () => {
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
        });

        it('replaces loading state with banner after API resolves', async () => {
            var slots = [
                { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] }
            ];
            global.API.getSchedule.mockResolvedValue(slots);
            global.API.getShiftWindows.mockResolvedValue(shiftWindows);

            jest.useFakeTimers();
            jest.setSystemTime(new Date(2025, 0, 15));

            global.HoursWarningBanner.updateTeamAssignment({
                teammate: { name: 'Alice' },
                shiftType: 'day',
                container: container
            });

            // Initially shows loading
            expect(container.querySelector('.hours-warning-banner').textContent).toBe('Loading hours...');

            // After API resolves
            await jest.runAllTimersAsync();

            var entry = container.querySelector('.hours-warning-entry');
            expect(entry).not.toBeNull();
            expect(entry.getAttribute('aria-label')).toContain('Alice');
        });
    });

    // Requirement 5.3: Error state on API failure
    describe('error state on API failure', () => {
        it('displays "Hours unavailable" when API.getSchedule rejects', async () => {
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
        });

        it('does not block the parent UI on API failure (no exception thrown)', async () => {
            global.API.getSchedule.mockRejectedValue(new Error('Server 500'));
            global.API.getShiftWindows.mockRejectedValue(new Error('Server 500'));

            jest.useFakeTimers();
            jest.setSystemTime(new Date(2025, 0, 15));

            expect(() => {
                global.HoursWarningBanner.updateTeamAssignment({
                    teammate: { name: 'Alice' },
                    shiftType: 'day',
                    container: container
                });
            }).not.toThrow();

            await jest.runAllTimersAsync();

            // Banner shows error message gracefully
            var banner = container.querySelector('.hours-warning-banner');
            expect(banner.textContent).toBe('Hours unavailable');
        });
    });

    // Requirement 5.4: Refresh updates banner
    describe('refresh updates banner', () => {
        it('calling updateTeamAssignment again replaces the previous banner content', () => {
            jest.useFakeTimers();
            jest.setSystemTime(new Date(2025, 0, 15));

            // First call with Alice
            global.HoursWarningBanner.updateTeamAssignment({
                teammate: { name: 'Alice' },
                shiftType: 'day',
                container: container,
                slots: [],
                shiftWindows: shiftWindows
            });

            var entry1 = container.querySelector('.hours-warning-entry');
            expect(entry1.getAttribute('aria-label')).toContain('Alice');

            // Second call with Bob (different teammate)
            global.HoursWarningBanner.updateTeamAssignment({
                teammate: { name: 'Bob', custom_start: '07:00' },
                shiftType: 'day',
                container: container,
                slots: [],
                shiftWindows: shiftWindows
            });

            // Should only have one banner with Bob's data
            var banners = container.querySelectorAll('.hours-warning-banner');
            expect(banners.length).toBe(1);
            var entry2 = container.querySelector('.hours-warning-entry');
            expect(entry2.getAttribute('aria-label')).toContain('Bob');
            expect(entry2.getAttribute('aria-label')).not.toContain('Alice');
        });

        it('calling updateTeamAssignment with different shift type updates projected hours', () => {
            jest.useFakeTimers();
            jest.setSystemTime(new Date(2025, 0, 15));

            // First call with day shift
            global.HoursWarningBanner.updateTeamAssignment({
                teammate: { name: 'Alice' },
                shiftType: 'day',
                container: container,
                slots: [],
                shiftWindows: shiftWindows
            });

            var entry1 = container.querySelector('.hours-warning-entry');
            expect(entry1.getAttribute('aria-label')).toContain('projected 12h');

            // Second call with night shift
            global.HoursWarningBanner.updateTeamAssignment({
                teammate: { name: 'Alice' },
                shiftType: 'night',
                container: container,
                slots: [],
                shiftWindows: shiftWindows
            });

            var entry2 = container.querySelector('.hours-warning-entry');
            // Night shift: 18:00 to 06:30 = 12.5h - 0.5h = 12h (same duration in this config)
            expect(entry2.getAttribute('aria-label')).toContain('projected 12h');
        });

        it('calling clear() removes the banner from the team assignment container', () => {
            jest.useFakeTimers();
            jest.setSystemTime(new Date(2025, 0, 15));

            global.HoursWarningBanner.updateTeamAssignment({
                teammate: { name: 'Alice' },
                shiftType: 'day',
                container: container,
                slots: [],
                shiftWindows: shiftWindows
            });

            expect(container.querySelector('.hours-warning-banner')).not.toBeNull();

            global.HoursWarningBanner.clear(container);

            expect(container.querySelector('.hours-warning-banner')).toBeNull();
            expect(container.innerHTML).toBe('');
        });

        it('calling clear() after API-fetched banner removes it', async () => {
            var slots = [
                { date: '2025-01-13', shift_type: 'day', teammates: ['Alice'] }
            ];
            global.API.getSchedule.mockResolvedValue(slots);
            global.API.getShiftWindows.mockResolvedValue(shiftWindows);

            jest.useFakeTimers();
            jest.setSystemTime(new Date(2025, 0, 15));

            global.HoursWarningBanner.updateTeamAssignment({
                teammate: { name: 'Alice' },
                shiftType: 'day',
                container: container
            });

            await jest.runAllTimersAsync();

            expect(container.querySelector('.hours-warning-banner')).not.toBeNull();

            global.HoursWarningBanner.clear(container);

            expect(container.querySelector('.hours-warning-banner')).toBeNull();
        });
    });
});
