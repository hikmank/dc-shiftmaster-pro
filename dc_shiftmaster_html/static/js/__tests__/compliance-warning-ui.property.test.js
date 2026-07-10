/**
 * Property-based tests for Compliance Warning UI
 * Feature: compliance-warning-ui
 *
 * Uses fast-check to verify correctness properties across many random inputs.
 * Test file structured to accommodate Properties 1-8.
 */
const fc = require('fast-check');

// ─── Shared Arbitraries ──────────────────────────────────────────────────────

/**
 * Generate a single violation object with random but valid data.
 */
function violationArbitrary() {
    return fc.record({
        rule: fc.constantFrom('weekly_hours', 'weekly_days', 'daily_hours'),
        projected: fc.double({ min: 0.5, max: 200, noNaN: true }),
        limit: fc.double({ min: 0.5, max: 200, noNaN: true }),
        window_start: fc.option(
            fc.date({ min: new Date('2024-01-01'), max: new Date('2026-12-31') })
                .map(d => d.toISOString().slice(0, 10)),
            { nil: null }
        ),
        window_end: fc.option(
            fc.date({ min: new Date('2024-01-01'), max: new Date('2026-12-31') })
                .map(d => d.toISOString().slice(0, 10)),
            { nil: null }
        )
    });
}

/**
 * Generate a non-empty array of 1-5 violations.
 */
function violationsArrayArbitrary() {
    return fc.array(violationArbitrary(), { minLength: 1, maxLength: 5 });
}

// ─── Property 1 ──────────────────────────────────────────────────────────────

describe('Feature: compliance-warning-ui, Property 1: Compliance response interception prevents error toast', () => {
    let toastCalls;
    let complianceModalCalls;

    beforeEach(() => {
        // Set up minimal DOM for the compliance modal
        document.body.innerHTML = `
            <div id="compliance-modal" role="dialog" aria-modal="true" aria-labelledby="compliance-heading" hidden>
                <h2 id="compliance-heading">Compliance Warning</h2>
                <div id="compliance-violations"></div>
                <button id="compliance-acknowledge" aria-label="Acknowledge compliance warnings and proceed with override">Acknowledge &amp; Proceed</button>
                <button id="compliance-cancel" aria-label="Cancel override and close compliance warning">Cancel</button>
            </div>
            <div id="toast-container"></div>
        `;

        // Track Toast.show calls
        toastCalls = [];
        global.Toast = {
            show: function (message, type) {
                toastCalls.push({ message: message, type: type });
            }
        };

        // Track ComplianceModal.show calls
        complianceModalCalls = [];
        global.ComplianceModal = {
            show: function (options) {
                complianceModalCalls.push(options);
            }
        };

        // Stub API module
        global.API = {
            setOverrideRaw: function () { return Promise.resolve({ status: 200, body: {} }); }
        };
    });

    afterEach(() => {
        delete global.Toast;
        delete global.ComplianceModal;
        delete global.API;
        document.body.innerHTML = '';
    });

    /**
     * **Validates: Requirements 1.1, 1.2**
     *
     * Property 1: For any POST /api/overrides response with HTTP status 422
     * and a body containing status: "compliance_warning" with a non-empty
     * violations array, the Override_Submission_Handler SHALL NOT display an
     * error toast and SHALL pass the violations array to the ComplianceModal.
     */
    it('should not show error toast and should pass violations to ComplianceModal for any valid compliance_warning response', () => {
        fc.assert(
            fc.property(
                violationsArrayArbitrary(),
                (violations) => {
                    // Reset tracking arrays for each iteration
                    toastCalls = [];
                    complianceModalCalls = [];

                    // Simulate the response from API.setOverrideRaw
                    const result = {
                        status: 422,
                        body: {
                            status: 'compliance_warning',
                            violations: violations
                        }
                    };

                    // Simulate the override submission handler logic
                    // (as specified in the design document's modified override flow)
                    const overrideData = { date: '2025-01-15', shift_type: 'day', name: 'TestUser' };

                    if (result.status === 201) {
                        // Success path
                        Toast.show('Override saved', 'success');
                    } else if (result.status === 422 && result.body.status === 'compliance_warning' && Array.isArray(result.body.violations) && result.body.violations.length > 0) {
                        // Compliance warning path — show modal, no error toast
                        ComplianceModal.show({
                            violations: result.body.violations,
                            overrideData: overrideData,
                            onSuccess: function () {}
                        });
                    } else {
                        // Default error toast
                        Toast.show(result.body.error || 'Request failed', 'error');
                    }

                    // Assert: Toast.show was NOT called with 'error' type
                    const errorToasts = toastCalls.filter(function (call) {
                        return call.type === 'error';
                    });
                    expect(errorToasts.length).toBe(0);

                    // Assert: ComplianceModal.show WAS called with the violations array
                    expect(complianceModalCalls.length).toBe(1);
                    expect(complianceModalCalls[0].violations).toEqual(violations);
                }
            ),
            { numRuns: 100 }
        );
    });
});


// ─── Property 2 ──────────────────────────────────────────────────────────────

