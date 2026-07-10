/* DC-ShiftMaster Pro — Proactive Hours Warning Banner */
// NOTE: This module is purely informational (Requirements 6.1, 6.2, 6.3).
// It NEVER disables or modifies the #override-submit button state.
// Managers can always proceed with assignments regardless of banner content.
var HoursWarningBanner = (function () {

    /**
     * Determine the work week (Sunday–Saturday) containing a given date.
     * @param {string} dateStr - YYYY-MM-DD
     * @returns {{start: string, end: string}} Week boundaries where start is Sunday and end is Saturday
     */
    function getWeekForDate(dateStr) {
        var parts = dateStr.split('-');
        var year = parseInt(parts[0], 10);
        var month = parseInt(parts[1], 10) - 1; // JS months are 0-indexed
        var day = parseInt(parts[2], 10);
        var date = new Date(year, month, day);
        var dayOfWeek = date.getDay(); // 0 = Sunday, 6 = Saturday

        // Find Sunday on or before the date
        var sunday = new Date(year, month, day - dayOfWeek);
        // Find Saturday (6 days after Sunday)
        var saturday = new Date(sunday.getFullYear(), sunday.getMonth(), sunday.getDate() + 6);

        return {
            start: formatDate(sunday),
            end: formatDate(saturday)
        };
    }

    /**
     * Format a Date object as YYYY-MM-DD.
     * @param {Date} d - Date object
     * @returns {string} Formatted date string
     */
    function formatDate(d) {
        var yyyy = d.getFullYear();
        var mm = ('0' + (d.getMonth() + 1)).slice(-2);
        var dd = ('0' + d.getDate()).slice(-2);
        return yyyy + '-' + mm + '-' + dd;
    }

    /**
     * Compute a single teammate's weekly hours and days for a given week.
     * Pure computation, no DOM interaction.
     * @param {string} teammateName - Name of the teammate
     * @param {string} weekStart - Sunday date (YYYY-MM-DD)
     * @param {string} weekEnd - Saturday date (YYYY-MM-DD)
     * @param {Array} slots - Schedule slot array
     * @param {Object} teammate - Teammate object (for custom_start)
     * @param {Object} shiftWindows - Shift window config
     * @returns {{currentHours: number, currentDays: number}}
     */
    function computeTeammateWeeklyHours(teammateName, weekStart, weekEnd, slots, teammate, shiftWindows) {
        var totalHours = 0;
        var distinctDates = {};

        for (var i = 0; i < slots.length; i++) {
            var slot = slots[i];

            // Filter by date range (inclusive)
            if (slot.date < weekStart || slot.date > weekEnd) {
                continue;
            }

            // Filter by teammate name — slots have a `teammates` array or a `name` field
            var slotTeammates = slot.teammates || (slot.name ? [slot.name] : []);
            var found = false;
            for (var j = 0; j < slotTeammates.length; j++) {
                if (slotTeammates[j] === teammateName) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                continue;
            }

            // Compute duration using WeeklySummary functions
            var effectiveStart = WeeklySummary.getEffectiveStart(teammate, slot.shift_type, shiftWindows);
            var endTime = shiftWindows[slot.shift_type].end;
            totalHours += WeeklySummary.computeDuration(effectiveStart, endTime);

            // Track distinct dates
            distinctDates[slot.date] = true;
        }

        return {
            currentHours: totalHours,
            currentDays: Object.keys(distinctDates).length
        };
    }

    /**
     * Compute projected hours by adding pending shift duration to current hours.
     * @param {number} currentHours - Current weekly hours
     * @param {string} shiftType - 'day' or 'night'
     * @param {Object} teammate - Teammate object (for custom_start)
     * @param {Object} shiftWindows - Shift window config
     * @returns {number} Projected total hours
     */
    function computeProjectedHours(currentHours, shiftType, teammate, shiftWindows) {
        var effectiveStart = WeeklySummary.getEffectiveStart(teammate, shiftType, shiftWindows);
        var endTime = shiftWindows[shiftType].end;
        var shiftDuration = WeeklySummary.computeDuration(effectiveStart, endTime);
        return currentHours + shiftDuration;
    }

    /**
     * Get the text label for a compliance color class.
     * @param {string} colorClass - 'compliance-green', 'compliance-yellow', or 'compliance-red'
     * @returns {string} 'OK', 'Caution', or 'Over Limit'
     */
    function colorToLabel(colorClass) {
        if (colorClass === 'compliance-yellow') return 'Caution';
        if (colorClass === 'compliance-red') return 'Over Limit';
        return 'OK';
    }

    /**
     * Render the hours warning banner into a container.
     * Internal function — not exposed on the public API.
     * @param {HTMLElement} container - DOM element to render into
     * @param {Array} entries - Array of TeammateHoursEntry objects
     */
    function renderBanner(container, entries) {
        // Remove any existing banner from the container
        var existing = container.querySelector('.hours-warning-banner');
        if (existing) {
            container.removeChild(existing);
        }

        // Create the banner container
        var banner = document.createElement('div');
        banner.className = 'hours-warning-banner';
        banner.setAttribute('role', 'status');
        banner.setAttribute('aria-live', 'polite');

        // Sort entries by projectedHours descending
        var sorted = entries.slice().sort(function (a, b) {
            return b.projectedHours - a.projectedHours;
        });

        // Render each entry
        for (var i = 0; i < sorted.length; i++) {
            var entry = sorted[i];
            var entryDiv = document.createElement('div');
            entryDiv.className = 'hours-warning-entry';
            entryDiv.setAttribute('aria-label',
                entry.name + ': ' + entry.currentHours + 'h this week, projected ' + entry.projectedHours + 'h, ' + entry.hoursLabel
            );

            // Name span
            var nameSpan = document.createElement('span');
            nameSpan.className = 'hours-warning-name';
            nameSpan.textContent = entry.name;
            entryDiv.appendChild(nameSpan);

            // Current hours span
            var currentSpan = document.createElement('span');
            currentSpan.className = 'hours-warning-current';
            currentSpan.textContent = entry.currentHours + 'h this week';
            entryDiv.appendChild(currentSpan);

            // Projected hours span with color class
            var projectedSpan = document.createElement('span');
            projectedSpan.className = 'hours-warning-projected ' + entry.hoursColor;
            projectedSpan.textContent = 'projected ' + entry.projectedHours + 'h';
            entryDiv.appendChild(projectedSpan);

            // Text label span
            var labelSpan = document.createElement('span');
            labelSpan.className = 'hours-warning-label';
            labelSpan.textContent = entry.hoursLabel;
            entryDiv.appendChild(labelSpan);

            banner.appendChild(entryDiv);
        }

        // If any entry has projectedHours >= 60, append a summary warning line
        var overLimitCount = 0;
        for (var j = 0; j < sorted.length; j++) {
            if (sorted[j].projectedHours >= 60) {
                overLimitCount++;
            }
        }
        if (overLimitCount > 0) {
            var summaryDiv = document.createElement('div');
            summaryDiv.className = 'hours-warning-summary';
            summaryDiv.textContent = overLimitCount + (overLimitCount === 1 ? ' teammate exceeds' : ' teammates exceed') + ' compliance limit';
            banner.appendChild(summaryDiv);
        }

        container.appendChild(banner);
    }

    /**
     * Compute and display hours warning for selected teammates in the Override Modal.
     * @param {Object} options
     * @param {Array<string>} options.selectedNames - Names of checked teammates
     * @param {string} options.date - Override date (YYYY-MM-DD)
     * @param {string} options.shiftType - 'day' or 'night'
     * @param {Array} options.slots - Schedule slot array (already loaded by dashboard)
     * @param {Array} options.teammates - Full teammate objects array
     * @param {Object} options.shiftWindows - Shift window config
     * @param {HTMLElement} options.container - DOM element to render into
     */
    function updateOverrideModal(options) {
        var selectedNames = options.selectedNames || [];
        var container = options.container;

        // If no teammates selected, clear the banner and return
        if (selectedNames.length === 0) {
            clear(container);
            return;
        }

        // Determine week boundaries for the override date
        var week = getWeekForDate(options.date);
        var weekStart = week.start;
        var weekEnd = week.end;

        var entries = [];

        for (var i = 0; i < selectedNames.length; i++) {
            var name = selectedNames[i];

            // Find the teammate object from the teammates array
            var teammate = null;
            for (var j = 0; j < options.teammates.length; j++) {
                if (options.teammates[j].name === name) {
                    teammate = options.teammates[j];
                    break;
                }
            }

            // If teammate not found, skip
            if (!teammate) {
                continue;
            }

            // Compute current weekly hours and days
            var weeklyResult = computeTeammateWeeklyHours(
                name, weekStart, weekEnd, options.slots, teammate, options.shiftWindows
            );
            var currentHours = weeklyResult.currentHours;
            var currentDays = weeklyResult.currentDays;

            // Compute projected hours
            var projectedHours = computeProjectedHours(
                currentHours, options.shiftType, teammate, options.shiftWindows
            );

            // Determine if the override date is already in the teammate's scheduled dates for that week
            // Check if any slot in the week has this date for this teammate
            var dateAlreadyScheduled = false;
            for (var k = 0; k < options.slots.length; k++) {
                var slot = options.slots[k];
                if (slot.date !== options.date) continue;
                var slotTeammates = slot.teammates || (slot.name ? [slot.name] : []);
                for (var m = 0; m < slotTeammates.length; m++) {
                    if (slotTeammates[m] === name) {
                        dateAlreadyScheduled = true;
                        break;
                    }
                }
                if (dateAlreadyScheduled) break;
            }

            var projectedDays = dateAlreadyScheduled ? currentDays : currentDays + 1;

            // Get color classes
            var hoursColor = WeeklySummary.hoursColorClass(projectedHours);
            var daysColor = WeeklySummary.daysColorClass(projectedDays);

            // Get text labels
            var hoursLabel = colorToLabel(hoursColor);
            var daysLabel = colorToLabel(daysColor);

            entries.push({
                name: name,
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

        renderBanner(container, entries);
    }

    /**
     * Default shift windows used as fallback when API data is unavailable.
     */
    var DEFAULT_SHIFT_WINDOWS = {
        day: { start: '06:00', end: '18:30' },
        night: { start: '18:00', end: '06:30' }
    };

    /**
     * Compute and display hours warning for a single teammate in Team Assignment.
     * @param {Object} options
     * @param {Object} options.teammate - Teammate object
     * @param {string} options.shiftType - Target shift type
     * @param {HTMLElement} options.container - DOM element to render into
     * @param {Array} [options.slots] - Optional pre-loaded schedule slots
     * @param {Object} [options.shiftWindows] - Optional pre-loaded shift windows
     */
    function updateTeamAssignment(options) {
        var teammate = options.teammate;
        var shiftType = options.shiftType;
        var container = options.container;

        if (!teammate || !shiftType || !container) {
            return;
        }

        // Determine today's date as YYYY-MM-DD
        var now = new Date();
        var today = formatDate(now);

        // Determine current week boundaries
        var week = getWeekForDate(today);
        var weekStart = week.start;
        var weekEnd = week.end;

        // Normalize shift type: FHD/BHD -> day, FHN/BHN -> night
        var normalizedShift = shiftType;
        if (shiftType === 'FHD' || shiftType === 'BHD') {
            normalizedShift = 'day';
        } else if (shiftType === 'FHN' || shiftType === 'BHN') {
            normalizedShift = 'night';
        }

        // If slots are provided directly, compute and render immediately
        if (options.slots) {
            var shiftWindows = options.shiftWindows || DEFAULT_SHIFT_WINDOWS;
            computeAndRender(teammate, normalizedShift, weekStart, weekEnd, today, options.slots, shiftWindows, container);
            return;
        }

        // Show loading state
        showLoading(container);

        // Fetch schedule data and shift windows from API
        var year = AppState.getYear();
        var currentMonth = now.getMonth() + 1;

        Promise.all([
            API.getSchedule(year, currentMonth),
            API.getShiftWindows()
        ]).then(function (results) {
            var slots = results[0];
            if (!Array.isArray(slots)) {
                slots = [];
            }
            var shiftWindows = results[1] || DEFAULT_SHIFT_WINDOWS;
            computeAndRender(teammate, normalizedShift, weekStart, weekEnd, today, slots, shiftWindows, container);
        }).catch(function () {
            showError(container);
        });
    }

    /**
     * Compute hours and render a single-entry banner for a teammate.
     * @param {Object} teammate - Teammate object
     * @param {string} shiftType - Normalized shift type ('day' or 'night')
     * @param {string} weekStart - Week start date (YYYY-MM-DD)
     * @param {string} weekEnd - Week end date (YYYY-MM-DD)
     * @param {string} today - Today's date (YYYY-MM-DD)
     * @param {Array} slots - Schedule slot array
     * @param {Object} shiftWindows - Shift window config
     * @param {HTMLElement} container - DOM element to render into
     */
    function computeAndRender(teammate, shiftType, weekStart, weekEnd, today, slots, shiftWindows, container) {
        try {
            var weeklyResult = computeTeammateWeeklyHours(
                teammate.name, weekStart, weekEnd, slots, teammate, shiftWindows
            );
            var currentHours = weeklyResult.currentHours;
            var currentDays = weeklyResult.currentDays;

            var projectedHours = computeProjectedHours(
                currentHours, shiftType, teammate, shiftWindows
            );

            // Check if today is already scheduled for this teammate
            var dateAlreadyScheduled = false;
            for (var i = 0; i < slots.length; i++) {
                var slot = slots[i];
                if (slot.date !== today) continue;
                var slotTeammates = slot.teammates || (slot.name ? [slot.name] : []);
                for (var j = 0; j < slotTeammates.length; j++) {
                    if (slotTeammates[j] === teammate.name) {
                        dateAlreadyScheduled = true;
                        break;
                    }
                }
                if (dateAlreadyScheduled) break;
            }

            var projectedDays = dateAlreadyScheduled ? currentDays : currentDays + 1;

            var hoursColor = WeeklySummary.hoursColorClass(projectedHours);
            var daysColor = WeeklySummary.daysColorClass(projectedDays);
            var hoursLabel = colorToLabel(hoursColor);
            var daysLabel = colorToLabel(daysColor);

            var entry = {
                name: teammate.name,
                currentHours: currentHours,
                currentDays: currentDays,
                projectedHours: projectedHours,
                projectedDays: projectedDays,
                hoursColor: hoursColor,
                daysColor: daysColor,
                hoursLabel: hoursLabel,
                daysLabel: daysLabel
            };

            renderBanner(container, [entry]);
        } catch (e) {
            // Gracefully handle errors — show error message, never break parent UI
            showError(container);
        }
    }

    /**
     * Show a loading indicator in the container.
     * @param {HTMLElement} container - DOM element to render into
     */
    function showLoading(container) {
        clear(container);
        var banner = document.createElement('div');
        banner.className = 'hours-warning-banner';
        banner.setAttribute('role', 'status');
        banner.setAttribute('aria-live', 'polite');
        banner.textContent = 'Loading hours...';
        container.appendChild(banner);
    }

    /**
     * Show an error message in the container.
     * @param {HTMLElement} container - DOM element to render into
     */
    function showError(container) {
        clear(container);
        var banner = document.createElement('div');
        banner.className = 'hours-warning-banner';
        banner.setAttribute('role', 'status');
        banner.setAttribute('aria-live', 'polite');
        banner.textContent = 'Hours unavailable';
        container.appendChild(banner);
    }

    /**
     * Hide/clear the banner from a container.
     * @param {HTMLElement} container - DOM element containing the banner
     */
    function clear(container) {
        if (!container) {
            return;
        }
        var banner = container.querySelector('.hours-warning-banner');
        if (banner) {
            banner.parentNode.removeChild(banner);
        }
    }

    return {
        updateOverrideModal: updateOverrideModal,
        updateTeamAssignment: updateTeamAssignment,
        clear: clear,
        computeTeammateWeeklyHours: computeTeammateWeeklyHours,
        computeProjectedHours: computeProjectedHours,
        getWeekForDate: getWeekForDate,
        colorToLabel: colorToLabel,
        _internal: {
            renderBanner: renderBanner
        }
    };
})();
