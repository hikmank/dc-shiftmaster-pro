/**
 * Property-based tests for HoursWarningBanner module
 * Feature: proactive-hours-warning
 *
 * Uses fast-check to verify correctness properties across many random inputs.
 */
const fc = require('fast-check');
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

// ─── Shared Arbitraries ──────────────────────────────────────────────────────

/**
 * Generate a valid HH:MM time string (00:00 to 23:59).
 */
function timeStringArbitrary() {
    return fc.integer({ min: 0, max: 23 }).chain(hour =>
        fc.integer({ min: 0, max: 59 }).map(minute => {
            const hh = String(hour).padStart(2, '0');
            const mm = String(minute).padStart(2, '0');
            return hh + ':' + mm;
        })
    );
}

/**
 * Generate a valid shiftWindows object with start/end times for day and night.
 */
function shiftWindowsArbitrary() {
    return fc.record({
        day: fc.record({
            start: timeStringArbitrary(),
            end: timeStringArbitrary()
        }),
        night: fc.record({
            start: timeStringArbitrary(),
            end: timeStringArbitrary()
        })
    });
}

/**
 * Generate a teammate object with optional custom_start.
 */
function teammateArbitrary() {
    return fc.record({
        name: fc.string({ minLength: 1, maxLength: 20 }),
        custom_start: fc.option(timeStringArbitrary(), { nil: undefined })
    }).map(obj => {
        // Remove custom_start key entirely if undefined to match real objects
        if (obj.custom_start === undefined) {
            return { name: obj.name };
        }
        return obj;
    });
}

// ─── Property 1 ──────────────────────────────────────────────────────────────

// Feature: proactive-hours-warning, Property 1: Week boundary computation is correct
describe('Feature: proactive-hours-warning, Property 1: Week boundary computation is correct', () => {
    /**
     * **Validates: Requirements 1.1, 5.2**
     *
     * Property 1: For any valid date string (YYYY-MM-DD), getWeekForDate(date)
     * returns a start that is a Sunday on or before the date and an end that is
     * the following Saturday, such that start <= date <= end and end - start == 6 days.
     */

    beforeEach(() => {
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.HoursWarningBanner;
    });

    it('returns correct Sunday-Saturday boundaries for any valid date', () => {
        // Generator: arbitrary valid dates between 2000 and 2030
        const validDateArb = fc.tuple(
            fc.integer({ min: 2000, max: 2030 }),  // year
            fc.integer({ min: 1, max: 12 })         // month
        ).chain(([year, month]) => {
            // Compute the number of days in this month
            const daysInMonth = new Date(year, month, 0).getDate();
            return fc.tuple(
                fc.constant(year),
                fc.constant(month),
                fc.integer({ min: 1, max: daysInMonth })  // valid day for month
            );
        }).map(([year, month, day]) => {
            // Format as YYYY-MM-DD
            const mm = ('0' + month).slice(-2);
            const dd = ('0' + day).slice(-2);
            return year + '-' + mm + '-' + dd;
        });

        fc.assert(
            fc.property(validDateArb, (dateStr) => {
                const result = global.HoursWarningBanner.getWeekForDate(dateStr);

                // Parse the input date and result dates using UTC to avoid DST issues
                const inputParts = dateStr.split('-').map(Number);
                const startParts = result.start.split('-').map(Number);
                const endParts = result.end.split('-').map(Number);

                const inputDate = new Date(dateStr + 'T00:00:00');
                const startDate = new Date(result.start + 'T00:00:00');
                const endDate = new Date(result.end + 'T00:00:00');

                // Assert: start is a Sunday (getDay() === 0)
                expect(startDate.getDay()).toBe(0);

                // Assert: end is a Saturday (getDay() === 6)
                expect(endDate.getDay()).toBe(6);

                // Assert: start <= date <= end (using string comparison for YYYY-MM-DD)
                expect(result.start <= dateStr).toBe(true);
                expect(dateStr <= result.end).toBe(true);

                // Assert: end - start === 6 days (using UTC to avoid DST issues)
                const startUTC = Date.UTC(startParts[0], startParts[1] - 1, startParts[2]);
                const endUTC = Date.UTC(endParts[0], endParts[1] - 1, endParts[2]);
                const diffDays = (endUTC - startUTC) / (1000 * 60 * 60 * 24);
                expect(diffDays).toBe(6);
            }),
            { numRuns: 100 }
        );
    });
});

// ─── Property 3 ──────────────────────────────────────────────────────────────