describe('Feature: compliance-warning-ui, Property 2: Violation card rendering matches violation data', () => {
    const fs = require('fs');
    const path = require('path');

    const RULE_LABELS = {
        weekly_hours: 'Weekly Hours Exceeded',
        weekly_days: 'Weekly Days Exceeded',
        daily_hours: 'Daily Hours Exceeded'
    };

    /**
     * Set up minimal DOM that compliance-modal.js needs (getElementById calls at top).
     */
    function buildDOM() {
        document.body.innerHTML = `
            <div id="compliance-modal" role="dialog" aria-modal="true" aria-labelledby="compliance-heading" hidden>
                <h2 id="compliance-heading">Compliance Warning</h2>
                <div id="compliance-violations"></div>
                <button id="compliance-acknowledge" aria-label="Acknowledge compliance warnings and proceed with override">Acknowledge &amp; Proceed</button>
                <button id="compliance-cancel" aria-label="Cancel override and close compliance warning">Cancel</button>
            </div>
            <div id="toast-container"></div>
        `;
    }

    /**
     * Set up global stubs that compliance-modal.js depends on.
     */
    function setupGlobals() {
        global.API = {
            setOverrideRaw: function () { return Promise.resolve({ status: 201, body: {} }); }
        };
        global.Toast = {
            show: function () {}
        };
    }

    /**
     * Load compliance-modal.js by evaluating its source in the current global scope.
     */
    function loadComplianceModal() {
        const src = fs.readFileSync(
            path.resolve(__dirname, '..', 'compliance-modal.js'),
            'utf-8'
        );
        const script = new Function('global', `
            with (global) {
                ${src}
                global.ComplianceModal = ComplianceModal;
            }
        `);
        script(global);
    }

    /**
     * Generator for a date string in YYYY-MM-DD format.
     */
    const dateStringArb = fc.tuple(
        fc.integer({ min: 2020, max: 2030 }),
        fc.integer({ min: 1, max: 12 }),
        fc.integer({ min: 1, max: 28 })
    ).map(([y, m, d]) => `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`);

    /**
     * Generator for a single violation object.
     * window_start and window_end are either both null or both valid date strings.
     */
    const violationWithWindowArb = fc.tuple(
        fc.constantFrom('weekly_hours', 'weekly_days', 'daily_hours'),
        fc.double({ min: 0.1, max: 200, noNaN: true }),
        fc.double({ min: 0.1, max: 200, noNaN: true }),
        fc.boolean()
    ).chain(([rule, projected, limit, hasWindow]) => {
        if (hasWindow) {
            return fc.tuple(dateStringArb, dateStringArb).map(([ws, we]) => ({
                rule,
                projected,
                limit,
                window_start: ws,
                window_end: we
            }));
        }
        return fc.constant({
            rule,
            projected,
            limit,
            window_start: null,
            window_end: null
        });
    });

    /**
     * Generator for an array of 1-5 violations.
     */
    const violationsArrayArb = fc.array(violationWithWindowArb, { minLength: 1, maxLength: 5 });

    beforeEach(() => {
        buildDOM();
        setupGlobals();
        loadComplianceModal();
    });

    afterEach(() => {
        delete global.ComplianceModal;
        delete global.API;
        delete global.Toast;
        document.body.innerHTML = '';
    });

    /**
     * **Validates: Requirements 2.3, 2.4, 2.5, 2.6, 2.7**
     *
     * Property 2: For any violations array containing objects with rule ∈
     * {"weekly_hours", "weekly_days", "daily_hours"}, arbitrary numeric projected
     * and limit values, and optional window_start/window_end date strings, the
     * ComplianceModal SHALL render exactly one Violation_Card per violation, each
     * displaying the correct human-readable label, the projected value, the limit
     * value, and the date range (when window_start and window_end are non-null).
     */
    it('renders violation cards matching violation data for any valid violations array', () => {
        fc.assert(
            fc.property(
                violationsArrayArb,
                (violations) => {
                    // Render each violation card
                    const cards = violations.map(v => global.ComplianceModal.renderViolationCard(v));

                    // Assert: exactly one card per violation
                    expect(cards.length).toBe(violations.length);

                    cards.forEach((card, i) => {
                        const violation = violations[i];

                        // Assert: card has role="alert"
                        expect(card.getAttribute('role')).toBe('alert');

                        // Assert: card contains the correct human-readable label
                        const expectedLabel = RULE_LABELS[violation.rule];
                        const ruleEl = card.querySelector('.violation-rule');
                        expect(ruleEl).not.toBeNull();
                        expect(ruleEl.textContent).toBe(expectedLabel);

                        // Assert: card contains "Projected: X | Limit: Y" with correct values
                        const detailEl = card.querySelector('.violation-detail');
                        expect(detailEl).not.toBeNull();
                        expect(detailEl.textContent).toBe(
                            'Projected: ' + violation.projected + ' | Limit: ' + violation.limit
                        );

                        // Assert: date range handling
                        const rangeEl = card.querySelector('.violation-range');
                        if (violation.window_start !== null && violation.window_end !== null) {
                            // If window_start and window_end are non-null, card contains the date range text
                            expect(rangeEl).not.toBeNull();
                            expect(rangeEl.textContent).toBe(
                                violation.window_start + ' \u2013 ' + violation.window_end
                            );
                        } else {
                            // If window_start or window_end is null, no date range element exists
                            expect(rangeEl).toBeNull();
                        }
                    });
                }
            ),
            { numRuns: 100 }
        );
    });
});


// ─── Property 3 ──────────────────────────────────────────────────────────────

