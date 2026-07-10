/* DC-ShiftMaster Pro — Weekly Compliance Summary */
var WeeklySummary = (function () {
    /**
     * Compute shift duration in hours from start and end time strings.
     * Handles overnight shifts by adding 24h when end <= start.
     * Subtracts 30 minutes for the FHD/BHD handoff period (not counted as worked hours).
     * @param {string} startTime - HH:MM format
     * @param {string} endTime - HH:MM format
     * @returns {number} Duration in hours (actual worked time)
     */
    function computeDuration(startTime, endTime) {
        var startParts = startTime.split(':');
        var endParts = endTime.split(':');
        var startMinutes = parseInt(startParts[0], 10) * 60 + parseInt(startParts[1], 10);
        var endMinutes = parseInt(endParts[0], 10) * 60 + parseInt(endParts[1], 10);
        var duration = endMinutes - startMinutes;
        if (duration <= 0) {
            duration += 24 * 60;
        }
        // Subtract 30 min handoff (FHD/BHD) — not counted as worked hours
        duration -= 30;
        if (duration < 0) duration = 0;
        return duration / 60;
    }

    /**
     * Determine the effective start time for a teammate on a given shift type.
     * Uses custom_start if available, otherwise the shift window default.
     * @param {Object} teammate - Teammate object with optional custom_start
     * @param {string} shiftType - 'day' or 'night'
     * @param {Object} shiftWindows - Shift window config {day: {start, end}, night: {start, end}}
     * @returns {string} Effective start time in HH:MM format
     */
    function getEffectiveStart(teammate, shiftType, shiftWindows) {
        if (teammate.custom_start) {
            return teammate.custom_start;
        }
        return shiftWindows[shiftType].start;
    }

    /**
     * Determine the color class for a given hours value based on compliance thresholds.
     * @param {number} hours - Total weekly hours
     * @returns {string} CSS class name: 'compliance-green', 'compliance-yellow', or 'compliance-red'
     */
    function hoursColorClass(hours) {
        if (hours < 50) {
            return 'compliance-green';
        }
        if (hours >= 60) {
            return 'compliance-red';
        }
        return 'compliance-yellow';
    }

    /**
     * Determine the color class for a given days count.
     * @param {number} days - Total weekly days worked
     * @returns {string} CSS class name: 'compliance-green' or 'compliance-red'
     */
    function daysColorClass(days) {
        if (days >= 6) {
            return 'compliance-red';
        }
        return 'compliance-green';
    }

    /**
     * Compute weekly summaries for all teammates from schedule slot data.
     * @param {Array} slots - Schedule slot array from API
     * @param {Array} teammates - Teammate array from API
     * @param {Object} shiftWindows - Shift window configuration
     * @param {number} year - Current year
     * @param {number} month - Current month (1-12)
     * @returns {Array} Array of week summary objects
     */
    function computeWeeklySummaries(slots, teammates, shiftWindows, year, month) {
        // Helper: format a Date as YYYY-MM-DD
        function formatDate(d) {
            var yyyy = d.getFullYear();
            var mm = ('0' + (d.getMonth() + 1)).slice(-2);
            var dd = ('0' + d.getDate()).slice(-2);
            return yyyy + '-' + mm + '-' + dd;
        }

        // Step 1: Determine all Sunday–Saturday week spans overlapping the month
        // First day of the month
        var firstOfMonth = new Date(year, month - 1, 1);
        // Last day of the month
        var lastOfMonth = new Date(year, month, 0);

        // Find Sunday on or before the first day of the month
        var firstSunday = new Date(firstOfMonth);
        var dayOfWeek = firstSunday.getDay(); // 0=Sunday
        firstSunday.setDate(firstSunday.getDate() - dayOfWeek);

        // Find Saturday on or after the last day of the month
        var lastSaturday = new Date(lastOfMonth);
        var lastDayOfWeek = lastSaturday.getDay();
        if (lastDayOfWeek !== 6) {
            lastSaturday.setDate(lastSaturday.getDate() + (6 - lastDayOfWeek));
        }

        // Generate week spans
        var weeks = [];
        var current = new Date(firstSunday);
        while (current <= lastSaturday) {
            var weekStart = new Date(current);
            var weekEnd = new Date(current);
            weekEnd.setDate(weekEnd.getDate() + 6);
            weeks.push({
                start: formatDate(weekStart),
                end: formatDate(weekEnd)
            });
            current.setDate(current.getDate() + 7);
        }

        // Build a lookup map for teammates by name
        var teammateMap = {};
        for (var t = 0; t < teammates.length; t++) {
            teammateMap[teammates[t].name] = teammates[t];
        }

        // Step 2: For each week, compute per-teammate totals
        var summaries = [];
        for (var w = 0; w < weeks.length; w++) {
            var week = weeks[w];
            var weekStartStr = week.start;
            var weekEndStr = week.end;

            // Filter slots within this week
            var weekSlots = [];
            for (var s = 0; s < slots.length; s++) {
                var slotDate = slots[s].date;
                if (slotDate >= weekStartStr && slotDate <= weekEndStr) {
                    weekSlots.push(slots[s]);
                }
            }

            // Group by teammate name (use Object.create(null) to avoid prototype collisions)
            // Slots have a `teammates` array (not a single `name`), so expand each slot
            var grouped = Object.create(null);
            for (var i = 0; i < weekSlots.length; i++) {
                var slot = weekSlots[i];
                var slotTeammates = slot.teammates || (slot.name ? [slot.name] : []);
                for (var ti = 0; ti < slotTeammates.length; ti++) {
                    var tmn = slotTeammates[ti];
                    if (!tmn || tmn.toLowerCase() === 'nobody') continue;
                    if (!grouped[tmn]) {
                        grouped[tmn] = [];
                    }
                    grouped[tmn].push(slot);
                }
            }

            // Compute totals for each teammate
            var teammateResults = [];
            var names = Object.keys(grouped);
            for (var n = 0; n < names.length; n++) {
                var tmName = names[n];
                var tmSlots = grouped[tmName];
                var teammate = teammateMap[tmName];

                // Compute total hours
                var totalHours = 0;
                var distinctDates = {};
                for (var j = 0; j < tmSlots.length; j++) {
                    var sl = tmSlots[j];
                    // Determine effective start: check slot's teammate_starts first,
                    // then teammate's custom_start, then shift window default
                    var customStart = (sl.teammate_starts && sl.teammate_starts[tmName])
                        || (teammate && teammate.custom_start)
                        || null;
                    var effectiveStart = customStart || (shiftWindows[sl.shift_type] && shiftWindows[sl.shift_type].start) || sl.start_time || '06:00';
                    var endTime = (shiftWindows[sl.shift_type] && shiftWindows[sl.shift_type].end) || sl.end_time || '18:00';
                    totalHours += computeDuration(effectiveStart, endTime);
                    distinctDates[sl.date] = true;
                }

                var totalDays = Object.keys(distinctDates).length;

                teammateResults.push({
                    name: tmName,
                    totalHours: totalHours,
                    totalDays: totalDays,
                    hoursColor: hoursColorClass(totalHours),
                    daysColor: daysColorClass(totalDays)
                });
            }

            summaries.push({
                weekStart: weekStartStr,
                weekEnd: weekEndStr,
                teammates: teammateResults
            });
        }

        return summaries;
    }

    /**
     * Render weekly summary rows into the calendar grid.
     * Each row spans the full 7-column grid width and appears after each week's Saturday.
     * @param {Array} summaries - Output from computeWeeklySummaries
     * @param {HTMLElement} grid - The calendar grid container
     */
    function render(summaries, grid) {
        // Remove any existing summary rows
        var existing = grid.querySelectorAll('.weekly-summary-row');
        for (var i = existing.length - 1; i >= 0; i--) {
            existing[i].parentNode.removeChild(existing[i]);
        }

        if (!summaries || summaries.length === 0) {
            return;
        }

        // The grid is a 7-column CSS grid with day-card elements (including hidden
        // leading blanks). Each set of 7 items forms one visual week row (Sun–Sat).
        // We insert a full-width summary row after each group of 7.
        // Collect all current children (excluding any leftover summary rows)
        var children = [];
        for (var c = 0; c < grid.children.length; c++) {
            children.push(grid.children[c]);
        }
        var totalItems = children.length;
        var weekRows = Math.ceil(totalItems / 7);

        // Build summary rows and insert after each week's last day-card.
        // Insert from last to first so indices don't shift.
        for (var w = weekRows - 1; w >= 0; w--) {
            if (w >= summaries.length) continue;
            var summary = summaries[w];
            if (!summary.teammates || summary.teammates.length === 0) continue;

            var row = document.createElement('div');
            row.className = 'weekly-summary-row';

            for (var t = 0; t < summary.teammates.length; t++) {
                var tm = summary.teammates[t];

                var teammateSpan = document.createElement('span');
                teammateSpan.className = 'summary-teammate';

                var nameSpan = document.createElement('span');
                nameSpan.className = 'summary-name';
                nameSpan.textContent = tm.name;

                var hoursSpan = document.createElement('span');
                hoursSpan.className = tm.hoursColor;
                hoursSpan.textContent = tm.totalHours.toFixed(1) + 'h';

                var daysSpan = document.createElement('span');
                daysSpan.className = tm.daysColor;
                daysSpan.textContent = tm.totalDays + 'd';

                teammateSpan.appendChild(nameSpan);
                teammateSpan.appendChild(hoursSpan);
                teammateSpan.appendChild(daysSpan);

                row.appendChild(teammateSpan);
            }

            // Insert after the last item of this week row
            var insertAfterIndex = Math.min((w + 1) * 7 - 1, totalItems - 1);
            var refNode = children[insertAfterIndex];
            if (refNode && refNode.nextSibling) {
                grid.insertBefore(row, refNode.nextSibling);
            } else {
                grid.appendChild(row);
            }
        }
    }

    return {
        computeDuration: computeDuration,
        getEffectiveStart: getEffectiveStart,
        hoursColorClass: hoursColorClass,
        daysColorClass: daysColorClass,
        computeWeeklySummaries: computeWeeklySummaries,
        render: render
    };
})();
