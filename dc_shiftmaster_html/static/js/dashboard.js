/* DC-ShiftMaster Pro — Dashboard / Calendar view */
var Dashboard = (function () {
    var currentMonth = new Date().getMonth() + 1; // 1-12
    var allTeammates = [];
    var _shiftWindows = { day: { start: '06:00', end: '18:30' }, night: { start: '18:00', end: '06:30' } };
    var _lastMap = {};  // cached slot map for banner refresh
    var _cachedSlots = []; // cached raw slots array for hours warning banner

    var MONTH_NAMES = [
        '', 'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    var DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

    /* Curated palette of 20 vibrant, easily distinguishable colors
       on the dark #1E293B surface. Each is a full 32-bit hex RGB. */
    var COLOR_PALETTE = [
        '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7',
        '#DDA0DD', '#FF8C42', '#98D8C8', '#F7DC6F', '#BB8FCE',
        '#85C1E9', '#F1948A', '#82E0AA', '#F8C471', '#AED6F1',
        '#D7BDE2', '#A3E4D7', '#FAD7A0', '#A9CCE3', '#D5F5E3',
    ];

    /* Map teammate name → stable palette index */
    var _colorCache = {};
    var _nextColorIdx = 0;
    function nameToColor(name) {
        if (_colorCache[name]) return _colorCache[name];
        var color = COLOR_PALETTE[_nextColorIdx % COLOR_PALETTE.length];
        _nextColorIdx++;
        _colorCache[name] = color;
        return color;
    }
    /* Reset color assignments when teammates change */
    function resetColors() { _colorCache = {}; _nextColorIdx = 0; }

    /* Weekday-based ownership:
       Sun(0), Mon(1), Tue(2) = Front Half always
       Thu(4), Fri(5), Sat(6) = Back Half always
       Wed(3) = alternates every week (Front in week 1, Back in week 2)
       Uses a 14-day cycle anchored to the Sunday on or before Jan 1. */
    function halfLabel(dateStr) {
        var d = new Date(dateStr + 'T00:00:00');
        var dow = d.getDay(); // Sun=0..Sat=6
        if (dow === 0 || dow === 1 || dow === 2) return 'Front'; // Sun, Mon, Tue
        if (dow === 4 || dow === 5 || dow === 6) return 'Back'; // Thu, Fri, Sat
        // Wednesday — check which week of the 2-week cycle
        var jan1 = new Date(d.getFullYear(), 0, 1);
        var jan1Dow = jan1.getDay(); // Sun=0..Sat=6
        var cycleStart = new Date(jan1.getTime() - jan1Dow * 86400000);
        var offset = Math.floor((d - cycleStart) / 86400000);
        var cycleDay = ((offset % 14) + 14) % 14;
        return cycleDay < 7 ? 'Front' : 'Back';
    }

    function daysInMonth(year, month) {
        return new Date(year, month, 0).getDate();
    }

    /* Calculate end time for a custom start, preserving the shift duration.
       E.g. default day is 06:00–18:30 = 12.5h. If custom start is 12:00,
       end = 12:00 + 12.5h = 00:30 (next day). */
    function calcEndTime(customStart, defaultStart, defaultEnd) {
        function toMins(hhmm) {
            var p = hhmm.split(':');
            return parseInt(p[0], 10) * 60 + parseInt(p[1], 10);
        }
        function fromMins(m) {
            m = ((m % 1440) + 1440) % 1440;
            var h = Math.floor(m / 60);
            var mm = m % 60;
            return (h < 10 ? '0' : '') + h + ':' + (mm < 10 ? '0' : '') + mm;
        }
        var duration;
        if (defaultEnd && defaultStart) {
            var defStart = toMins(defaultStart);
            var defEnd = toMins(defaultEnd);
            duration = defEnd - defStart;
            if (duration <= 0) duration += 1440;
        } else {
            duration = 750; // 12h 30m default
        }
        var custStart = toMins(customStart);
        return fromMins(custStart + duration);
    }

    function render(slots) {
        var year = AppState.getYear();
        var grid = document.getElementById('calendar-grid');
        grid.innerHTML = '';
        resetColors();

        // Today's date string for highlighting
        var now = new Date();
        var todayStr = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');

        // Monthly shift count tracker
        var shiftCounts = {};

        // Update month label
        document.getElementById('month-label').textContent =
            MONTH_NAMES[currentMonth] + ' ' + year;

        // Build a map: date -> { day: [...], night: [...] }
        var map = {};
        slots.forEach(function (s) {
            if (!map[s.date]) map[s.date] = { day: [], night: [] };
            map[s.date][s.shift_type].push(s);
        });

        var total = daysInMonth(year, currentMonth);
        // Leading blanks for day-of-week alignment
        var firstDow = new Date(year, currentMonth - 1, 1).getDay();
        for (var b = 0; b < firstDow; b++) {
            var blank = document.createElement('div');
            blank.className = 'day-card';
            blank.style.visibility = 'hidden';
            grid.appendChild(blank);
        }

        var overrideCount = 0;

        for (var d = 1; d <= total; d++) {
            var dateStr = year + '-' + String(currentMonth).padStart(2, '0') + '-' + String(d).padStart(2, '0');
            var dow = new Date(year, currentMonth - 1, d).getDay();
            var card = document.createElement('div');
            card.className = 'day-card';
            if (dow === 0 || dow === 6) card.classList.add('weekend');
            if (dateStr === todayStr) card.classList.add('today');
            card.setAttribute('data-date', dateStr);

            var hdr = document.createElement('div');
            hdr.className = 'day-card-header';
            hdr.innerHTML = '<span class="day-number">' + d + '</span>' +
                '<span>' + DOW[dow] + '</span>' +
                '<span class="half-label">' + halfLabel(dateStr) + '</span>';
            card.appendChild(hdr);

            var info = map[dateStr] || { day: [], night: [] };

            // Day shift section — show full time range
            var dayStart = (info.day[0] && info.day[0].start_time) || '06:00';
            var dayEnd = (info.day[0] && info.day[0].end_time) || '18:30';
            var dayLabel = document.createElement('div');
            dayLabel.className = 'shift-section-label day-label';
            dayLabel.textContent = '☀️ Day  ' + dayStart + ' – ' + dayEnd;
            card.appendChild(dayLabel);
            appendPills(card, info.day, 'day');

            // Divider
            var divider = document.createElement('div');
            divider.className = 'shift-divider';
            card.appendChild(divider);

            // Night shift section — show full time range
            var nightStart = (info.night[0] && info.night[0].start_time) || '18:00';
            var nightEnd = (info.night[0] && info.night[0].end_time) || '06:30';
            var nightLabel = document.createElement('div');
            nightLabel.className = 'shift-section-label night-label';
            nightLabel.textContent = '🌙 Night  ' + nightStart + ' – ' + nightEnd;
            card.appendChild(nightLabel);
            appendPills(card, info.night, 'night');

            // Feature 2: Headcount badge
            var uniqueNames = {};
            [].concat(info.day, info.night).forEach(function (s) {
                (s.teammates || []).forEach(function (n) {
                    if (n && n.toLowerCase() !== 'nobody') uniqueNames[n] = true;
                });
            });
            var headcount = Object.keys(uniqueNames).length;
            if (headcount > 0) {
                var badge = document.createElement('span');
                badge.className = 'headcount-badge';
                badge.textContent = '👥 ' + headcount;
                hdr.appendChild(badge);
            }

            // Track shift counts for monthly stats
            [].concat(info.day, info.night).forEach(function (s) {
                if (s.is_override) overrideCount++;
                (s.teammates || []).forEach(function (n) {
                    if (n && n.toLowerCase() !== 'nobody') {
                        shiftCounts[n] = (shiftCounts[n] || 0) + 1;
                    }
                });
            });

            card.addEventListener('click', (function (ds) {
                return function () { openOverrideModal(ds); };
            })(dateStr));

            grid.appendChild(card);
        }

        // Render color legend
        renderLegend();

        // Render monthly stats
        renderStats(shiftCounts);

        // Cache map for banner timer refresh
        _lastMap = map;

        // Update override count badge
        var overrideBadge = document.getElementById('override-count');
        if (overrideCount > 0) {
            overrideBadge.textContent = overrideCount + ' override' + (overrideCount > 1 ? 's' : '');
            overrideBadge.hidden = false;
        } else {
            overrideBadge.hidden = true;
        }

        // Update current-shift banner
        updateShiftBanner(map, year);

        // Render weekly compliance summary rows
        if (typeof WeeklySummary !== 'undefined') {
            var summaries = WeeklySummary.computeWeeklySummaries(
                slots,
                allTeammates,
                _shiftWindows,
                year,
                currentMonth
            );
            WeeklySummary.render(summaries, grid);
        }
    }

    function updateShiftBanner(map, year) {
        var banner = document.getElementById('current-shift-banner');
        var now = new Date();
        if (currentMonth !== now.getMonth() + 1 || year !== now.getFullYear()) {
            banner.hidden = true;
            return;
        }
        var todayStr = year + '-' + String(currentMonth).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
        var hour = now.getHours();
        var shiftType = (hour >= 6 && hour < 18) ? 'day' : 'night';
        var info = map[todayStr];
        if (!info) { banner.hidden = true; return; }
        var slots = info[shiftType] || [];
        var names = [];
        slots.forEach(function (s) {
            (s.teammates || []).forEach(function (n) {
                if (n && n.toLowerCase() !== 'nobody' && names.indexOf(n) === -1) names.push(n);
            });
        });
        if (!names.length) { banner.hidden = true; return; }
        var minsNow = now.getHours() * 60 + now.getMinutes();
        var shiftEndMins = shiftType === 'day' ? 18 * 60 : 6 * 60;
        var minsLeft;
        if (shiftType === 'day') {
            minsLeft = shiftEndMins - minsNow;
        } else {
            minsLeft = minsNow >= 18 * 60 ? (24 * 60 - minsNow + 6 * 60) : (6 * 60 - minsNow);
        }
        var hLeft = Math.floor(minsLeft / 60);
        var mLeft = minsLeft % 60;
        var timeStr = hLeft + 'h ' + (mLeft < 10 ? '0' : '') + mLeft + 'm';
        banner.textContent = '\uD83D\uDFE2 ON SHIFT NOW: ' + names.join(', ') + ' \u2014 ' + shiftType + ' shift \u2014 ' + timeStr + ' left';
        banner.hidden = false;
    }

    function renderLegend() {
        var container = document.getElementById('color-legend');
        container.innerHTML = '';
        var names = Object.keys(_colorCache);
        if (!names.length) return;
        names.forEach(function (name) {
            var item = document.createElement('span');
            item.className = 'legend-item';
            var swatch = document.createElement('span');
            swatch.className = 'legend-swatch';
            swatch.style.backgroundColor = _colorCache[name];
            item.appendChild(swatch);
            item.appendChild(document.createTextNode(name));
            container.appendChild(item);
        });
    }

    function renderStats(shiftCounts) {
        var container = document.getElementById('monthly-stats');
        container.innerHTML = '';
        var names = Object.keys(shiftCounts).sort();
        if (!names.length) return;

        var title = document.createElement('h3');
        title.textContent = 'Monthly Shift Summary';
        container.appendChild(title);

        var statsGrid = document.createElement('div');
        statsGrid.className = 'stats-grid';
        names.forEach(function (name) {
            var row = document.createElement('div');
            row.className = 'stat-row';
            var swatch = document.createElement('span');
            swatch.className = 'stat-swatch';
            swatch.style.backgroundColor = _colorCache[name] || '#666';
            row.appendChild(swatch);
            var nameEl = document.createElement('span');
            nameEl.className = 'stat-name';
            nameEl.textContent = name;
            row.appendChild(nameEl);
            var countEl = document.createElement('span');
            countEl.className = 'stat-count';
            countEl.textContent = shiftCounts[name];
            row.appendChild(countEl);
            statsGrid.appendChild(row);
        });
        container.appendChild(statsGrid);
    }

    function appendPills(card, slotArr, type) {
        if (!slotArr.length) return;
        var row = document.createElement('div');
        row.className = 'pills-row';
        slotArr.forEach(function (slot) {
            (slot.teammates || []).forEach(function (name) {
                var pill = document.createElement('span');
                pill.className = 'shift-pill';
                if (slot.is_override) pill.classList.add('override');
                // Unique color per teammate
                pill.style.backgroundColor = nameToColor(name);
                pill.style.color = '#fff';
                // Day/night distinction via left border
                pill.style.borderLeft = '3px solid ' + (type === 'day' ? '#FFD966' : '#4472C4');
                var label = name;
                var starts = slot.teammate_starts || {};
                pill.textContent = label;
                if (starts[name]) {
                    var customEnd = calcEndTime(starts[name], slot.start_time, slot.end_time || '');
                    var t = document.createElement('span');
                    t.className = 'pill-time';
                    t.textContent = ' (' + starts[name] + ' – ' + customEnd + ')';
                    pill.appendChild(t);
                    pill.title = name + ': ' + starts[name] + ' – ' + customEnd;
                }
                row.appendChild(pill);
            });
        });
        card.appendChild(row);
    }

    /* ── Override modal ── */
    function openOverrideModal(dateStr) {
        var modal = document.getElementById('override-modal');
        document.getElementById('override-date-label').textContent = 'Date: ' + dateStr;
        modal.setAttribute('data-date', dateStr);

        // Populate teammate checkbox list
        var listEl = document.getElementById('override-teammate-list');
        listEl.innerHTML = '';
        allTeammates.forEach(function (t) {
            var label = document.createElement('label');
            label.className = 'override-checkbox-label';
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.value = t.name;
            label.appendChild(cb);
            label.appendChild(document.createTextNode(' ' + t.name));
            listEl.appendChild(label);
        });
        modal.hidden = false;
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.getElementById('override-cancel').addEventListener('click', function () {
            document.getElementById('override-modal').hidden = true;
            HoursWarningBanner.clear(document.getElementById('hours-warning-container'));
        });
        document.getElementById('override-submit').addEventListener('click', function () {
            var modal = document.getElementById('override-modal');
            var dateStr = modal.getAttribute('data-date');
            var shiftType = document.getElementById('override-shift-type').value;
            var checkboxes = document.querySelectorAll('#override-teammate-list input:checked');
            var names = [];
            checkboxes.forEach(function (cb) { names.push(cb.value); });
            var name = names.join(',') || 'nobody';
            var data = { date: dateStr, shift_type: shiftType, name: name };
            API.setOverrideRaw(data).then(function (result) {
                if (result.status === 201) {
                    Toast.show('Override saved', 'success');
                    modal.hidden = true;
                    HoursWarningBanner.clear(document.getElementById('hours-warning-container'));
                    fetchAndRender();
                } else if (result.status === 422 && result.body.status === 'compliance_warning' && Array.isArray(result.body.violations) && result.body.violations.length > 0) {
                    ComplianceModal.show({
                        violations: result.body.violations,
                        overrideData: data,
                        onSuccess: fetchAndRender
                    });
                } else {
                    Toast.show(result.body.error || 'Request failed', 'error');
                }
            }).catch(function (e) { Toast.show(e.message || 'Request failed', 'error'); });
        });
        document.getElementById('override-remove').addEventListener('click', function () {
            var modal = document.getElementById('override-modal');
            var dateStr = modal.getAttribute('data-date');
            var shiftType = document.getElementById('override-shift-type').value;
            API.removeOverride({ date: dateStr, shift_type: shiftType })
                .then(function () {
                    Toast.show('Override removed', 'success');
                    modal.hidden = true;
                    HoursWarningBanner.clear(document.getElementById('hours-warning-container'));
                    fetchAndRender();
                })
                .catch(function (e) { Toast.show(e.message, 'error'); });
        });

        // Backdrop click — close override modal and clear hours warning banner
        document.getElementById('override-modal').addEventListener('click', function (e) {
            if (e.target === this) {
                this.hidden = true;
                HoursWarningBanner.clear(document.getElementById('hours-warning-container'));
            }
        });

        // Wire checkbox change events in Override Modal to update Hours Warning Banner
        // Uses event delegation on #override-teammate-list for efficiency
        document.getElementById('override-teammate-list').addEventListener('change', function (e) {
            if (e.target && e.target.type === 'checkbox') {
                triggerHoursWarningUpdate();
            }
        });

        // Also update banner when shift type changes (affects projected hours)
        document.getElementById('override-shift-type').addEventListener('change', function () {
            triggerHoursWarningUpdate();
        });

        document.getElementById('prev-month').addEventListener('click', function () {
            currentMonth--;
            if (currentMonth < 1) { currentMonth = 12; AppState.setYear(AppState.getYear() - 1); }
            fetchAndRender();
        });
        document.getElementById('next-month').addEventListener('click', function () {
            currentMonth++;
            if (currentMonth > 12) { currentMonth = 1; AppState.setYear(AppState.getYear() + 1); }
            fetchAndRender();
        });
        document.getElementById('today-btn').addEventListener('click', function () {
            var now = new Date();
            currentMonth = now.getMonth() + 1;
            AppState.setYear(now.getFullYear());
            fetchAndRender();
        });
        document.getElementById('print-btn').addEventListener('click', function () {
            window.print();
        });
    });

    /**
     * Gather current override modal state and trigger the Hours Warning Banner update.
     * Called on checkbox change and shift type change events.
     */
    function triggerHoursWarningUpdate() {
        var modal = document.getElementById('override-modal');
        var container = document.getElementById('hours-warning-container');
        if (!modal || !container) return;

        // Gather selected teammate names from checked checkboxes
        var checkboxes = document.querySelectorAll('#override-teammate-list input[type="checkbox"]:checked');
        var selectedNames = [];
        checkboxes.forEach(function (cb) { selectedNames.push(cb.value); });

        // Get the override date from the modal's data-date attribute
        var date = modal.getAttribute('data-date');

        // Get the shift type from the select element
        var shiftType = document.getElementById('override-shift-type').value;

        // Call HoursWarningBanner.updateOverrideModal with all required data
        HoursWarningBanner.updateOverrideModal({
            selectedNames: selectedNames,
            date: date,
            shiftType: shiftType,
            slots: _cachedSlots,
            teammates: allTeammates,
            shiftWindows: _shiftWindows,
            container: container
        });
    }

    function fetchAndRender() {
        var year = AppState.getYear();
        Promise.all([
            API.getSchedule(year, currentMonth),
            API.getTeammates(),
            API.getShiftWindows()
        ]).then(function (results) {
            allTeammates = results[1] || [];
            var slots = results[0];
            if (!Array.isArray(slots)) {
                Toast.show('Schedule data unavailable', 'error');
                slots = [];
            }
            // Update shift windows if available
            if (results[2]) {
                _shiftWindows = results[2];
            }
            _cachedSlots = slots;
            render(slots);
        }).catch(function (e) {
            Toast.show(e.message, 'error');
            render([]);
        });
    }

    // Auto-refresh: update banner timer every 60s (no API call)
    setInterval(function () {
        if (Object.keys(_lastMap).length) {
            updateShiftBanner(_lastMap, AppState.getYear());
        }
    }, 60000);

    // Auto-refresh: full data reload every 5 minutes
    setInterval(function () {
        fetchAndRender();
    }, 300000);

    return { load: fetchAndRender };
})();

function loadDashboard() { Dashboard.load(); }