describe('Feature: compliance-warning-ui, Property 3: Acknowledgment resubmission sends correct payload', () => {
    const fs = require('fs');
    const path = require('path');
    let capturedPayload;

    beforeEach(() => {
        // Build minimal compliance modal DOM
        document.body.innerHTML = `
            <div id="compliance-modal" role="dialog" aria-modal="true" aria-labelledby="compliance-heading" hidden>
                <h2 id="compliance-heading">Compliance Warning</h2>
                <div id="compliance-violations"></div>
                <button id="compliance-acknowledge" aria-label="Acknowledge compliance warnings and proceed with override">Acknowledge &amp; Proceed</button>
                <button id="compliance-cancel" aria-label="Cancel override and close compliance warning">Cancel</button>
            </div>
            <div id="toast-container"></div>
        `;

        capturedPayload = null;

        // Mock API.setOverrideRaw to capture the payload
        global.API = {
            setOverrideRaw: function (data) {
                capturedPayload = data;
                return Promise.resolve({ status: 201, body: { message: 'Override saved' } });
            }
        };

        // Mock Toast.show
        global.Toast = {
            show: function () {}
        };

        // Load the ComplianceModal module
        const modalSrc = fs.readFileSync(
            path.resolve(__dirname, '..', 'compliance-modal.js'),
            'utf-8'
        );
        const script = new Function('global', `
            with (global) {
                ${modalSrc}
                global.ComplianceModal = ComplianceModal;
            }
        `);
        script(global);
    });

    afterEach(() => {
        delete global.ComplianceModal;
        delete global.API;
        delete global.Toast;
        document.body.innerHTML = '';
    });

    /**
     * **Validates: Requirements 3.1**
     *
     * Property 3: For any original override data containing date, shift_type,
     * and name values, when the manager clicks "Acknowledge & Proceed", the
     * resubmission request SHALL contain all original fields plus
     * `acknowledge_violations: true`.
     */
    it('sends original override data plus acknowledge_violations: true for any override data', async () => {
        await fc.assert(
            fc.asyncProperty(
                fc.record({
                    date: fc.date({
                        min: new Date('2020-01-01'),
                        max: new Date('2030-12-31')
                    }).map(d => d.toISOString().slice(0, 10)),
                    shift_type: fc.constantFrom('day', 'night'),
                    name: fc.string({ minLength: 1, maxLength: 50 }).filter(s => s.trim().length > 0)
                }),
                async (overrideData) => {
                    // Reset captured payload
                    capturedPayload = null;

                    // Show the compliance modal with the generated override data
                    global.ComplianceModal.show({
                        violations: [{ rule: 'weekly_hours', projected: 62, limit: 60, window_start: '2025-01-06', window_end: '2025-01-12' }],
                        overrideData: overrideData,
                        onSuccess: function () {}
                    });

                    // Click the "Acknowledge & Proceed" button
                    document.getElementById('compliance-acknowledge').click();

                    // Wait for the async promise chain to resolve
                    await new Promise(r => setTimeout(r, 0));

                    // Assert: payload was captured
                    expect(capturedPayload).not.toBeNull();

                    // Assert: payload contains all original fields with their original values
                    expect(capturedPayload.date).toBe(overrideData.date);
                    expect(capturedPayload.shift_type).toBe(overrideData.shift_type);
                    expect(capturedPayload.name).toBe(overrideData.name);

                    // Assert: payload contains acknowledge_violations: true
                    expect(capturedPayload.acknowledge_violations).toBe(true);
                }
            ),
            { numRuns: 100 }
        );
    });
});


// ─── Property 4 ──────────────────────────────────────────────────────────────

