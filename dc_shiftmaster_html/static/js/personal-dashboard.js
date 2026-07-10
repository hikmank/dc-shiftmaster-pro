/* DC-ShiftMaster Pro — Personal dashboard (my shifts, my requests, claimed) */
var PersonalDashboard = (function () {
    var STATUS_STYLES = {
        open:      { badge: '#3b82f6', label: 'Open' },
        claimed:   { badge: '#22c55e', label: 'Claimed' },
        cancelled: { badge: '#9ca3af', label: 'Cancelled' }
    };

    function escHtml(s) {
        return String(s || '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function render() {
        var container = document.getElementById('my-shifts-view');
        if (!container) return;

        container.innerHTML =
            '<h2>My Dashboard</h2>' +
            '<div id="pd-my-shifts" class="pd-section">' +
                '<h3>My Upcoming Shifts</h3>' +
                '<div id="pd-shifts-list" class="pd-list"><p class="empty-message">Loading...</p></div>' +
            '</div>' +
            '<div id="pd-my-requests" class="pd-section">' +
                '<h3>My Coverage Requests</h3>' +
                '<div id="pd-requests-list" class="pd-list"><p class="empty-message">Loading...</p></div>' +
            '</div>' +
            '<div id="pd-claimed" class="pd-section">' +
                '<h3>Shifts I\'ve Claimed</h3>' +
                '<div id="pd-claimed-list" class="pd-list"><p class="empty-message">Loading...</p></div>' +
            '</div>';

        loadAll();
    }

    function loadAll() {
        loadMyShifts();
        loadMyRequests();
        loadClaimedShifts();
    }

    /* --- My Upcoming Shifts --- */
    function loadMyShifts() {
        API.getMyShifts()
            .then(function (shifts) { renderShifts(shifts || []); })
            .catch(function (err) {
                Toast.show(err.message, 'error');
                renderShifts([]);
            });
    }

    function renderShifts(shifts) {
        var el = document.getElementById('pd-shifts-list');
        if (!el) return;

        if (!shifts.length) {
            el.innerHTML = '<p class="empty-message">No upcoming shifts.</p>';
            return;
        }

        var html = '<table class="pd-table"><thead><tr>' +
            '<th>Date</th><th>Shift</th><th>Start</th><th>End</th>' +
            '</tr></thead><tbody>';

        shifts.forEach(function (s) {
            html += '<tr>' +
                '<td>' + escHtml(s.date) + '</td>' +
                '<td>' + escHtml(s.shift_type === 'day' ? 'Day' : 'Night') + '</td>' +
                '<td>' + escHtml(s.start_time || '') + '</td>' +
                '<td>' + escHtml(s.end_time || '') + '</td>' +
                '</tr>';
        });

        html += '</tbody></table>';
        el.innerHTML = html;
    }

    /* --- My Coverage Requests --- */
    function loadMyRequests() {
        API.getMyCoverageRequests()
            .then(function (requests) { renderRequests(requests || []); })
            .catch(function (err) {
                Toast.show(err.message, 'error');
                renderRequests([]);
            });
    }

    function renderRequests(requests) {
        var el = document.getElementById('pd-requests-list');
        if (!el) return;

        if (!requests.length) {
            el.innerHTML = '<p class="empty-message">No coverage requests posted.</p>';
            return;
        }

        el.innerHTML = '';
        requests.forEach(function (req) {
            el.appendChild(createRequestCard(req));
        });
    }

    function createRequestCard(req) {
        var style = STATUS_STYLES[req.status] || STATUS_STYLES.open;

        var card = document.createElement('div');
        card.className = 'coverage-card';
        card.style.borderLeft = '4px solid ' + style.badge;

        var header = document.createElement('div');
        header.className = 'coverage-card-header';

        var dateShift = document.createElement('span');
        dateShift.className = 'coverage-date-shift';
        dateShift.textContent = req.date + ' — ' + (req.shift_type === 'day' ? 'Day' : 'Night');
        header.appendChild(dateShift);

        var badge = document.createElement('span');
        badge.className = 'coverage-badge';
        badge.style.backgroundColor = style.badge;
        badge.textContent = style.label;
        header.appendChild(badge);

        card.appendChild(header);

        if (req.note) {
            var note = document.createElement('div');
            note.className = 'coverage-note';
            note.textContent = req.note;
            card.appendChild(note);
        }

        if (req.status === 'claimed' && req.claimer_display_name) {
            var claimer = document.createElement('div');
            claimer.className = 'coverage-requester';
            claimer.textContent = 'Claimed by: ' + escHtml(req.claimer_display_name);
            card.appendChild(claimer);
        }

        // Action buttons for own requests
        var actions = document.createElement('div');
        actions.className = 'coverage-actions';

        if (req.status === 'open' || req.status === 'claimed') {
            var cancelBtn = document.createElement('button');
            cancelBtn.className = 'btn btn-sm btn-danger';
            cancelBtn.textContent = 'Cancel';
            cancelBtn.addEventListener('click', function () { handleCancel(req.id); });
            actions.appendChild(cancelBtn);
        }

        if (actions.childNodes.length) {
            card.appendChild(actions);
        }

        return card;
    }

    /* --- Shifts I've Claimed --- */
    function loadClaimedShifts() {
        var currentUser = AppState.user || {};
        if (!currentUser.id) {
            renderClaimed([]);
            return;
        }

        API.getCoverageRequests()
            .then(function (requests) {
                var claimed = (requests || []).filter(function (r) {
                    return r.claimer_id === currentUser.id;
                });
                renderClaimed(claimed);
            })
            .catch(function (err) {
                Toast.show(err.message, 'error');
                renderClaimed([]);
            });
    }

    function renderClaimed(requests) {
        var el = document.getElementById('pd-claimed-list');
        if (!el) return;

        if (!requests.length) {
            el.innerHTML = '<p class="empty-message">No claimed shifts.</p>';
            return;
        }

        el.innerHTML = '';
        requests.forEach(function (req) {
            el.appendChild(createClaimedCard(req));
        });
    }

    function createClaimedCard(req) {
        var style = STATUS_STYLES[req.status] || STATUS_STYLES.open;

        var card = document.createElement('div');
        card.className = 'coverage-card';
        card.style.borderLeft = '4px solid ' + style.badge;

        var header = document.createElement('div');
        header.className = 'coverage-card-header';

        var dateShift = document.createElement('span');
        dateShift.className = 'coverage-date-shift';
        dateShift.textContent = req.date + ' — ' + (req.shift_type === 'day' ? 'Day' : 'Night');
        header.appendChild(dateShift);

        var badge = document.createElement('span');
        badge.className = 'coverage-badge';
        badge.style.backgroundColor = style.badge;
        badge.textContent = style.label;
        header.appendChild(badge);

        card.appendChild(header);

        var requester = document.createElement('div');
        requester.className = 'coverage-requester';
        requester.textContent = 'Requested by: ' + escHtml(req.requester_display_name || 'Unknown');
        card.appendChild(requester);

        if (req.note) {
            var note = document.createElement('div');
            note.className = 'coverage-note';
            note.textContent = req.note;
            card.appendChild(note);
        }

        // Unclaim button if still claimed
        if (req.status === 'claimed') {
            var actions = document.createElement('div');
            actions.className = 'coverage-actions';

            var unclaimBtn = document.createElement('button');
            unclaimBtn.className = 'btn btn-sm';
            unclaimBtn.textContent = 'Unclaim';
            unclaimBtn.addEventListener('click', function () { handleUnclaim(req.id); });
            actions.appendChild(unclaimBtn);

            card.appendChild(actions);
        }

        return card;
    }

    /* --- Actions --- */
    async function handleCancel(id) {
        if (!confirm('Cancel this coverage request?')) return;
        try {
            await API.cancelCoverage(id);
            Toast.show('Request cancelled', 'success');
            loadAll();
        } catch (err) {
            Toast.show(err.message, 'error');
        }
    }

    async function handleUnclaim(id) {
        try {
            await API.unclaimCoverage(id);
            Toast.show('Claim removed', 'success');
            loadAll();
        } catch (err) {
            Toast.show(err.message, 'error');
        }
    }

    // Auto-refresh on WebSocket coverage events
    WS.onCoverageEvent(function () {
        loadAll();
    });

    return { render: render, loadAll: loadAll };
})();

/* Global loader called by Router */
function loadPersonalDashboard() {
    PersonalDashboard.render();
}
