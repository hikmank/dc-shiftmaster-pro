/* DC-ShiftMaster Pro — Coverage request board */
var Coverage = (function () {
    var STATUS_STYLES = {
        open:      { border: '#3b82f6', badge: '#3b82f6', label: 'Open' },
        claimed:   { border: '#22c55e', badge: '#22c55e', label: 'Claimed' },
        cancelled: { border: '#9ca3af', badge: '#9ca3af', label: 'Cancelled' }
    };

    function escHtml(s) {
        return String(s || '')
            .replace(/&/g, '&amp;')
            .replace(/"/g, '&quot;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }

    function render() {
        var container = document.getElementById('coverage-view');
        if (!container) return;

        container.innerHTML =
            '<h2>Coverage Requests</h2>' +
            '<div class="form-card" id="coverage-form-card">' +
                '<h3>Request Coverage</h3>' +
                '<form id="coverage-form">' +
                    '<div class="form-row">' +
                        '<div class="form-group">' +
                            '<label for="cov-date">Date</label>' +
                            '<input type="date" id="cov-date" class="form-control" required>' +
                        '</div>' +
                        '<div class="form-group">' +
                            '<label for="cov-shift">Shift Type</label>' +
                            '<select id="cov-shift" class="form-control" required>' +
                                '<option value="day">Day</option>' +
                                '<option value="night">Night</option>' +
                            '</select>' +
                        '</div>' +
                    '</div>' +
                    '<div class="form-group">' +
                        '<label for="cov-note">Note (optional)</label>' +
                        '<textarea id="cov-note" class="form-control" rows="2" placeholder="Any details..."></textarea>' +
                    '</div>' +
                    '<button type="submit" class="btn btn-primary">Submit Request</button>' +
                '</form>' +
            '</div>' +
            '<div id="coverage-list"></div>';

        document.getElementById('coverage-form').addEventListener('submit', handleCreate);
        loadRequests();
    }

    function loadRequests() {
        API.getCoverageRequests()
            .then(function (requests) { renderList(requests || []); })
            .catch(function (err) {
                Toast.show(err.message, 'error');
                renderList([]);
            });
    }

    function renderList(requests) {
        var listEl = document.getElementById('coverage-list');
        if (!listEl) return;

        if (!requests.length) {
            listEl.innerHTML = '<p class="empty-message">No coverage requests yet.</p>';
            return;
        }

        listEl.innerHTML = '';
        requests.forEach(function (req) {
            listEl.appendChild(createCard(req));
        });
    }

    function createCard(req) {
        var style = STATUS_STYLES[req.status] || STATUS_STYLES.open;
        var currentUser = AppState.user || {};
        var isOwn = currentUser.id === req.requester_id;
        var isClaimer = currentUser.id === req.claimer_id;

        var card = document.createElement('div');
        card.className = 'coverage-card';
        card.style.borderLeft = '4px solid ' + style.border;

        // Header row: date + shift + status badge
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

        // Requester name
        var requester = document.createElement('div');
        requester.className = 'coverage-requester';
        requester.textContent = 'Requested by: ' + escHtml(req.requester_display_name || 'Unknown');
        card.appendChild(requester);

        // Note
        if (req.note) {
            var note = document.createElement('div');
            note.className = 'coverage-note';
            note.textContent = req.note;
            card.appendChild(note);
        }

        // Action buttons
        var actions = document.createElement('div');
        actions.className = 'coverage-actions';

        if (req.status === 'open') {
            if (!isOwn) {
                var claimBtn = document.createElement('button');
                claimBtn.className = 'btn btn-sm btn-primary';
                claimBtn.textContent = 'Claim';
                claimBtn.addEventListener('click', function () { handleClaim(req.id); });
                actions.appendChild(claimBtn);
            }
            if (isOwn) {
                var cancelBtn = document.createElement('button');
                cancelBtn.className = 'btn btn-sm btn-danger';
                cancelBtn.textContent = 'Cancel';
                cancelBtn.addEventListener('click', function () { handleCancel(req.id); });
                actions.appendChild(cancelBtn);
            }
        }

        if (req.status === 'claimed') {
            if (isClaimer) {
                var unclaimBtn = document.createElement('button');
                unclaimBtn.className = 'btn btn-sm';
                unclaimBtn.textContent = 'Unclaim';
                unclaimBtn.addEventListener('click', function () { handleUnclaim(req.id); });
                actions.appendChild(unclaimBtn);
            }
            if (isOwn) {
                var cancelBtn2 = document.createElement('button');
                cancelBtn2.className = 'btn btn-sm btn-danger';
                cancelBtn2.textContent = 'Cancel';
                cancelBtn2.addEventListener('click', function () { handleCancel(req.id); });
                actions.appendChild(cancelBtn2);
            }
        }

        if (actions.childNodes.length) {
            card.appendChild(actions);
        }

        return card;
    }

    async function handleCreate(e) {
        e.preventDefault();
        var dateVal = document.getElementById('cov-date').value;
        var shiftVal = document.getElementById('cov-shift').value;
        var noteVal = document.getElementById('cov-note').value.trim();

        if (!dateVal) {
            Toast.show('Please select a date.', 'error');
            return;
        }

        try {
            await API.createCoverageRequest({
                date: dateVal,
                shift_type: shiftVal,
                note: noteVal
            });
            Toast.show('Coverage request created', 'success');
            document.getElementById('coverage-form').reset();
            loadRequests();
        } catch (err) {
            Toast.show(err.message, 'error');
        }
    }

    async function handleClaim(id) {
        try {
            await API.claimCoverage(id);
            Toast.show('Shift claimed', 'success');
            loadRequests();
        } catch (err) {
            Toast.show(err.message, 'error');
        }
    }

    async function handleUnclaim(id) {
        try {
            await API.unclaimCoverage(id);
            Toast.show('Claim removed', 'success');
            loadRequests();
        } catch (err) {
            Toast.show(err.message, 'error');
        }
    }

    async function handleCancel(id) {
        if (!confirm('Cancel this coverage request?')) return;
        try {
            await API.cancelCoverage(id);
            Toast.show('Request cancelled', 'success');
            loadRequests();
        } catch (err) {
            Toast.show(err.message, 'error');
        }
    }

    return { render: render, loadRequests: loadRequests };
})();

/* Global loader called by Router */
function loadCoverage() {
    Coverage.render();
}
