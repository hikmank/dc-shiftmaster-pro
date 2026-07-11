/* DC-ShiftMaster Pro — Override Panel (bulk delete management) */
var OverridesPanel = (function () {
    var MONTH_NAMES = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];

    var currentYear = null;
    var overrides = [];

    /**
     * Initialize the Override Panel.
     * Call this once the DOM is ready and the team view is active.
     */
    function init() {
        var container = document.getElementById('overrides-panel');
        if (!container) return;
        currentYear = AppState.getYear();
        renderPanel(container);
        loadOverrides();
    }

    /**
     * Render the panel skeleton (toolbar, list container, controls).
     */
    function renderPanel(container) {
        container.innerHTML =
            '<div class="overrides-panel">' +
                '<div class="overrides-toolbar">' +
                    '<h3 class="overrides-title">Schedule Overrides</h3>' +
                    '<div class="overrides-year-selector">' +
                        '<label for="overrides-year">Year:</label>' +
                        '<select id="overrides-year" class="form-control"></select>' +
                    '</div>' +
                '</div>' +
                '<div class="overrides-controls">' +
                    '<div class="overrides-range-controls">' +
                        '<div class="form-group">' +
                            '<label for="overrides-start-date">Start Date</label>' +
                            '<input type="date" id="overrides-start-date" class="form-control">' +
                        '</div>' +
                        '<div class="form-group">' +
                            '<label for="overrides-end-date">End Date</label>' +
                            '<input type="date" id="overrides-end-date" class="form-control">' +
                        '</div>' +
                        '<button id="overrides-delete-range-btn" class="btn btn-danger">Delete by Range</button>' +
                        '<span id="overrides-range-error" class="validation-error" hidden></span>' +
                    '</div>' +
                    '<div class="overrides-action-buttons">' +
                        '<label class="overrides-select-all-label">' +
                            '<input type="checkbox" id="overrides-select-all"> Select All' +
                        '</label>' +
                        '<button id="overrides-delete-selected-btn" class="btn btn-danger" disabled>Delete Selected</button>' +
                        '<button id="overrides-clear-all-btn" class="btn btn-danger">Clear All Overrides</button>' +
                    '</div>' +
                '</div>' +
                '<div id="overrides-empty-message" class="overrides-empty" hidden>' +
                    '<p>No overrides found for the selected year.</p>' +
                '</div>' +
                '<div id="overrides-list" class="overrides-list"></div>' +
            '</div>';

        populateYearSelector();
        bindEvents();
    }

    /**
     * Populate the year dropdown with a range of years around the current year.
     */
    function populateYearSelector() {
        var select = document.getElementById('overrides-year');
        if (!select) return;
        select.innerHTML = '';
        var baseYear = new Date().getFullYear();
        for (var y = baseYear - 2; y <= baseYear + 2; y++) {
            var opt = document.createElement('option');
            opt.value = y;
            opt.textContent = y;
            if (y === currentYear) opt.selected = true;
            select.appendChild(opt);
        }
    }

    /**
     * Bind event listeners for all panel interactions.
     */
    function bindEvents() {
        var yearSelect = document.getElementById('overrides-year');
        if (yearSelect) {
            yearSelect.addEventListener('change', function () {
                currentYear = parseInt(yearSelect.value, 10);
                loadOverrides();
            });
        }

        var selectAll = document.getElementById('overrides-select-all');
        if (selectAll) {
            selectAll.addEventListener('change', function () {
                toggleSelectAll(selectAll.checked);
            });
        }

        var deleteSelectedBtn = document.getElementById('overrides-delete-selected-btn');
        if (deleteSelectedBtn) {
            deleteSelectedBtn.addEventListener('click', handleDeleteSelected);
        }

        var clearAllBtn = document.getElementById('overrides-clear-all-btn');
        if (clearAllBtn) {
            clearAllBtn.addEventListener('click', handleClearAll);
        }

        var deleteRangeBtn = document.getElementById('overrides-delete-range-btn');
        if (deleteRangeBtn) {
            deleteRangeBtn.addEventListener('click', handleDeleteByRange);
        }

        // Validate date range on input change
        var startInput = document.getElementById('overrides-start-date');
        var endInput = document.getElementById('overrides-end-date');
        if (startInput) startInput.addEventListener('change', validateDateRange);
        if (endInput) endInput.addEventListener('change', validateDateRange);
    }

    /**
     * Load overrides for the current year from the API.
     */
    function loadOverrides() {
        API.getOverrides(currentYear)
            .then(function (data) {
                overrides = data || [];
                renderOverrideList();
            })
            .catch(function (err) {
                console.error('Failed to load overrides:', err);
                Toast.show('Failed to load overrides: ' + err.message, 'error');
                overrides = [];
                renderOverrideList();
            });
    }

    /**
     * Group overrides by month and render the list.
     */
    function renderOverrideList() {
        var listEl = document.getElementById('overrides-list');
        var emptyEl = document.getElementById('overrides-empty-message');
        if (!listEl || !emptyEl) return;

        // Reset select-all checkbox
        var selectAll = document.getElementById('overrides-select-all');
        if (selectAll) selectAll.checked = false;
        updateDeleteSelectedState();

        if (overrides.length === 0) {
            emptyEl.hidden = false;
            listEl.innerHTML = '';
            return;
        }

        emptyEl.hidden = true;
        var grouped = groupByMonth(overrides);
        listEl.innerHTML = '';

        // Sort months in order
        var monthKeys = Object.keys(grouped).sort();
        monthKeys.forEach(function (monthKey) {
            var section = document.createElement('div');
            section.className = 'overrides-month-group';

            var header = document.createElement('h4');
            header.className = 'overrides-month-header';
            var parts = monthKey.split('-');
            var monthIndex = parseInt(parts[1], 10) - 1;
            header.textContent = MONTH_NAMES[monthIndex] + ' ' + parts[0];
            section.appendChild(header);

            grouped[monthKey].forEach(function (override) {
                section.appendChild(createOverrideRow(override));
            });

            listEl.appendChild(section);
        });
    }

    /**
     * Group overrides into buckets by YYYY-MM key.
     */
    function groupByMonth(items) {
        var groups = {};
        items.forEach(function (item) {
            // item.date is YYYY-MM-DD
            var key = item.date.substring(0, 7); // YYYY-MM
            if (!groups[key]) groups[key] = [];
            groups[key].push(item);
        });
        return groups;
    }

    /**
     * Create a single override row with checkbox, date, shift type, name.
     */
    function createOverrideRow(override) {
        var row = document.createElement('div');
        row.className = 'override-entry';
        row.setAttribute('data-date', override.date);
        row.setAttribute('data-shift-type', override.shift_type);

        var checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'override-checkbox';
        checkbox.setAttribute('data-date', override.date);
        checkbox.setAttribute('data-shift-type', override.shift_type);
        checkbox.addEventListener('change', function () {
            updateDeleteSelectedState();
            updateSelectAllState();
        });

        var dateSpan = document.createElement('span');
        dateSpan.className = 'override-date';
        dateSpan.textContent = formatDate(override.date);

        var shiftSpan = document.createElement('span');
        shiftSpan.className = 'override-shift';
        shiftSpan.textContent = override.shift_type;

        var nameSpan = document.createElement('span');
        nameSpan.className = 'override-name';
        nameSpan.textContent = override.name || '—';

        row.appendChild(checkbox);
        row.appendChild(dateSpan);
        row.appendChild(shiftSpan);
        row.appendChild(nameSpan);
        return row;
    }

    /**
     * Format a YYYY-MM-DD date into a more readable form.
     */
    function formatDate(dateStr) {
        var parts = dateStr.split('-');
        var y = parts[0];
        var m = parseInt(parts[1], 10);
        var d = parseInt(parts[2], 10);
        return MONTH_NAMES[m - 1].substring(0, 3) + ' ' + d + ', ' + y;
    }

    /**
     * Toggle all checkboxes to match the Select All state.
     */
    function toggleSelectAll(checked) {
        var checkboxes = document.querySelectorAll('#overrides-list .override-checkbox');
        for (var i = 0; i < checkboxes.length; i++) {
            checkboxes[i].checked = checked;
        }
        updateDeleteSelectedState();
    }

    /**
     * Update the Select All checkbox to reflect individual checkbox states.
     */
    function updateSelectAllState() {
        var checkboxes = document.querySelectorAll('#overrides-list .override-checkbox');
        var selectAll = document.getElementById('overrides-select-all');
        if (!selectAll || checkboxes.length === 0) return;

        var allChecked = true;
        for (var i = 0; i < checkboxes.length; i++) {
            if (!checkboxes[i].checked) {
                allChecked = false;
                break;
            }
        }
        selectAll.checked = allChecked;
    }

    /**
     * Enable/disable the "Delete Selected" button based on checkbox state.
     */
    function updateDeleteSelectedState() {
        var btn = document.getElementById('overrides-delete-selected-btn');
        if (!btn) return;
        var selected = getSelectedKeys();
        btn.disabled = selected.length === 0;
    }

    /**
     * Get the list of selected override keys (date + shift_type pairs).
     */
    function getSelectedKeys() {
        var checkboxes = document.querySelectorAll('#overrides-list .override-checkbox:checked');
        var keys = [];
        for (var i = 0; i < checkboxes.length; i++) {
            keys.push({
                date: checkboxes[i].getAttribute('data-date'),
                shift_type: checkboxes[i].getAttribute('data-shift-type')
            });
        }
        return keys;
    }

    /**
     * Validate the date range inputs. Returns true if valid.
     */
    function validateDateRange() {
        var startInput = document.getElementById('overrides-start-date');
        var endInput = document.getElementById('overrides-end-date');
        var errorEl = document.getElementById('overrides-range-error');
        if (!startInput || !endInput || !errorEl) return false;

        var start = startInput.value;
        var end = endInput.value;

        if (!start || !end) {
            errorEl.hidden = true;
            return false;
        }

        if (start > end) {
            errorEl.textContent = 'Start date must be on or before end date.';
            errorEl.hidden = false;
            return false;
        }

        errorEl.hidden = true;
        return true;
    }

    /**
     * Handle "Delete by Range" button click.
     */
    function handleDeleteByRange() {
        var startInput = document.getElementById('overrides-start-date');
        var endInput = document.getElementById('overrides-end-date');
        if (!startInput || !endInput) return;

        var start = startInput.value;
        var end = endInput.value;

        if (!start || !end) {
            Toast.show('Please select both start and end dates.', 'error');
            return;
        }

        if (!validateDateRange()) return;

        var payload = { mode: 'range', start_date: start, end_date: end };

        // Preview first to get count
        previewBulkDelete(payload)
            .then(function (count) {
                var msg = count + ' override(s) will be deleted between ' + start + ' and ' + end + '.';
                var rendered = ConfirmDialog.show({
                    title: 'Delete by Date Range',
                    message: msg,
                    requirePhrase: false,
                    onConfirm: function () {
                        executeBulkDelete(payload);
                    }
                });
                // Fail-safe: block deletion if dialog fails to render
                if (!rendered) {
                    Toast.show('Unable to display confirmation dialog. Deletion blocked for safety.', 'error');
                }
            })
            .catch(function (err) {
                Toast.show('Preview failed: ' + err.message, 'error');
            });
    }

    /**
     * Handle "Delete Selected" button click.
     */
    function handleDeleteSelected() {
        var keys = getSelectedKeys();
        if (keys.length === 0) return;

        var payload = { mode: 'keys', keys: keys };

        previewBulkDelete(payload)
            .then(function (count) {
                var msg = count + ' override(s) will be deleted.';
                var rendered = ConfirmDialog.show({
                    title: 'Delete Selected Overrides',
                    message: msg,
                    requirePhrase: false,
                    onConfirm: function () {
                        executeBulkDelete(payload);
                    }
                });
                // Fail-safe: block deletion if dialog fails to render
                if (!rendered) {
                    Toast.show('Unable to display confirmation dialog. Deletion blocked for safety.', 'error');
                }
            })
            .catch(function (err) {
                Toast.show('Preview failed: ' + err.message, 'error');
            });
    }

    /**
     * Handle "Clear All Overrides" button click.
     */
    function handleClearAll() {
        var payload = { mode: 'year', year: currentYear };

        previewBulkDelete(payload)
            .then(function (count) {
                if (count === 0) {
                    Toast.show('No overrides to clear for ' + currentYear + '.', 'error');
                    return;
                }
                var msg = 'This will delete ALL ' + count + ' override(s) for ' + currentYear + '.';
                var rendered = ConfirmDialog.show({
                    title: 'Clear All Overrides for ' + currentYear,
                    message: msg,
                    requirePhrase: true,
                    onConfirm: function () {
                        executeBulkDelete(payload);
                    }
                });
                // Fail-safe: block deletion if dialog fails to render
                if (!rendered) {
                    Toast.show('Unable to display confirmation dialog. Deletion blocked for safety.', 'error');
                }
            })
            .catch(function (err) {
                Toast.show('Preview failed: ' + err.message, 'error');
            });
    }

    /**
     * Call the preview endpoint to get a count of overrides that would be deleted.
     */
    function previewBulkDelete(payload) {
        return API.previewBulkDelete(payload).then(function (data) {
            return data.count;
        });
    }

    /**
     * Call the bulk delete endpoint to actually remove overrides.
     */
    function executeBulkDelete(payload) {
        API.bulkDeleteOverrides(payload)
            .then(function (result) {
                Toast.show(result.deleted_count + ' override(s) removed.', 'success');
                loadOverrides();
                // Refresh dashboard calendar if available
                if (typeof Dashboard !== 'undefined' && Dashboard.load) {
                    Dashboard.load();
                }
            })
            .catch(function (err) {
                Toast.show('Delete failed: ' + err.message, 'error');
            });
    }

    // --- Public API ---
    return {
        init: init,
        load: loadOverrides,
        groupByMonth: groupByMonth
    };
})();
