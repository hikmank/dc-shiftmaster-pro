/* DC-ShiftMaster Pro — Settings view */
var Settings = (function () {
    function load() {
        var view = document.getElementById('settings-view');
        view.innerHTML =
            '<h2 style="margin-bottom:1rem">Settings</h2>' +
            '<div class="settings-section" id="sw-section">' +
            '<h3>Shift Windows</h3>' +
            '<div class="form-row">' +
            '<div class="form-group"><label>Day Start</label><input class="form-control" id="sw-day-start" placeholder="HH:MM"></div>' +
            '<div class="form-group"><label>Day End</label><input class="form-control" id="sw-day-end" placeholder="HH:MM"></div>' +
            '<div class="form-group"><label>Night Start</label><input class="form-control" id="sw-night-start" placeholder="HH:MM"></div>' +
            '<div class="form-group"><label>Night End</label><input class="form-control" id="sw-night-end" placeholder="HH:MM"></div>' +
            '</div>' +
            '<button class="btn btn-primary" id="save-sw" style="margin-top:.75rem">Save Shift Windows</button>' +
            '</div>' +
            '<div class="settings-section">' +
            '<h3>Region &amp; Year</h3>' +
            '<div class="form-row">' +
            '<div class="form-group"><label>Region</label><input class="form-control" id="set-region" placeholder="e.g. ATL68"></div>' +
            '<div class="form-group"><label>Year</label><input class="form-control" id="set-year" type="number"></div>' +
            '</div>' +
            '</div>' +
            '<div class="settings-section">' +
            '<h3>Import Database</h3>' +
            '<p style="color:var(--text-muted);font-size:.85rem;margin-bottom:.75rem">Upload a legacy teammates.db file to merge data.</p>' +
            '<input type="file" id="db-file-input" accept=".db" hidden>' +
            '<button class="btn" id="import-db-btn">Choose .db File</button>' +
            '</div>';

        // Populate current values
        document.getElementById('set-region').value = AppState.getRegion();
        document.getElementById('set-year').value = AppState.getYear();

        API.getShiftWindows().then(function (sw) {
            if (sw.day) {
                document.getElementById('sw-day-start').value = sw.day.start_time || '';
                document.getElementById('sw-day-end').value = sw.day.end_time || '';
            }
            if (sw.night) {
                document.getElementById('sw-night-start').value = sw.night.start_time || '';
                document.getElementById('sw-night-end').value = sw.night.end_time || '';
            }
        }).catch(function () {});

        // Save shift windows
        document.getElementById('save-sw').addEventListener('click', function () {
            var dayData = { start_time: document.getElementById('sw-day-start').value, end_time: document.getElementById('sw-day-end').value };
            var nightData = { start_time: document.getElementById('sw-night-start').value, end_time: document.getElementById('sw-night-end').value };
            Promise.all([
                API.updateShiftWindow('day', dayData),
                API.updateShiftWindow('night', nightData)
            ]).then(function () { Toast.show('Shift windows saved', 'success'); })
              .catch(function (e) { Toast.show(e.message, 'error'); });
        });

        // Region / year persistence
        document.getElementById('set-region').addEventListener('change', function () {
            AppState.setRegion(this.value);
            Toast.show('Region updated', 'success');
        });
        document.getElementById('set-year').addEventListener('change', function () {
            AppState.setYear(parseInt(this.value, 10) || new Date().getFullYear());
            Toast.show('Year updated', 'success');
        });

        // DB import
        var dbInput = document.getElementById('db-file-input');
        document.getElementById('import-db-btn').addEventListener('click', function () { dbInput.click(); });
        dbInput.addEventListener('change', function () {
            if (!dbInput.files.length) return;
            API.importDb(dbInput.files[0])
                .then(function (res) {
                    Toast.show('Imported: ' + res.teammates_count + ' teammates, ' +
                        res.shift_windows_count + ' shift windows, ' +
                        res.overrides_count + ' overrides', 'success');
                })
                .catch(function (e) { Toast.show(e.message, 'error'); })
                .finally(function () { dbInput.value = ''; });
        });
    }

    return { load: load };
})();

function loadSettings() { Settings.load(); }