// Feature: proactive-hours-warning, Property 3: Projected hours equals current hours plus shift duration
describe('Feature: proactive-hours-warning, Property 3: Projected hours equals current hours plus shift duration', () => {
    /**
     * Validates: Requirements 2.1, 2.2, 2.3
     */

    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
    });

    it('projected hours equals currentHours + computeDuration(effectiveStart, end) for any valid inputs', () => {
        fc.assert(
            fc.property(
                fc.double({ min: 0, max: 100, noNaN: true, noDefaultInfinity: true }),
                fc.constantFrom('day', 'night'),
                teammateArbitrary(),
                shiftWindowsArbitrary(),
                (currentHours, shiftType, teammate, shiftWindows) => {
                    // Call the function under test
                    const result = global.HoursWarningBanner.computeProjectedHours(
                        currentHours, shiftType, teammate, shiftWindows
                    );

                    // Independently compute expected value
                    const effectiveStart = teammate.custom_start
                        ? teammate.custom_start
                        : shiftWindows[shiftType].start;
                    const endTime = shiftWindows[shiftType].end;
                    const shiftDuration = global.WeeklySummary.computeDuration(effectiveStart, endTime);
                    const expected = currentHours + shiftDuration;

                    // Assert equality (floating point safe comparison)
                    expect(result).toBeCloseTo(expected, 10);
                }
            ),
            { numRuns: 100 }
        );
    });
});


// ─── Property 5 ──────────────────────────────────────────────────────────────

// Feature: proactive-hours-warning, Property 5: Rendered entries match selected teammates
describe('Feature: proactive-hours-warning, Property 5: Rendered entries match selected teammates', () => {
    /**
     * **Validates: Requirements 4.2, 4.4, 7.1**
     *
     * Property 5: For any non-empty set of selected teammate names and corresponding
     * schedule data, the banner SHALL render exactly one entry per selected name,
     * and each entry SHALL contain the teammate's name, current hours value,
     * projected hours value, and a compliance color indicator.
     */

    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
    });

    it('renders exactly one entry per selected teammate with correct values', () => {
        // Generator: unique teammate names (1-5 names, alphanumeric to avoid edge cases)
        const uniqueNamesArb = fc.uniqueArray(
            fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,14}$/),
            { minLength: 1, maxLength: 5 }
        );

        // Generator: projected hours (non-negative)
        const projectedHoursArb = fc.double({ min: 0, max: 120, noNaN: true, noDefaultInfinity: true });

        // Generator: current hours (non-negative)
        const currentHoursArb = fc.double({ min: 0, max: 100, noNaN: true, noDefaultInfinity: true });

        // Generator: current days (0-7)
        const currentDaysArb = fc.integer({ min: 0, max: 7 });

        // Generator: projected days (0-7)
        const projectedDaysArb = fc.integer({ min: 0, max: 7 });

        fc.assert(
            fc.property(
                uniqueNamesArb,
                fc.array(projectedHoursArb, { minLength: 5, maxLength: 5 }),
                fc.array(currentHoursArb, { minLength: 5, maxLength: 5 }),
                fc.array(currentDaysArb, { minLength: 5, maxLength: 5 }),
                fc.array(projectedDaysArb, { minLength: 5, maxLength: 5 }),
                (names, projHoursArr, currHoursArr, currDaysArr, projDaysArr) => {
                    // Build entries array for each name
                    var entries = [];
                    for (var i = 0; i < names.length; i++) {
                        var projectedHours = projHoursArr[i % projHoursArr.length];
                        var currentHours = currHoursArr[i % currHoursArr.length];
                        var currentDays = currDaysArr[i % currDaysArr.length];
                        var projectedDays = projDaysArr[i % projDaysArr.length];
                        var hoursColor = global.WeeklySummary.hoursColorClass(projectedHours);
                        var daysColor = global.WeeklySummary.daysColorClass(projectedDays);
                        var hoursLabel = global.HoursWarningBanner.colorToLabel(hoursColor);
                        var daysLabel = global.HoursWarningBanner.colorToLabel(daysColor);

                        entries.push({
                            name: names[i],
                            currentHours: currentHours,
                            currentDays: currentDays,
                            projectedHours: projectedHours,
                            projectedDays: projectedDays,
                            hoursColor: hoursColor,
                            daysColor: daysColor,
                            hoursLabel: hoursLabel,
                            daysLabel: daysLabel
                        });
                    }

                    // Create a jsdom container
                    var container = document.createElement('div');

                    // Call renderBanner
                    global.HoursWarningBanner._internal.renderBanner(container, entries);

                    // Verify: exactly one .hours-warning-entry per name
                    var entryElements = container.querySelectorAll('.hours-warning-entry');
                    expect(entryElements.length).toBe(names.length);

                    // Verify: each entry has an aria-label containing the teammate's name
                    // Note: entries are sorted by projectedHours descending, so we check
                    // that all names appear somewhere in the rendered entries
                    var renderedLabels = [];
                    for (var j = 0; j < entryElements.length; j++) {
                        renderedLabels.push(entryElements[j].getAttribute('aria-label'));
                    }

                    for (var k = 0; k < names.length; k++) {
                        var name = names[k];
                        var found = renderedLabels.some(function (label) {
                            return label && label.indexOf(name + ':') === 0;
                        });
                        expect(found).toBe(true);
                    }

                    // Verify: each entry contains projected hours value in its aria-label
                    for (var m = 0; m < entries.length; m++) {
                        var entry = entries[m];
                        var matchingLabel = renderedLabels.find(function (label) {
                            return label && label.indexOf(entry.name + ':') === 0;
                        });
                        expect(matchingLabel).toBeDefined();
                        expect(matchingLabel).toContain('projected ' + entry.projectedHours + 'h');
                    }
                }
            ),
            { numRuns: 100 }
        );
    });
});

