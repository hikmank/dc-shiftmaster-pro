/* DC-ShiftMaster Pro — Export view */
var Export = (function () {
    function load() {
        var year = AppState.getYear();
        var view = document.getElementById('export-view');
        view.innerHTML =
            '<h2 style="margin-bottom:1rem">Export Schedule</h2>' +
            '<div class="export-section">' +
            '<h3>Date Range</h3>' +
            '<div class="form-row" style="margin-bottom:1rem">' +
            '<div class="form-group"><label>From</label><input type="date" class="form-control" id="exp-from" value="' + year + '-01-01"></div>' +
            '<div class="form-group"><label>To</label><input type="date" class="form-control" id="exp-to" value="' + year + '-12-31"></div>' +
            '</div>' +
            '<div style="display:flex;gap:.5rem;flex-wrap:wrap;margin-bottom:1rem">' +
            '<button class="btn btn-sm" id="range-full">Full Year</button>' +
            '<button class="btn btn-sm" id="range-q1">Q1 (Jan-Mar)</button>' +
            '<button class="btn btn-sm" id="range-q2">Q2 (Apr-Jun)</button>' +
            '<button class="btn btn-sm" id="range-q3">Q3 (Jul-Sep)</button>' +
            '<button class="btn btn-sm" id="range-q4">Q4 (Oct-Dec)</button>' +
            '<button class="btn btn-sm" id="range-month">Current Month</button>' +
            '</div>' +
            '<h3>Download</h3>' +
            '<div class="export-buttons">' +
            '<button class="btn" id="exp-csv">&#x1F4C4; Export CSV</button>' +
            '<button class="btn" id="exp-json">&#x1F4CB; Export JSON</button>' +
            '<button class="btn" id="exp-xlsx">&#x1F4CA; Export Excel</button>' +
            '<button class="btn" id="exp-ics">&#x1F4C5; ICS Calendar</button>' +
            '</div></div>';

        // Wire preset buttons
        var y = year;
        document.getElementById('range-full').addEventListener('click', function() { setRange(y+'-01-01', y+'-12-31'); });
        document.getElementById('range-q1').addEventListener('click', function() { setRange(y+'-01-01', y+'-03-31'); });
        document.getElementById('range-q2').addEventListener('click', function() { setRange(y+'-04-01', y+'-06-30'); });
        document.getElementById('range-q3').addEventListener('click', function() { setRange(y+'-07-01', y+'-09-30'); });
        document.getElementById('range-q4').addEventListener('click', function() { setRange(y+'-10-01', y+'-12-31'); });
        document.getElementById('range-month').addEventListener('click', function() {
            var now = new Date();
            var m = String(now.getMonth()+1).padStart(2,'0');
            var last = new Date(now.getFullYear(), now.getMonth()+1, 0).getDate();
            setRange(now.getFullYear()+'-'+m+'-01', now.getFullYear()+'-'+m+'-'+String(last).padStart(2,'0'));
        });

        wire('exp-csv', 'csv');
        wire('exp-json', 'json');
        wire('exp-xlsx', 'xlsx');
        wire('exp-ics', 'ics');
    }

    function setRange(from, to) {
        document.getElementById('exp-from').value = from;
        document.getElementById('exp-to').value = to;
    }

    function wire(btnId, format) {
        var btn = document.getElementById(btnId);
        btn.addEventListener('click', function () {
            var year = AppState.getYear();
            var from = document.getElementById('exp-from').value;
            var to = document.getElementById('exp-to').value;
            var url = '/api/export/' + year + '/' + format;
            var params = [];
            if (from) params.push('from=' + from);
            if (to) params.push('to=' + to);
            if (params.length) url += '?' + params.join('&');

            var orig = btn.innerHTML;
            btn.innerHTML = orig + ' <span class="spinner"></span>';
            btn.disabled = true;

            fetch(url).then(function (res) {
                if (!res.ok) {
                    return res.json().then(function (body) {
                        throw new Error(body.error || 'Export failed');
                    });
                }
                return res.blob().then(function (blob) {
                    var cd = res.headers.get('Content-Disposition') || '';
                    var match = cd.match(/filename=(.+)/);
                    var filename = match ? match[1] : 'schedule.' + format;
                    var a = document.createElement('a');
                    a.href = URL.createObjectURL(blob);
                    a.download = filename;
                    a.click();
                    URL.revokeObjectURL(a.href);
                    Toast.show('Download started', 'success');
                });
            }).catch(function (e) {
                Toast.show(e.message, 'error');
            }).finally(function () {
                btn.innerHTML = orig;
                btn.disabled = false;
            });
        });
    }

    return { load: load };
})();

function loadExport() { Export.load(); }