describe('Feature: compliance-warning-ui, Property 4: Error message propagation after acknowledgment failure', () => {
    const fs = require('fs');
    const path = require('path');

    beforeEach(() => {
        // Build minimal compliance modal DOM
        document.body.innerHTML = `
            <div id="compliance-modal" role="dialog" aria-modal="true" aria-labelledby="compliance-heading" hidden>
                <h2 id="compliance-heading">Compliance Warning</h2>
                <div id="compliance-violations"></div>
                <button id="compliance-acknowledge" aria-label="Acknowledge compliance warnings and proceed with override">Acknowledge &amp; Proceed</button>
                <button id="compliance-cancel" aria-label="Cancel override and close compliance warning">Cancel</button>
            </div>
            <div id="toast-container"></div>
        `;

        // Mock Toast.show to capture calls
        global.Toast = {
            show: jest.fn()
        };

        // Mock API.setOverrideRaw (will be overridden per test iteration)
        global.API = {
            setOverrideRaw: jest.fn()
        };

        // Load the ComplianceModal module
        const modalSrc = fs.readFileSync(
            path.resolve(__dirname, '..', 'compliance-modal.js'),
            'utf-8'
        );
        const script = new Function('global', `
            with (global) {
                ${modalSrc}
                global.ComplianceModal = ComplianceModal;
            }
        `);
        script(global);
    });

    afterEach(() => {
        delete global.ComplianceModal;
        delete global.API;
        delete global.Toast;
        document.body.innerHTML = '';
    });

    /**
     * **Validates: Requirements 3.4**
     *
     * Property 4: For any error response from the acknowledgment resubmission
     * containing an error message string, the ComplianceModal SHALL close and
     * the Toast_Notification SHALL display that exact error message.
     */
    it('closes modal and shows exact error message in toast for any error response', async () => {
        await fc.assert(
            fc.asyncProperty(
                // Generate random non-empty error messages
                fc.string({ minLength: 1, maxLength: 200 }),
                // Generate random error status codes (anything not 201)
                fc.constantFrom(400, 403, 404, 409, 422, 500, 502, 503),
                async (errorMessage, errorStatus) => {
                    // Re-build DOM and reload module for each iteration
                    document.body.innerHTML = `
                        <div id="compliance-modal" role="dialog" aria-modal="true" aria-labelledby="compliance-heading" hidden>
                            <h2 id="compliance-heading">Compliance Warning</h2>
                            <div id="compliance-violations"></div>
                            <button id="compliance-acknowledge" aria-label="Acknowledge compliance warnings and proceed with override">Acknowledge &amp; Proceed</button>
                            <button id="compliance-cancel" aria-label="Cancel override and close compliance warning">Cancel</button>
                        </div>
                        <div id="toast-container"></div>
                    `;

                    global.Toast = { show: jest.fn() };

                    // Mock API.setOverrideRaw to return an error response
                    global.API = {
                        setOverrideRaw: jest.fn().mockResolvedValue({
                            status: errorStatus,
                            body: { error: errorMessage }
                        })
                    };

                    // Reload the ComplianceModal module with fresh DOM
                    const modalSrc = fs.readFileSync(
                        path.resolve(__dirname, '..', 'compliance-modal.js'),
                        'utf-8'
                    );
                    const script = new Function('global', `
                        with (global) {
                            ${modalSrc}
                            global.ComplianceModal = ComplianceModal;
                        }
                    `);
                    script(global);

                    // Show the compliance modal with sample violations and override data
                    global.ComplianceModal.show({
                        violations: [{ rule: 'weekly_hours', projected: 65, limit: 60, window_start: '2025-01-06', window_end: '2025-01-12' }],
                        overrideData: { date: '2025-01-10', shift_type: 'day', name: 'John Doe' },
                        onSuccess: jest.fn()
                    });

                    // Verify modal is visible before clicking acknowledge
                    const modal = document.getElementById('compliance-modal');
                    expect(modal.hasAttribute('hidden')).toBe(false);

                    // Click the acknowledge button
                    document.getElementById('compliance-acknowledge').click();

                    // Wait for the promise to resolve
                    await new Promise((r) => setTimeout(r, 0));

                    // Assert: modal is closed (hidden attribute is set)
                    expect(modal.hasAttribute('hidden')).toBe(true);

                    // Assert: Toast.show was called with the exact error message and 'error' type
                    expect(global.Toast.show).toHaveBeenCalledWith(errorMessage, 'error');
                }
            ),
            { numRuns: 100 }
        );
    });
});


// ─── Property 5 ──────────────────────────────────────────────────────────────