// ─── Property 4 ──────────────────────────────────────────────────────────────

// Feature: proactive-hours-warning, Property 4: Color classification matches compliance thresholds
describe('Feature: proactive-hours-warning, Property 4: Color classification matches compliance thresholds', () => {
    /**
     * **Validates: Requirements 3.1, 3.2, 3.3, 3.4**
     *
     * Property 4: For any non-negative hours value, the assigned color class
     * SHALL be 'compliance-green' when hours < 50, 'compliance-yellow' when
     * 50 ≤ hours < 60, and 'compliance-red' when hours ≥ 60.
     * For any non-negative days count, the assigned color class SHALL be
     * 'compliance-green' when days < 6 and 'compliance-red' when days ≥ 6.
     */

    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
    });

    it('hoursColorClass returns correct color class for any non-negative hours value', () => {
        fc.assert(
            fc.property(
                fc.double({ min: 0, max: 200, noNaN: true, noDefaultInfinity: true }),
                (hours) => {
                    const result = global.WeeklySummary.hoursColorClass(hours);

                    if (hours < 50) {
                        expect(result).toBe('compliance-green');
                    } else if (hours >= 50 && hours < 60) {
                        expect(result).toBe('compliance-yellow');
                    } else {
                        // hours >= 60
                        expect(result).toBe('compliance-red');
                    }
                }
            ),
            { numRuns: 100 }
        );
    });

    it('daysColorClass returns correct color class for any non-negative days value', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 0, max: 14 }),
                (days) => {
                    const result = global.WeeklySummary.daysColorClass(days);

                    if (days < 6) {
                        expect(result).toBe('compliance-green');
                    } else {
                        // days >= 6
                        expect(result).toBe('compliance-red');
                    }
                }
            ),
            { numRuns: 100 }
        );
    });
});


// ─── Property 6 ──────────────────────────────────────────────────────────────

