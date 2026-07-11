/* DC-ShiftMaster Pro — Team management view */
var Team = (function () {
    var SHIFT_TYPES = ['FHD', 'FHN', 'BHD', 'BHN', 'Custom'];

    function renderList(teammates) {
        var container = document.getElementById('team-list');
        container.innerHTML = '';

        var displayTypes = ['FHD', 'FHN', 'BHD', 'BHN', 'Custom'];
        var groups = {};
        displayTypes.forEach(function (st) { groups[st] = []; });
        teammates.forEach(function (t) {
            if (groups[t.shift_type]) groups[t.shift_type].push(t);
        });

        displayTypes.forEach(function (st) {
            // Only show Custom group if it has at least one teammate
            if (st === 'Custom' && groups[st].length === 0) return;

            var section = document.createElement('div');
            section.className = 'shift-group';
            var title = document.createElement('div');
            title.className = 'shift-group-title';
            title.textContent = st + ' (' + groups[st].length + ')';
            section.appendChild(title);

            groups[st].forEach(function (t) {
                section.appendChild(createRow(t));
            });
            container.appendChild(section);
        });
    }

    function createRow(t) {
        var row = document.createElement('div');
        row.className = 'teammate-row';
        row.setAttribute('data-id', t.id);

        var nameSpan = document.createElement('span');
        nameSpan.className = 'name';
        nameSpan.textContent = t.name;
        row.appendChild(nameSpan);

        if (t.shift_type === 'Custom' && t.custom_days && t.custom_days.length > 0) {
            var daysSpan = document.createElement('span');
            daysSpan.className = 'custom-days';
            daysSpan.textContent = t.custom_days.join(', ');
            row.appendChild(daysSpan);
        }

        if (t.custom_start) {
            var cs = document.createElement('span');
            cs.className = 'custom-start';
            cs.textContent = t.custom_start;
            row.appendChild(cs);
        }

        var actions = document.createElement('span');
        actions.className = 'actions';

        var editBtn = document.createElement('button');
        editBtn.className = 'btn btn-sm';
        editBtn.textContent = 'Edit';
        editBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            showInlineEdit(row, t);
        });

        var delBtn = document.createElement('button');
        delBtn.className = 'btn btn-sm btn-danger';
        delBtn.textContent = 'Del';
        delBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            if (confirm('Delete teammate "' + t.name + '"?')) {
                API.deleteTeammate(t.id)
                    .then(function () { Toast.show('Deleted ' + t.name, 'success'); load(); })
                    .catch(function (err) { Toast.show(err.message, 'error'); });
            }
        });

        actions.appendChild(editBtn);
        actions.appendChild(delBtn);
        row.appendChild(actions);
        return row;
    }

    function showInlineEdit(row, t) {
        row.innerHTML = '';
        var form = document.createElement('div');
        form.className = 'form-row';
        form.innerHTML =
            '<div class="form-group"><input class="form-control" id="edit-name" value="' + escHtml(t.name) + '"></div>' +
            '<div class="form-group"><select class="form-control" id="edit-shift">' +
            SHIFT_TYPES.map(function (s) { return '<option' + (s === t.shift_type ? ' selected' : '') + '>' + s + '</option>'; }).join('') +
            '</select></div>' +
            buildDaySelectorHtml('edit') +
            '<div class="form-group"><input class="form-control" id="edit-start" placeholder="HH:MM" value="' + escHtml(t.custom_start || '') + '"></div>';
        row.appendChild(form);

        // If editing a Custom teammate, show the day selector and pre-check stored days
        if (t.shift_type === 'Custom') {
            var editSelector = document.getElementById('edit-day-selector');
            if (editSelector) {
                editSelector.style.display = '';
                if (t.custom_days && t.custom_days.length > 0) {
                    var checkboxes = editSelector.querySelectorAll('.day-checkbox');
                    for (var i = 0; i < checkboxes.length; i++) {
                        if (t.custom_days.indexOf(checkboxes[i].value) !== -1) {
                            checkboxes[i].checked = true;
                        }
                    }
                }
            }
        }

        var warningContainer = document.getElementById('team-hours-warning-container');

        // Trigger hours warning banner when inline edit is shown
        var shiftSelect = document.getElementById('edit-shift');

        // Add change listener for shift type dropdown to show/hide day selector
        shiftSelect.addEventListener('change', function () {
            toggleDaySelector('edit', shiftSelect.value);
        });

        if (typeof HoursWarningBanner !== 'undefined' && warningContainer) {
            HoursWarningBanner.updateTeamAssignment({
                teammate: t,
                shiftType: shiftSelect.value,
                container: warningContainer
            });

            // Update banner when shift type dropdown changes
            shiftSelect.addEventListener('change', function () {
                HoursWarningBanner.updateTeamAssignment({
                    teammate: t,
                    shiftType: shiftSelect.value,
                    container: warningContainer
                });
            });
        }

        var saveBtn = document.createElement('button');
        saveBtn.className = 'btn btn-primary btn-sm';
        saveBtn.textContent = 'Save';
        saveBtn.addEventListener('click', function () {
            var shiftType = document.getElementById('edit-shift').value;
            var data = {
                name: document.getElementById('edit-name').value,
                shift_type: shiftType,
                custom_start: document.getElementById('edit-start').value
            };
            // For Custom shift type, collect checked days and validate
            if (shiftType === 'Custom') {
                var customDays = getCheckedDays('edit');
                if (customDays.length === 0) {
                    Toast.show('Please select at least one day', 'error');
                    return;
                }
                data.custom_days = customDays;
            }
            API.updateTeammate(t.id, data)
                .then(function () {
                    Toast.show('Updated', 'success');
                    clearTeamBanner();
                    load();
                })
                .catch(function (err) { Toast.show(err.message, 'error'); });
        });
        var cancelBtn = document.createElement('button');
        cancelBtn.className = 'btn btn-sm';
        cancelBtn.textContent = 'Cancel';
        cancelBtn.addEventListener('click', function () {
            clearTeamBanner();
            load();
        });
        row.appendChild(saveBtn);
        row.appendChild(cancelBtn);
    }

    function escHtml(s) {
        return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    var DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    function buildDaySelectorHtml(idPrefix) {
        var html = '<div class="day-selector" id="' + idPrefix + '-day-selector" style="display:none;margin-top:.5rem">' +
            '<label style="display:block;margin-bottom:.25rem">Days</label>' +
            '<div style="display:flex;gap:.75rem;flex-wrap:wrap">';
        DAY_NAMES.forEach(function (day) {
            html += '<label style="display:inline-flex;align-items:center;gap:.25rem">' +
                '<input type="checkbox" class="day-checkbox" value="' + day + '"> ' + day +
                '</label>';
        });
        html += '</div></div>';
        return html;
    }

    function toggleDaySelector(idPrefix, shiftType) {
        var selector = document.getElementById(idPrefix + '-day-selector');
        if (!selector) return;
        if (shiftType === 'Custom') {
            selector.style.display = '';
            // Reset all checkboxes when switching to Custom
            var checkboxes = selector.querySelectorAll('.day-checkbox');
            for (var i = 0; i < checkboxes.length; i++) {
                checkboxes[i].checked = false;
            }
        } else {
            selector.style.display = 'none';
        }
    }

    function getCheckedDays(idPrefix) {
        var selector = document.getElementById(idPrefix + '-day-selector');
        if (!selector) return [];
        var checkboxes = selector.querySelectorAll('.day-checkbox');
        var days = [];
        for (var i = 0; i < checkboxes.length; i++) {
            if (checkboxes[i].checked) days.push(checkboxes[i].value);
        }
        return days;
    }

    function showAddForm() {
        var container = document.getElementById('add-teammate-form');
        container.hidden = false;
        container.innerHTML =
            '<div class="form-row">' +
            '<div class="form-group"><label>Name</label><input class="form-control" id="new-name"></div>' +
            '<div class="form-group"><label>Shift Type</label><select class="form-control" id="new-shift">' +
            SHIFT_TYPES.map(function (s) { return '<option>' + s + '</option>'; }).join('') +
            '</select></div>' +
            '<div class="form-group"><label>Custom Start</label><input class="form-control" id="new-start" placeholder="HH:MM (optional)"></div>' +
            '</div>' +
            buildDaySelectorHtml('new') +
            '<div style="display:flex;gap:.5rem;margin-top:.5rem">' +
            '<button class="btn btn-primary" id="submit-new">Add</button>' +
            '<button class="btn" id="cancel-new">Cancel</button></div>';

        var shiftSelect = document.getElementById('new-shift');
        // Show/hide day selector based on initial value
        toggleDaySelector('new', shiftSelect.value);
        // Add change listener for shift type dropdown
        shiftSelect.addEventListener('change', function () {
            toggleDaySelector('new', shiftSelect.value);
        });

        document.getElementById('submit-new').addEventListener('click', function () {
            var shiftType = document.getElementById('new-shift').value;
            var data = {
                name: document.getElementById('new-name').value,
                shift_type: shiftType,
                custom_start: document.getElementById('new-start').value
            };
            // For Custom shift type, collect checked days and validate
            if (shiftType === 'Custom') {
                var customDays = getCheckedDays('new');
                if (customDays.length === 0) {
                    Toast.show('Please select at least one day', 'error');
                    return;
                }
                data.custom_days = customDays;
            }
            API.addTeammate(data)
                .then(function () { Toast.show('Teammate added', 'success'); container.hidden = true; load(); })
                .catch(function (err) { Toast.show(err.message, 'error'); });
        });
        document.getElementById('cancel-new').addEventListener('click', function () {
            container.hidden = true;
        });
    }

    /**
     * Clear the team hours warning banner (Requirement 5.4).
     * Called on list refresh, save, and cancel to remove stale banner state.
     */
    function clearTeamBanner() {
        var warningContainer = document.getElementById('team-hours-warning-container');
        if (typeof HoursWarningBanner !== 'undefined' && warningContainer) {
            HoursWarningBanner.clear(warningContainer);
        }
    }

    var currentTeammateCount = 0;

    function updateClearAllButton() {
        var btn = document.getElementById('clear-all-btn');
        if (btn) {
            btn.disabled = currentTeammateCount === 0;
        }
    }

    function load() {
        // Clear the hours warning banner on list refresh since no teammate is actively being edited
        clearTeamBanner();
        API.getTeammates()
            .then(function (list) {
                var teammates = list || [];
                currentTeammateCount = teammates.length;
                renderList(teammates);
                updateClearAllButton();
            })
            .catch(function (err) {
                Toast.show(err.message, 'error');
                currentTeammateCount = 0;
                renderList([]);
                updateClearAllButton();
            });
        // Initialize the Override Panel if available
        if (typeof OverridesPanel !== 'undefined' && OverridesPanel.init) {
            OverridesPanel.init();
        }
    }

    function exportTeamCsv() {
        API.getTeammates()
            .then(function (list) {
                var rows = ['name,shift_type,custom_start,custom_days'];
                (list || []).forEach(function (t) {
                    var days = '';
                    if (t.shift_type === 'Custom' && Array.isArray(t.custom_days) && t.custom_days.length) {
                        days = t.custom_days.join(';');
                    }
                    rows.push(
                        '"' + (t.name || '').replace(/"/g, '""') + '",' +
                        (t.shift_type || '') + ',' +
                        (t.custom_start || '') + ',' +
                        days
                    );
                });
                var csv = rows.join('\n');
                var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
                var url = URL.createObjectURL(blob);
                var a = document.createElement('a');
                a.href = url;
                a.download = 'teammates_export.csv';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            })
            .catch(function (err) { Toast.show(err.message, 'error'); });
    }

    /**
     * Upload a file to a given import endpoint and handle the result.
     * Displays imported_count, skipped_count, errors, and handles conflicts
     * by prompting for overwrite.
     */
    function handleImportUpload(file, endpoint, fileInputEl) {
        var fd = new FormData();
        fd.append('file', file);

        fetch(endpoint, { method: 'POST', body: fd })
            .then(function (res) {
                return res.json().then(function (body) {
                    return { status: res.status, body: body };
                });
            })
            .then(function (result) {
                var res = result.body;

                // If the response is just an error (400/413), show it and bail
                if (result.status >= 400 && res.error) {
                    Toast.show(res.error, 'error');
                    return;
                }

                // Build result summary message
                var parts = [];
                if (typeof res.imported_count !== 'undefined') {
                    parts.push('Imported: ' + res.imported_count);
                }
                if (typeof res.skipped_count !== 'undefined' && res.skipped_count > 0) {
                    parts.push('Skipped: ' + res.skipped_count);
                }
                if (res.errors && res.errors.length > 0) {
                    parts.push('Errors: ' + res.errors.length);
                }
                var summaryMsg = parts.join(' | ');

                // Show summary toast
                var toastType = (res.imported_count > 0) ? 'success' : 'error';
                Toast.show(summaryMsg, toastType);

                // If there are errors, log them for debugging
                if (res.errors && res.errors.length > 0) {
                    console.warn('Import errors:', res.errors);
                }

                // Handle conflicts — offer overwrite
                if (res.conflicts && res.conflicts.length > 0) {
                    var conflictDetails = res.conflicts.map(function (c) {
                        return c.date + ' ' + c.shift_type + ' (existing: ' + c.existing_name + ')';
                    }).join('\n');

                    var confirmMsg = res.conflicts.length + ' conflict(s) found:\n' +
                        conflictDetails + '\n\nDo you want to overwrite existing data?';

                    if (confirm(confirmMsg)) {
                        // Re-upload with overwrite=true
                        var overwriteFd = new FormData();
                        overwriteFd.append('file', file);
                        var overwriteUrl = endpoint + (endpoint.indexOf('?') === -1 ? '?' : '&') + 'overwrite=true';

                        fetch(overwriteUrl, { method: 'POST', body: overwriteFd })
                            .then(function (res2) {
                                return res2.json().then(function (body2) {
                                    return { status: res2.status, body: body2 };
                                });
                            })
                            .then(function (result2) {
                                var res2 = result2.body;
                                if (result2.status >= 400 && res2.error) {
                                    Toast.show(res2.error, 'error');
                                    return;
                                }
                                var msg2 = 'Overwrite complete — Imported: ' + (res2.imported_count || 0);
                                if (res2.skipped_count > 0) msg2 += ' | Skipped: ' + res2.skipped_count;
                                Toast.show(msg2, 'success');
                                load();
                            })
                            .catch(function (err) { Toast.show(err.message, 'error'); });
                    }
                }

                // Reload team list if anything was imported
                if (res.imported_count > 0) {
                    load();
                }
            })
            .catch(function (err) { Toast.show(err.message, 'error'); })
            .finally(function () { if (fileInputEl) fileInputEl.value = ''; });
    }

    document.addEventListener('DOMContentLoaded', function () {
        document.getElementById('add-teammate-btn').addEventListener('click', showAddForm);
        document.getElementById('export-csv-btn').addEventListener('click', exportTeamCsv);
        var csvInput = document.getElementById('csv-file-input');
        document.getElementById('import-csv-btn').addEventListener('click', function () {
            csvInput.click();
        });
        csvInput.addEventListener('change', function () {
            if (!csvInput.files.length) return;
            API.importCsv(csvInput.files[0])
                .then(function (res) {
                    var msg = 'Imported ' + res.imported_count + ' teammates';
                    if (res.skipped_rows && res.skipped_rows.length) {
                        msg += ', skipped rows: ' + res.skipped_rows.join(', ');
                    }
                    Toast.show(msg, 'success');
                    load();
                })
                .catch(function (err) { Toast.show(err.message, 'error'); })
                .finally(function () { csvInput.value = ''; });
        });

        // ICS import button and file picker
        var icsInput = document.getElementById('ics-file-input');
        document.getElementById('import-ics-btn').addEventListener('click', function () {
            icsInput.click();
        });
        icsInput.addEventListener('change', function () {
            if (!icsInput.files.length) return;
            handleImportUpload(icsInput.files[0], '/api/import/ics', icsInput);
        });

        // JSON schedule import button and file picker
        var scheduleJsonInput = document.getElementById('schedule-json-file-input');
        document.getElementById('import-schedule-json-btn').addEventListener('click', function () {
            scheduleJsonInput.click();
        });
        scheduleJsonInput.addEventListener('change', function () {
            if (!scheduleJsonInput.files.length) return;
            handleImportUpload(scheduleJsonInput.files[0], '/api/import/schedule-json', scheduleJsonInput);
        });

        // Clear All button
        document.getElementById('clear-all-btn').addEventListener('click', function () {
            if (currentTeammateCount === 0) return;
            if (confirm('Remove all ' + currentTeammateCount + ' teammates? This cannot be undone.')) {
                API.clearAllTeammates()
                    .then(function (res) {
                        var count = res && res.deleted ? res.deleted : 0;
                        Toast.show('Removed ' + count + ' teammates', 'success');
                        load();
                    })
                    .catch(function (err) {
                        Toast.show(err.message, 'error');
                    });
            }
        });
    });

    return { load: load };
})();

function loadTeam() { Team.load(); }
