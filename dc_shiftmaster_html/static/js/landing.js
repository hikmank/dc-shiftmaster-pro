/* DC-ShiftMaster Pro — Landing Page (team selection, create, join) */
var LandingPage = (function () {
    var SITE_CODE_REGEX = /^[A-Z]{3}[0-9]{3}$/;
    var container = null;

    function init() {
        container = document.getElementById('landing-view');
        if (!container) return;
        render();
    }

    function show() {
        var landing = document.getElementById('landing-view');
        if (landing) landing.hidden = false;
        // Hide sidebar, header, bottom-nav, main content views
        var sidebar = document.getElementById('sidebar');
        var header = document.getElementById('header');
        var bottomNav = document.getElementById('bottom-nav');
        if (sidebar) sidebar.style.display = 'none';
        if (header) header.style.display = 'none';
        if (bottomNav) bottomNav.style.display = 'none';
        // Hide all other views
        var views = document.querySelectorAll('.view');
        views.forEach(function (v) {
            if (v.id !== 'landing-view') v.hidden = true;
        });
        fetchTeams();
    }

    function hide() {
        var landing = document.getElementById('landing-view');
        if (landing) landing.hidden = true;
        var sidebar = document.getElementById('sidebar');
        var header = document.getElementById('header');
        var bottomNav = document.getElementById('bottom-nav');
        if (sidebar) sidebar.style.display = '';
        if (header) header.style.display = '';
        if (bottomNav) bottomNav.style.display = '';
    }

    function render() {
        if (!container) return;
        container.innerHTML =
            '<div class="landing-page">' +
                '<h1 class="landing-title">DC-ShiftMaster Pro</h1>' +
                '<p class="landing-subtitle">Select a team to get started</p>' +

                '<!-- Team List -->' +
                '<div id="landing-team-list" class="landing-team-list"></div>' +

                '<!-- Error State -->' +
                '<div id="landing-error" class="landing-error" hidden>' +
                    '<p id="landing-error-msg">Failed to load teams.</p>' +
                    '<button id="landing-retry-btn" class="btn btn-primary">Retry</button>' +
                '</div>' +

                '<!-- Create Team Form -->' +
                '<div class="landing-section">' +
                    '<h2>Create a New Team</h2>' +
                    '<div class="form-group">' +
                        '<label for="create-site-code">Site Code</label>' +
                        '<input class="form-control" id="create-site-code" placeholder="e.g. ATL069" maxlength="6">' +
                        '<small id="create-site-code-error" class="form-error" hidden>Site code must be 3 uppercase letters followed by 3 digits</small>' +
                    '</div>' +
                    '<div class="form-group">' +
                        '<label for="create-display-name">Display Name</label>' +
                        '<input class="form-control" id="create-display-name" placeholder="e.g. Atlanta Warehouse 69">' +
                    '</div>' +
                    '<button id="create-team-btn" class="btn btn-primary">Create Team</button>' +
                '</div>' +

                '<!-- Join Team Form -->' +
                '<div class="landing-section">' +
                    '<h2>Join an Existing Team</h2>' +
                    '<div class="form-group">' +
                        '<label for="join-site-code">Site Code</label>' +
                        '<input class="form-control" id="join-site-code" placeholder="e.g. ATL069" maxlength="6">' +
                        '<small id="join-site-code-error" class="form-error" hidden>Site code must be 3 uppercase letters followed by 3 digits</small>' +
                    '</div>' +
                    '<button id="join-team-btn" class="btn btn-primary">Join Team</button>' +
                '</div>' +
            '</div>';

        wireHandlers();
    }

    function wireHandlers() {
        var retryBtn = document.getElementById('landing-retry-btn');
        if (retryBtn) {
            retryBtn.addEventListener('click', function () {
                document.getElementById('landing-error').hidden = true;
                fetchTeams();
            });
        }

        var createBtn = document.getElementById('create-team-btn');
        if (createBtn) {
            createBtn.addEventListener('click', createTeam);
        }

        var joinBtn = document.getElementById('join-team-btn');
        if (joinBtn) {
            joinBtn.addEventListener('click', joinTeam);
        }

        // Auto-uppercase site code inputs
        var createInput = document.getElementById('create-site-code');
        if (createInput) {
            createInput.addEventListener('input', function () {
                createInput.value = createInput.value.toUpperCase();
            });
        }
        var joinInput = document.getElementById('join-site-code');
        if (joinInput) {
            joinInput.addEventListener('input', function () {
                joinInput.value = joinInput.value.toUpperCase();
            });
        }
    }

    function fetchTeams() {
        var listEl = document.getElementById('landing-team-list');
        var errorEl = document.getElementById('landing-error');
        if (listEl) listEl.innerHTML = '<p class="loading">Loading teams...</p>';

        fetch('/api/teams', { credentials: 'same-origin' })
            .then(function (res) {
                if (!res.ok) throw new Error('Failed to load teams');
                return res.json();
            })
            .then(function (teams) {
                renderTeamList(teams);
            })
            .catch(function () {
                // Fallback behavior (Req 4.1): try to auto-select last active team
                var lastTeamId = AppState.getLastActiveTeam ? AppState.getLastActiveTeam() : null;
                if (lastTeamId) {
                    selectTeam(lastTeamId);
                } else {
                    // No fallback available — show error state with retry
                    if (listEl) listEl.innerHTML = '';
                    if (errorEl) errorEl.hidden = false;
                }
            });
    }

    function renderTeamList(teams) {
        var listEl = document.getElementById('landing-team-list');
        if (!listEl) return;

        if (!teams || teams.length === 0) {
            listEl.innerHTML = '<p class="landing-empty">You are not a member of any teams yet. Create or join a team below.</p>';
            return;
        }

        // Store teams for lookup when selecting
        var teamsById = {};
        teams.forEach(function (team) { teamsById[team.id] = team; });

        var html = '';
        teams.forEach(function (team) {
            html +=
                '<div class="landing-team-card" data-team-id="' + team.id + '">' +
                    '<span class="team-site-code">' + escHtml(team.site_code) + '</span>' +
                    '<span class="team-display-name">' + escHtml(team.display_name) + '</span>' +
                    '<button class="btn btn-primary btn-sm team-select-btn" data-team-id="' + team.id + '">Select</button>' +
                '</div>';
        });
        listEl.innerHTML = html;

        // Wire select buttons
        var selectBtns = listEl.querySelectorAll('.team-select-btn');
        for (var i = 0; i < selectBtns.length; i++) {
            selectBtns[i].addEventListener('click', function (e) {
                var teamId = parseInt(e.target.getAttribute('data-team-id'), 10);
                var teamData = teamsById[teamId] || null;
                selectTeam(teamId, teamData);
            });
        }
    }

    function validateSiteCode(code) {
        return SITE_CODE_REGEX.test(code);
    }

    function createTeam() {
        var siteCode = (document.getElementById('create-site-code').value || '').trim();
        var displayName = (document.getElementById('create-display-name').value || '').trim();
        var errorEl = document.getElementById('create-site-code-error');

        // Validate site code
        if (!validateSiteCode(siteCode)) {
            if (errorEl) errorEl.hidden = false;
            return;
        }
        if (errorEl) errorEl.hidden = true;

        if (!displayName) {
            Toast.show('Please enter a display name', 'error');
            return;
        }

        fetch('/api/teams', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ site_code: siteCode, display_name: displayName })
        })
        .then(function (res) {
            if (!res.ok) {
                return res.json().then(function (body) {
                    throw new Error(body.error || 'Failed to create team');
                });
            }
            return res.json();
        })
        .then(function (team) {
            Toast.show('Team ' + siteCode + ' created!', 'success');
            // Clear form
            document.getElementById('create-site-code').value = '';
            document.getElementById('create-display-name').value = '';
            // Auto-select the newly created team with full info
            selectTeam(team.id, { id: team.id, site_code: siteCode, display_name: displayName });
        })
        .catch(function (err) {
            Toast.show(err.message, 'error');
        });
    }

    function joinTeam() {
        var siteCode = (document.getElementById('join-site-code').value || '').trim();
        var errorEl = document.getElementById('join-site-code-error');

        // Validate site code
        if (!validateSiteCode(siteCode)) {
            if (errorEl) errorEl.hidden = false;
            return;
        }
        if (errorEl) errorEl.hidden = true;

        // POST to /api/teams/0/join with site_code in body
        // The backend ignores the team_id in the URL and looks up by site_code
        fetch('/api/teams/0/join', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ site_code: siteCode })
        })
        .then(function (res) {
            if (!res.ok) {
                return res.json().then(function (body) {
                    throw new Error(body.error || 'Failed to join team');
                });
            }
            return res.json();
        })
        .then(function (result) {
            Toast.show('Joined team ' + siteCode + '!', 'success');
            document.getElementById('join-site-code').value = '';
            // Refresh team list
            fetchTeams();
        })
        .catch(function (err) {
            Toast.show(err.message, 'error');
        });
    }

    function selectTeam(teamId, teamData) {
        fetch('/api/teams/select', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify({ team_id: teamId })
        })
        .then(function (res) {
            if (!res.ok) {
                return res.json().then(function (body) {
                    throw new Error(body.error || 'Failed to select team');
                });
            }
            return res.json();
        })
        .then(function (data) {
            // Store in local state with full team info (id, site_code, display_name)
            var teamInfo = teamData ? { id: teamId, site_code: teamData.site_code, display_name: teamData.display_name } : { id: data.active_team_id || teamId };
            if (AppState.setActiveTeam) {
                AppState.setActiveTeam(teamInfo);
            }
            // Store last active team for fallback recovery
            localStorage.setItem('lastActiveTeamId', String(teamId));
            // Redirect to dashboard
            hide();
            Router.show('dashboard');
        })
        .catch(function (err) {
            Toast.show(err.message, 'error');
        });
    }

    function escHtml(s) {
        if (!s) return '';
        return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    return {
        init: init,
        show: show,
        hide: hide,
        fetchTeams: fetchTeams,
        selectTeam: selectTeam
    };
})();