// Feature: proactive-hours-warning, Property 6: Entries are sorted by projected hours descending
describe('Feature: proactive-hours-warning, Property 6: Entries are sorted by projected hours descending', () => {
    /**
     * **Validates: Requirements 7.2**
     *
     * Property 6: For any list of two or more teammate hours entries, the rendered
     * order SHALL have each entry's projected hours greater than or equal to the
     * next entry's projected hours (i.e., sorted descending).
     */

    beforeEach(() => {
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.HoursWarningBanner;
    });

    it('rendered entries are ordered by projected hours descending for any set of 2-6 entries', () => {
        // Generator: array of 2-6 entry objects with random projectedHours (0-100)
        const entryArb = fc.record({
            name: fc.string({ minLength: 1, maxLength: 20 }),
            currentHours: fc.integer({ min: 0, max: 80 }),
            projectedHours: fc.integer({ min: 0, max: 100 }),
            currentDays: fc.integer({ min: 1, max: 7 }),
            projectedDays: fc.integer({ min: 1, max: 7 }),
            hoursColor: fc.constantFrom('compliance-green', 'compliance-yellow', 'compliance-red'),
            hoursLabel: fc.constantFrom('OK', 'Caution', 'Over Limit'),
            daysColor: fc.constantFrom('compliance-green', 'compliance-red'),
            daysLabel: fc.constantFrom('OK', 'Over Limit')
        });

        const entriesArb = fc.array(entryArb, { minLength: 2, maxLength: 6 });

        fc.assert(
            fc.property(entriesArb, (entries) => {
                // Create a jsdom container
                var container = document.createElement('div');

                // Call renderBanner with the generated entries
                global.HoursWarningBanner._internal.renderBanner(container, entries);

                // Query all rendered entry elements
                var entryElements = container.querySelectorAll('.hours-warning-entry');

                // Extract projected hours from each entry's aria-label
                var renderedHours = [];
                for (var i = 0; i < entryElements.length; i++) {
                    var ariaLabel = entryElements[i].getAttribute('aria-label');
                    // aria-label format: "{name}: {currentHours}h this week, projected {projectedHours}h, {label}"
                    var match = ariaLabel.match(/projected (\d+)h/);
                    expect(match).not.toBeNull();
                    renderedHours.push(parseInt(match[1], 10));
                }

                // Verify descending order: each entry's projectedHours >= next entry's projectedHours
                for (var j = 0; j < renderedHours.length - 1; j++) {
                    expect(renderedHours[j]).toBeGreaterThanOrEqual(renderedHours[j + 1]);
                }
            }),
            { numRuns: 100 }
        );
    });
});


// ─── Property 7 ──────────────────────────────────────────────────────────────

// Feature: proactive-hours-warning, Property 7: Red threshold warning count is accurate
describe('Feature: proactive-hours-warning, Property 7: Red threshold warning count is accurate', () => {
    /**
     * **Validates: Requirements 4.5, 7.3**
     *
     * Property 7: For any set of teammate hours entries, the displayed warning
     * count SHALL equal the number of entries whose projected hours are ≥ 60.
     * When the count is zero, no warning summary SHALL be displayed.
     */

    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
    });

    it('displayed warning count equals number of entries with projectedHours >= 60', () => {
        // Generator: array of 1-8 entry objects with random projectedHours (0-100)
        const entryArb = fc.record({
            name: fc.string({ minLength: 1, maxLength: 20 }),
            currentHours: fc.double({ min: 0, max: 100, noNaN: true, noDefaultInfinity: true }),
            currentDays: fc.integer({ min: 0, max: 7 }),
            projectedHours: fc.double({ min: 0, max: 100, noNaN: true, noDefaultInfinity: true }),
            projectedDays: fc.integer({ min: 0, max: 7 }),
            hoursColor: fc.constantFrom('compliance-green', 'compliance-yellow', 'compliance-red'),
            daysColor: fc.constantFrom('compliance-green', 'compliance-red'),
            hoursLabel: fc.constantFrom('OK', 'Caution', 'Over Limit'),
            daysLabel: fc.constantFrom('OK', 'Over Limit')
        });

        const entriesArb = fc.array(entryArb, { minLength: 1, maxLength: 8 });

        fc.assert(
            fc.property(entriesArb, (entries) => {
                // Create a jsdom container
                var container = document.createElement('div');

                // Call renderBanner
                global.HoursWarningBanner._internal.renderBanner(container, entries);

                // Count entries with projectedHours >= 60
                var expectedCount = 0;
                for (var i = 0; i < entries.length; i++) {
                    if (entries[i].projectedHours >= 60) {
                        expectedCount++;
                    }
                }

                // Check the summary element
                var summary = container.querySelector('.hours-warning-summary');

                if (expectedCount === 0) {
                    // No warning summary should be displayed
                    expect(summary).toBeNull();
                } else {
                    // Summary should exist and contain the correct count
                    expect(summary).not.toBeNull();
                    // Extract the number from the summary text
                    var summaryText = summary.textContent;
                    var match = summaryText.match(/^(\d+)/);
                    expect(match).not.toBeNull();
                    expect(parseInt(match[1], 10)).toBe(expectedCount);
                }
            }),
            { numRuns: 100 }
        );
    });
});


// ─── Property 2 ──────────────────────────────────────────────────────────────