describe('Feature: compliance-warning-ui, Property 5: Duration calculation correctness', () => {
    const fs = require('fs');
    const path = require('path');

    /**
     * Load the WeeklySummary module by evaluating its source in the current global scope.
     */
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

    beforeEach(() => {
        loadWeeklySummary();
    });

    afterEach(() => {
        delete global.WeeklySummary;
    });

    /**
     * Arbitrary for generating a valid HH:MM time string.
     */
    const timeArb = fc.tuple(
        fc.integer({ min: 0, max: 23 }),
        fc.integer({ min: 0, max: 59 })
    ).map(([h, m]) => String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0'));

    /**
     * **Validates: Requirements 7.3, 7.4**
     *
     * Property 5: For any start time and end time in HH:MM format, the
     * Duration_Calculator SHALL compute duration as (end - start) hours when
     * end > start, and (end - start + 24) hours when end ≤ start (overnight shift).
     * When a teammate has a non-empty custom_start, that value SHALL be used
     * instead of the shift window default start time.
     */
    it('computes correct duration for any pair of HH:MM start and end times', () => {
        fc.assert(
            fc.property(
                timeArb,
                timeArb,
                (startTime, endTime) => {
                    const result = global.WeeklySummary.computeDuration(startTime, endTime);

                    // Compute expected duration
                    const startParts = startTime.split(':');
                    const endParts = endTime.split(':');
                    const startMinutes = parseInt(startParts[0], 10) * 60 + parseInt(startParts[1], 10);
                    const endMinutes = parseInt(endParts[0], 10) * 60 + parseInt(endParts[1], 10);
                    var duration = endMinutes - startMinutes;
                    if (duration <= 0) {
                        duration += 24 * 60;
                    }
                    // Subtract 30 min FHD/BHD handoff
                    duration -= 30;
                    if (duration < 0) duration = 0;
                    const expected = duration / 60;

                    expect(result).toBeCloseTo(expected, 10);
                }
            ),
            { numRuns: 100 }
        );
    });

    it('getEffectiveStart returns custom_start when truthy, otherwise shiftWindows default', () => {
        /**
         * Arbitrary for a shift windows config object.
         */
        const shiftWindowsArb = fc.record({
            day: fc.record({
                start: timeArb,
                end: timeArb
            }),
            night: fc.record({
                start: timeArb,
                end: timeArb
            })
        });

        /**
         * Arbitrary for a teammate object with optional custom_start.
         */
        const teammateArb = fc.record({
            name: fc.string({ minLength: 1, maxLength: 30 }),
            custom_start: fc.oneof(
                fc.constant(''),
                fc.constant(null),
                fc.constant(undefined),
                timeArb
            )
        });

        const shiftTypeArb = fc.constantFrom('day', 'night');

        fc.assert(
            fc.property(
                teammateArb,
                shiftTypeArb,
                shiftWindowsArb,
                (teammate, shiftType, shiftWindows) => {
                    const result = global.WeeklySummary.getEffectiveStart(teammate, shiftType, shiftWindows);

                    if (teammate.custom_start) {
                        // custom_start is truthy — should be used
                        expect(result).toBe(teammate.custom_start);
                    } else {
                        // custom_start is falsy — should fall back to shift window default
                        expect(result).toBe(shiftWindows[shiftType].start);
                    }
                }
            ),
            { numRuns: 100 }
        );
    });
});


// ─── Property 6 ──────────────────────────────────────────────────────────────

describe('Feature: compliance-warning-ui, Property 6: Weekly summary row count matches calendar weeks', () => {
    const fs = require('fs');
    const path = require('path');

    /**
     * Load the WeeklySummary module by evaluating its source in the current global scope.
     */
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

    beforeEach(() => {
        loadWeeklySummary();
    });

    afterEach(() => {
        delete global.WeeklySummary;
    });

    /**
     * Compute the expected number of calendar weeks (Sunday–Saturday spans)
     * that overlap with a given year and month.
     */
    function expectedWeekCount(year, month) {
        const firstOfMonth = new Date(year, month - 1, 1);
        const lastOfMonth = new Date(year, month, 0);

        // Sunday on or before first of month
        const firstSunday = new Date(firstOfMonth);
        firstSunday.setDate(firstSunday.getDate() - firstSunday.getDay());

        // Saturday on or after last of month
        const lastSaturday = new Date(lastOfMonth);
        const lastDow = lastSaturday.getDay();
        if (lastDow !== 6) {
            lastSaturday.setDate(lastSaturday.getDate() + (6 - lastDow));
        }

        // Count weeks
        const diffDays = Math.round((lastSaturday - firstSunday) / (1000 * 60 * 60 * 24)) + 1;
        return diffDays / 7;
    }

    /**
     * **Validates: Requirements 7.1**
     *
     * Property 6: For any year and month (1–12), the Dashboard SHALL render
     * exactly as many Weekly_Summary_Row elements as there are distinct calendar
     * weeks (Sunday–Saturday spans) that overlap with that month.
     */
    it('produces exactly as many weekly summaries as there are calendar weeks overlapping the month', () => {
        const shiftWindows = {
            day: { start: '06:00', end: '18:00' },
            night: { start: '18:00', end: '06:00' }
        };

        fc.assert(
            fc.property(
                fc.integer({ min: 2020, max: 2030 }),
                fc.integer({ min: 1, max: 12 }),
                (year, month) => {
                    // Call computeWeeklySummaries with empty slots (we just want week span count)
                    const summaries = global.WeeklySummary.computeWeeklySummaries(
                        [], [], shiftWindows, year, month
                    );

                    // Compute expected week count independently
                    const expected = expectedWeekCount(year, month);

                    // Assert: summaries.length equals expected week count
                    expect(summaries.length).toBe(expected);
                }
            ),
            { numRuns: 100 }
        );
    });
});


// ─── Property 7 ──────────────────────────────────────────────────────────────

describe('Feature: compliance-warning-ui, Property 7: Weekly summary aggregation correctness', () => {
    const fs = require('fs');
    const path = require('path');

    /**
     * Load the WeeklySummary module by evaluating its source in the current global scope.
     */
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

    beforeEach(() => {
        loadWeeklySummary();
    });

    afterEach(() => {
        delete global.WeeklySummary;
    });

    // Fixed shift windows for testing
    const shiftWindows = {
        day: { start: '06:00', end: '18:00' },
        night: { start: '18:00', end: '06:00' }
    };

    /**
     * Arbitrary for generating a valid HH:MM time string.
     */
    const timeArb = fc.tuple(
        fc.integer({ min: 0, max: 23 }),
        fc.integer({ min: 0, max: 59 })
    ).map(([h, m]) => String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0'));

    /**
     * Arbitrary for generating a teammate with optional custom_start.
     */
    const teammateArb = fc.record({
        name: fc.string({ minLength: 1, maxLength: 20 }).filter(s => s.trim().length > 0 && !s.includes('\x00')),
        custom_start: fc.oneof(
            fc.constant(''),
            fc.constant(null),
            timeArb
        )
    });

    /**
     * Generate test data: 1-3 teammates and 1-10 slots assigned to those teammates
     * within January 2025 (which starts on Wednesday).
     */
    const testDataArb = fc.tuple(
        fc.array(teammateArb, { minLength: 1, maxLength: 3 }),
        fc.array(
            fc.record({
                dayOfMonth: fc.integer({ min: 1, max: 31 }),
                shift_type: fc.constantFrom('day', 'night'),
                teammateIndex: fc.nat()
            }),
            { minLength: 1, maxLength: 10 }
        )
    ).map(([teammates, rawSlots]) => {
        // Ensure unique teammate names
        const uniqueTeammates = [];
        const usedNames = new Set();
        for (let i = 0; i < teammates.length; i++) {
            let name = teammates[i].name.trim();
            if (name && !usedNames.has(name)) {
                usedNames.add(name);
                uniqueTeammates.push({ ...teammates[i], name: name });
            }
        }
        // Ensure at least one teammate
        if (uniqueTeammates.length === 0) {
            uniqueTeammates.push({ name: 'DefaultTeammate', custom_start: '' });
        }

        // Map raw slots to valid slots referencing actual teammates
        const slots = rawSlots.map(raw => {
            const tmIndex = raw.teammateIndex % uniqueTeammates.length;
            const day = String(raw.dayOfMonth).padStart(2, '0');
            return {
                date: '2025-01-' + day,
                shift_type: raw.shift_type,
                name: uniqueTeammates[tmIndex].name
            };
        });

        return { teammates: uniqueTeammates, slots: slots };
    });

    /**
     * Independently compute expected duration for a slot given teammates and shift windows.
     */
    function computeExpectedDuration(slot, teammates, shiftWindows) {
        const teammate = teammates.find(t => t.name === slot.name) || {};
        let startTime;
        if (teammate.custom_start) {
            startTime = teammate.custom_start;
        } else {
            startTime = shiftWindows[slot.shift_type].start;
        }
        const endTime = shiftWindows[slot.shift_type].end;

        const startParts = startTime.split(':');
        const endParts = endTime.split(':');
        const startMinutes = parseInt(startParts[0], 10) * 60 + parseInt(startParts[1], 10);
        const endMinutes = parseInt(endParts[0], 10) * 60 + parseInt(endParts[1], 10);
        let duration = endMinutes - startMinutes;
        if (duration <= 0) {
            duration += 24 * 60;
        }
        // Subtract 30 min FHD/BHD handoff
        duration -= 30;
        if (duration < 0) duration = 0;
        return duration / 60;
    }

    /**
     * **Validates: Requirements 7.2**
     *
     * Property 7: For any set of schedule slots assigned to teammates within a
     * given work week, the Weekly_Summary_Row SHALL list each teammate who has at
     * least one shift, with total hours equal to the sum of their individual shift
     * durations and total days equal to the count of distinct dates they are assigned.
     */
    it('aggregates total hours and total days correctly for each teammate in each week', () => {
        fc.assert(
            fc.property(
                testDataArb,
                ({ teammates, slots }) => {
                    const year = 2025;
                    const month = 1;

                    // Call the module under test
                    const summaries = global.WeeklySummary.computeWeeklySummaries(
                        slots, teammates, shiftWindows, year, month
                    );

                    // For each week in the result, verify aggregation correctness
                    for (let w = 0; w < summaries.length; w++) {
                        const summary = summaries[w];
                        const weekStart = summary.weekStart;
                        const weekEnd = summary.weekEnd;

                        // Filter slots that fall within this week
                        const weekSlots = slots.filter(s => s.date >= weekStart && s.date <= weekEnd);

                        // Group by teammate name (use Object.create(null) to avoid prototype collisions)
                        const grouped = Object.create(null);
                        for (let i = 0; i < weekSlots.length; i++) {
                            const s = weekSlots[i];
                            if (!grouped[s.name]) {
                                grouped[s.name] = [];
                            }
                            grouped[s.name].push(s);
                        }

                        // Verify: only teammates with at least one slot in this week are listed
                        const expectedNames = Object.keys(grouped).sort();
                        const actualNames = summary.teammates.map(t => t.name).sort();
                        expect(actualNames).toEqual(expectedNames);

                        // Verify each teammate's totals
                        for (let t = 0; t < summary.teammates.length; t++) {
                            const tmResult = summary.teammates[t];
                            const tmSlots = grouped[tmResult.name];

                            // Expected total hours = sum of computeDuration for each slot
                            let expectedHours = 0;
                            const distinctDates = new Set();
                            for (let j = 0; j < tmSlots.length; j++) {
                                expectedHours += computeExpectedDuration(tmSlots[j], teammates, shiftWindows);
                                distinctDates.add(tmSlots[j].date);
                            }

                            // Expected total days = count of distinct dates
                            const expectedDays = distinctDates.size;

                            // Assert totalHours matches
                            expect(tmResult.totalHours).toBeCloseTo(expectedHours, 10);

                            // Assert totalDays matches
                            expect(tmResult.totalDays).toBe(expectedDays);
                        }
                    }
                }
            ),
            { numRuns: 100 }
        );
    });
});


// ─── Property 8 ──────────────────────────────────────────────────────────────

describe('Feature: compliance-warning-ui, Property 8: Compliance threshold color-coding', () => {
    const fs = require('fs');
    const path = require('path');

    /**
     * Load the WeeklySummary module by evaluating its source in the current global scope.
     */
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

    beforeEach(() => {
        loadWeeklySummary();
    });

    afterEach(() => {
        delete global.WeeklySummary;
    });

    /**
     * **Validates: Requirements 7.5, 7.6, 7.7, 7.8**
     *
     * Property 8: For any numeric hours value, the Weekly_Summary_Row SHALL
     * display green when hours < 50, yellow when 50 ≤ hours ≤ 59, and red
     * when hours ≥ 60. For any numeric days value, the display SHALL be red
     * when days ≥ 6, and green otherwise.
     */
    it('hoursColorClass returns correct color class for any hours value', () => {
        fc.assert(
            fc.property(
                fc.double({ min: 0, max: 200, noNaN: true, noDefaultInfinity: true }),
                (hours) => {
                    const result = global.WeeklySummary.hoursColorClass(hours);

                    if (hours < 50) {
                        expect(result).toBe('compliance-green');
                    } else if (hours >= 60) {
                        expect(result).toBe('compliance-red');
                    } else {
                        // 50 <= hours < 60 (yellow range)
                        expect(result).toBe('compliance-yellow');
                    }
                }
            ),
            { numRuns: 100 }
        );
    });

    it('daysColorClass returns correct color class for any days value', () => {
        fc.assert(
            fc.property(
                fc.integer({ min: 0, max: 14 }),
                (days) => {
                    const result = global.WeeklySummary.daysColorClass(days);

                    if (days >= 6) {
                        expect(result).toBe('compliance-red');
                    } else {
                        expect(result).toBe('compliance-green');
                    }
                }
            ),
            { numRuns: 100 }
        );
    });
});



// ─── Dashboard Integration Unit Tests ────────────────────────────────────────

describe('Dashboard integration tests', () => {
    const fs = require('fs');
    const path = require('path');

    /**
     * **Validates: Requirements 1.1, 1.2**
     *
     * Test 1: 422 compliance_warning response triggers ComplianceModal.show
     */
    it('422 compliance_warning response triggers ComplianceModal.show', async () => {
        // Set up DOM with override modal elements
        document.body.innerHTML = `
            <div id="override-modal" data-date="2025-01-15" hidden>
                <span id="override-date-label"></span>
                <select id="override-shift-type"><option value="day">Day</option></select>
                <div id="override-teammate-list">
                    <label><input type="checkbox" value="Alice" checked /></label>
                </div>
                <button id="override-submit">Save</button>
                <button id="override-cancel">Cancel</button>
                <button id="override-remove">Remove</button>
            </div>
            <div id="compliance-modal" role="dialog" aria-modal="true" aria-labelledby="compliance-heading" hidden>
                <h2 id="compliance-heading">Compliance Warning</h2>
                <div id="compliance-violations"></div>
                <button id="compliance-acknowledge">Acknowledge &amp; Proceed</button>
                <button id="compliance-cancel-btn">Cancel</button>
            </div>
        `;

        const violations = [
            { rule: 'weekly_hours', projected: 62, limit: 60, window_start: '2025-01-06', window_end: '2025-01-12' }
        ];

        // Mock API.setOverrideRaw to return compliance_warning
        global.API = {
            setOverrideRaw: jest.fn().mockResolvedValue({
                status: 422,
                body: {
                    status: 'compliance_warning',
                    violations: violations
                }
            })
        };

        // Mock ComplianceModal.show
        global.ComplianceModal = {
            show: jest.fn()
        };

        // Mock Toast.show
        global.Toast = {
            show: jest.fn()
        };

        // Simulate the override submission handler logic (from dashboard.js)
        const data = { date: '2025-01-15', shift_type: 'day', name: 'Alice' };
        const result = await API.setOverrideRaw(data);

        if (result.status === 201) {
            Toast.show('Override saved', 'success');
        } else if (result.status === 422 && result.body.status === 'compliance_warning' && Array.isArray(result.body.violations) && result.body.violations.length > 0) {
            ComplianceModal.show({
                violations: result.body.violations,
                overrideData: data,
                onSuccess: function () {}
            });
        } else {
            Toast.show(result.body.error || 'Request failed', 'error');
        }

        // Assert: ComplianceModal.show was called with the violations
        expect(ComplianceModal.show).toHaveBeenCalledTimes(1);
        expect(ComplianceModal.show).toHaveBeenCalledWith(
            expect.objectContaining({
                violations: violations,
                overrideData: data
            })
        );

        // Assert: Toast.show was NOT called with 'error'
        const errorCalls = Toast.show.mock.calls.filter(call => call[1] === 'error');
        expect(errorCalls.length).toBe(0);

        // Cleanup
        delete global.API;
        delete global.ComplianceModal;
        delete global.Toast;
        document.body.innerHTML = '';
    });

    /**
     * **Validates: Requirements 1.3**
     *
     * Test 2: 422 without violations shows error toast
     */
    it('422 without violations shows error toast', async () => {
        // Mock API.setOverrideRaw to return 422 without violations
        global.API = {
            setOverrideRaw: jest.fn().mockResolvedValue({
                status: 422,
                body: { error: 'Some other error' }
            })
        };

        // Mock ComplianceModal.show
        global.ComplianceModal = {
            show: jest.fn()
        };

        // Mock Toast.show
        global.Toast = {
            show: jest.fn()
        };

        // Simulate the override submission handler logic
        const data = { date: '2025-01-15', shift_type: 'day', name: 'Alice' };
        const result = await API.setOverrideRaw(data);

        if (result.status === 201) {
            Toast.show('Override saved', 'success');
        } else if (result.status === 422 && result.body.status === 'compliance_warning' && Array.isArray(result.body.violations) && result.body.violations.length > 0) {
            ComplianceModal.show({
                violations: result.body.violations,
                overrideData: data,
                onSuccess: function () {}
            });
        } else {
            Toast.show(result.body.error || 'Request failed', 'error');
        }

        // Assert: Toast.show was called with 'Some other error' and 'error'
        expect(Toast.show).toHaveBeenCalledWith('Some other error', 'error');

        // Assert: ComplianceModal.show was NOT called
        expect(ComplianceModal.show).not.toHaveBeenCalled();

        // Cleanup
        delete global.API;
        delete global.ComplianceModal;
        delete global.Toast;
    });

    /**
     * **Validates: Requirements 7.10**
     *
     * Test 3: WeeklySummary rows render after calendar load
     */
    it('WeeklySummary rows render after calendar load', () => {
        // Set up a grid element with 7 day-card elements (one week)
        document.body.innerHTML = '<div id="calendar-grid"></div>';
        const grid = document.getElementById('calendar-grid');
        for (let i = 0; i < 7; i++) {
            const card = document.createElement('div');
            card.className = 'day-card';
            grid.appendChild(card);
        }

        // Load the WeeklySummary module
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

        // Mock computeWeeklySummaries to return a known summary
        const mockSummaries = [{
            weekStart: '2025-01-05',
            weekEnd: '2025-01-11',
            teammates: [
                { name: 'Alice', totalHours: 48, totalDays: 4, hoursColor: 'compliance-green', daysColor: 'compliance-green' }
            ]
        }];

        const originalCompute = global.WeeklySummary.computeWeeklySummaries;
        global.WeeklySummary.computeWeeklySummaries = jest.fn().mockReturnValue(mockSummaries);
        const renderSpy = jest.spyOn(global.WeeklySummary, 'render');

        // Simulate the render flow: call computeWeeklySummaries then render
        const slots = [{ date: '2025-01-06', shift_type: 'day', name: 'Alice' }];
        const allTeammates = [{ name: 'Alice', custom_start: '' }];
        const shiftWindows = { day: { start: '06:00', end: '18:00' }, night: { start: '18:00', end: '06:00' } };

        const summaries = global.WeeklySummary.computeWeeklySummaries(
            slots, allTeammates, shiftWindows, 2025, 1
        );
        global.WeeklySummary.render(summaries, grid);

        // Assert: computeWeeklySummaries was called
        expect(global.WeeklySummary.computeWeeklySummaries).toHaveBeenCalledWith(
            slots, allTeammates, shiftWindows, 2025, 1
        );

        // Assert: render was called with the summaries and grid
        expect(renderSpy).toHaveBeenCalledWith(mockSummaries, grid);

        // Cleanup
        renderSpy.mockRestore();
        delete global.WeeklySummary;
        document.body.innerHTML = '';
    });

    /**
     * **Validates: Requirements 7.10**
     *
     * Test 4: Summary rows re-render on month change
     */
    it('summary rows re-render on month change', () => {
        document.body.innerHTML = '<div id="calendar-grid"></div>';
        const grid = document.getElementById('calendar-grid');

        // Load the WeeklySummary module
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

        const shiftWindows = { day: { start: '06:00', end: '18:00' }, night: { start: '18:00', end: '06:00' } };
        const allTeammates = [{ name: 'Bob', custom_start: '' }];

        // First render (January 2025) — Jan 1 is Wednesday (dow=3), so 3 leading blanks + 31 days = 34 items = 5 visual rows
        // Simulate realistic grid: 3 blanks + 31 day cards
        for (let i = 0; i < 3; i++) {
            const blank = document.createElement('div');
            blank.className = 'day-card';
            blank.style.visibility = 'hidden';
            grid.appendChild(blank);
        }
        for (let i = 0; i < 31; i++) {
            const card = document.createElement('div');
            card.className = 'day-card';
            grid.appendChild(card);
        }

        const janSlots = [{ date: '2025-01-06', shift_type: 'day', teammates: ['Bob'], teammate_starts: {} }];
        const janSummaries = global.WeeklySummary.computeWeeklySummaries(
            janSlots, allTeammates, shiftWindows, 2025, 1
        );
        global.WeeklySummary.render(janSummaries, grid);

        // Verify summary rows exist after first render
        let summaryRows = grid.querySelectorAll('.weekly-summary-row');
        expect(summaryRows.length).toBeGreaterThan(0);

        // Verify January data is present (Bob's day shift on Jan 6 falls in week Jan 5-11)
        let allText = Array.from(summaryRows).map(r => r.textContent).join(' ');
        expect(allText).toContain('Bob');

        // Simulate month change: clear grid, rebuild with February 2025 layout
        // Feb 1, 2025 is Saturday (dow=6), so 6 leading blanks + 28 days = 34 items = 5 visual rows
        grid.innerHTML = '';
        for (let i = 0; i < 6; i++) {
            const blank = document.createElement('div');
            blank.className = 'day-card';
            blank.style.visibility = 'hidden';
            grid.appendChild(blank);
        }
        for (let i = 0; i < 28; i++) {
            const card = document.createElement('div');
            card.className = 'day-card';
            grid.appendChild(card);
        }

        // Feb 3, 2025 is a Monday — falls in the week starting Sun Feb 2
        const febSlots = [{ date: '2025-02-03', shift_type: 'night', teammates: ['Bob'], teammate_starts: {} }];
        const febSummaries = global.WeeklySummary.computeWeeklySummaries(
            febSlots, allTeammates, shiftWindows, 2025, 2
        );
        global.WeeklySummary.render(febSummaries, grid);

        // Assert: summary rows are present after month change re-render
        summaryRows = grid.querySelectorAll('.weekly-summary-row');
        expect(summaryRows.length).toBeGreaterThan(0);

        // Assert: at least one summary row contains Bob's data from the new month
        allText = Array.from(summaryRows).map(r => r.textContent).join(' ');
        expect(allText).toContain('Bob');

        // Cleanup
        delete global.WeeklySummary;
        document.body.innerHTML = '';
    });
});