// Feature: proactive-hours-warning, Property 2: Weekly hours summation matches slot durations
describe('Feature: proactive-hours-warning, Property 2: Weekly hours summation matches slot durations', () => {
    /**
     * **Validates: Requirements 1.1, 2.1**
     *
     * Property 2: For any teammate name, valid week boundaries, and set of schedule
     * slots, computeTeammateWeeklyHours SHALL return currentHours equal to the sum
     * of WeeklySummary.computeDuration(effectiveStart, endTime) for all slots within
     * the week that include that teammate, and currentDays equal to the count of
     * distinct dates among those slots.
     */

    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
    });

    it('returns sum of computeDuration for matching slots and correct distinct day count', () => {
        // Fixed shift windows as specified in the task
        const shiftWindows = {
            day: { start: '06:00', end: '18:30' },
            night: { start: '18:00', end: '06:30' }
        };

        // Helper to format date as YYYY-MM-DD
        function formatTestDate(d) {
            const yyyy = d.getFullYear();
            const mm = ('0' + (d.getMonth() + 1)).slice(-2);
            const dd = ('0' + d.getDate()).slice(-2);
            return yyyy + '-' + mm + '-' + dd;
        }

        // Generator: teammate name (non-empty alphanumeric)
        const nameArb = fc.stringMatching(/^[A-Za-z][A-Za-z0-9 ]{0,9}$/);

        // Generator: a valid Sunday date (weekStart) between 2020 and 2028
        const weekStartArb = fc.integer({ min: 2020, max: 2028 }).chain(year =>
            fc.integer({ min: 1, max: 12 }).chain(month => {
                const daysInMonth = new Date(year, month, 0).getDate();
                return fc.integer({ min: 1, max: daysInMonth }).map(day => {
                    // Find the Sunday on or before this date
                    const d = new Date(year, month - 1, day);
                    const dayOfWeek = d.getDay();
                    const sunday = new Date(year, month - 1, day - dayOfWeek);
                    return sunday;
                });
            })
        );

        fc.assert(
            fc.property(
                nameArb.chain(name =>
                    weekStartArb.chain(weekStartDate => {
                        // Generate slot definitions (0-10 slots)
                        const slotsArb = fc.array(
                            fc.record({
                                dateOffset: fc.integer({ min: -7, max: 14 }),
                                shift_type: fc.constantFrom('day', 'night'),
                                includeTeammate: fc.boolean()
                            }),
                            { minLength: 0, maxLength: 10 }
                        );

                        // Generate teammate custom_start (optional)
                        const customStartArb = fc.option(timeStringArbitrary(), { nil: undefined });

                        return fc.tuple(
                            fc.constant(name),
                            fc.constant(weekStartDate),
                            slotsArb,
                            customStartArb
                        );
                    })
                ),
                ([teammateName, weekStartDate, slotDefs, customStart]) => {
                    // Build week boundaries
                    const weekStartStr = formatTestDate(weekStartDate);
                    const weekEndDate = new Date(
                        weekStartDate.getFullYear(),
                        weekStartDate.getMonth(),
                        weekStartDate.getDate() + 6
                    );
                    const weekEndStr = formatTestDate(weekEndDate);

                    // Build teammate object
                    const teammate = customStart !== undefined
                        ? { name: teammateName, custom_start: customStart }
                        : { name: teammateName };

                    // Build slots from definitions
                    const slots = slotDefs.map(def => {
                        const slotDate = new Date(
                            weekStartDate.getFullYear(),
                            weekStartDate.getMonth(),
                            weekStartDate.getDate() + def.dateOffset
                        );
                        const dateStr = formatTestDate(slotDate);
                        const teammates = def.includeTeammate
                            ? [teammateName, 'OtherPerson']
                            : ['OtherPerson', 'AnotherOne'];
                        return {
                            date: dateStr,
                            shift_type: def.shift_type,
                            teammates: teammates
                        };
                    });

                    // Call the function under test
                    const result = global.HoursWarningBanner.computeTeammateWeeklyHours(
                        teammateName, weekStartStr, weekEndStr, slots, teammate, shiftWindows
                    );

                    // Independently compute expected values
                    let expectedHours = 0;
                    const distinctDates = {};

                    for (let i = 0; i < slots.length; i++) {
                        const slot = slots[i];

                        // Filter: date within week range (inclusive)
                        if (slot.date < weekStartStr || slot.date > weekEndStr) {
                            continue;
                        }

                        // Filter: teammates includes the name
                        if (slot.teammates.indexOf(teammateName) === -1) {
                            continue;
                        }

                        // Compute duration using WeeklySummary functions
                        const effectiveStart = global.WeeklySummary.getEffectiveStart(
                            teammate, slot.shift_type, shiftWindows
                        );
                        const endTime = shiftWindows[slot.shift_type].end;
                        expectedHours += global.WeeklySummary.computeDuration(effectiveStart, endTime);

                        // Track distinct dates
                        distinctDates[slot.date] = true;
                    }

                    const expectedDays = Object.keys(distinctDates).length;

                    // Assert currentHours matches expected sum
                    expect(result.currentHours).toBeCloseTo(expectedHours, 10);

                    // Assert currentDays matches expected distinct day count
                    expect(result.currentDays).toBe(expectedDays);
                }
            ),
            { numRuns: 100 }
        );
    });
});

// ─── Property 8 ──────────────────────────────────────────────────────────────

// Feature: proactive-hours-warning, Property 8: Accessibility labels contain name and compliance status
describe('Feature: proactive-hours-warning, Property 8: Accessibility labels contain name and compliance status', () => {
    /**
     * **Validates: Requirements 8.2, 8.3, 8.4**
     *
     * Property 8: For any teammate hours entry, the rendered element SHALL include
     * an aria-label attribute containing the teammate's name, the projected hours
     * value, and a text status label ('OK', 'Caution', or 'Over Limit') that
     * corresponds to the compliance color classification. The text label SHALL not
     * rely solely on color.
     */

    beforeEach(() => {
        loadWeeklySummary();
        loadHoursWarningBanner();
    });

    afterEach(() => {
        delete global.WeeklySummary;
        delete global.HoursWarningBanner;
    });

    /**
     * Generate a teammate entry object with random name, hours, and correct hoursLabel.
     */
    function teammateEntryArbitrary() {
        return fc.record({
            name: fc.stringMatching(/^[a-zA-Z0-9]{1,10}$/),
            currentHours: fc.integer({ min: 0, max: 100 }),
            projectedHours: fc.integer({ min: 0, max: 100 })
        }).map(({ name, currentHours, projectedHours }) => {
            // Determine the correct hoursLabel based on projectedHours thresholds
            let hoursColor;
            let hoursLabel;
            if (projectedHours < 50) {
                hoursColor = 'compliance-green';
                hoursLabel = 'OK';
            } else if (projectedHours >= 50 && projectedHours < 60) {
                hoursColor = 'compliance-yellow';
                hoursLabel = 'Caution';
            } else {
                hoursColor = 'compliance-red';
                hoursLabel = 'Over Limit';
            }

            return {
                name: name,
                currentHours: currentHours,
                currentDays: 3,
                projectedHours: projectedHours,
                projectedDays: 4,
                hoursColor: hoursColor,
                daysColor: 'compliance-green',
                hoursLabel: hoursLabel,
                daysLabel: 'OK'
            };
        });
    }

    it('each rendered entry has aria-label containing name, projected hours, and correct text label', () => {
        fc.assert(
            fc.property(
                fc.array(teammateEntryArbitrary(), { minLength: 1, maxLength: 5 }),
                (entries) => {
                    // Create a jsdom container
                    const container = document.createElement('div');

                    // Render the banner
                    global.HoursWarningBanner._internal.renderBanner(container, entries);

                    // Get all rendered entry elements
                    const entryElements = container.querySelectorAll('.hours-warning-entry');

                    // Should have exactly one entry per input entry
                    expect(entryElements.length).toBe(entries.length);

                    // Entries are sorted by projectedHours descending in the render
                    const sorted = entries.slice().sort((a, b) => b.projectedHours - a.projectedHours);

                    for (let i = 0; i < entryElements.length; i++) {
                        const el = entryElements[i];
                        const expectedEntry = sorted[i];

                        // Verify aria-label attribute exists
                        const ariaLabel = el.getAttribute('aria-label');
                        expect(ariaLabel).not.toBeNull();

                        // Verify aria-label contains the teammate's name
                        expect(ariaLabel).toContain(expectedEntry.name);

                        // Verify aria-label contains the projected hours value
                        expect(ariaLabel).toContain(String(expectedEntry.projectedHours));

                        // Verify aria-label contains the correct text label
                        expect(ariaLabel).toContain(expectedEntry.hoursLabel);

                        // Verify a .hours-warning-label span exists with the text label
                        // (not relying solely on color)
                        const labelSpan = el.querySelector('.hours-warning-label');
                        expect(labelSpan).not.toBeNull();
                        expect(labelSpan.textContent).toBe(expectedEntry.hoursLabel);
                    }
                }
            ),
            { numRuns: 100 }
        );
    });
});
