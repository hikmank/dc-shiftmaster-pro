/* DC-ShiftMaster Pro — Client-side state (year, region, active team) */
var AppState = (function () {
    var ACTIVE_TEAM_KEY = 'sm_active_team';
    var LAST_ACTIVE_TEAM_KEY = 'sm_last_active_team_id';

    function getYear() {
        var v = localStorage.getItem('sm_year');
        return v ? parseInt(v, 10) : new Date().getFullYear();
    }
    function setYear(y) {
        localStorage.setItem('sm_year', String(y));
        updateHeader();
    }
    function getRegion() {
        return localStorage.getItem('sm_region') || '';
    }
    function setRegion(r) {
        localStorage.setItem('sm_region', r);
        updateHeader();
        // Also push to server so exports use it
        API.setRegion(r).catch(function () {});
    }

    // --- Active Team State ---

    function getActiveTeam() {
        var raw = sessionStorage.getItem(ACTIVE_TEAM_KEY);
        if (!raw) return null;
        try {
            return JSON.parse(raw);
        } catch (e) {
            return null;
        }
    }

    function setActiveTeam(team) {
        sessionStorage.setItem(ACTIVE_TEAM_KEY, JSON.stringify(team));
        // Persist team id in localStorage for fallback recovery
        if (team && team.id) {
            localStorage.setItem(LAST_ACTIVE_TEAM_KEY, String(team.id));
        }
        updateHeader();
    }

    function clearActiveTeam() {
        sessionStorage.removeItem(ACTIVE_TEAM_KEY);
        updateHeader();
    }

    function getLastActiveTeam() {
        return localStorage.getItem(LAST_ACTIVE_TEAM_KEY);
    }

    // --- 403 Team Error Handling ---

    function handleTeamError(response) {
        if (response && response.status === 403) {
            var code = response.data && response.data.code;
            if (code === 'NO_TEAM' || code === 'INVALID_TEAM') {
                clearActiveTeam();
                // Redirect to landing page
                if (typeof Router !== 'undefined' && Router.navigate) {
                    Router.navigate('/landing');
                } else {
                    window.location.hash = '#/landing';
                }
                return true;
            }
        }
        return false;
    }

    function updateHeader() {
        var info = document.getElementById('header-info');
        if (!info) return;
        var parts = [];
        var team = getActiveTeam();
        if (team && team.site_code) {
            parts.push(team.site_code);
        } else {
            var r = getRegion();
            if (r) parts.push(r);
        }
        parts.push(String(getYear()));
        info.textContent = parts.join(' — ');
    }
    return {
        getYear: getYear,
        setYear: setYear,
        getRegion: getRegion,
        setRegion: setRegion,
        updateHeader: updateHeader,
        getActiveTeam: getActiveTeam,
        setActiveTeam: setActiveTeam,
        clearActiveTeam: clearActiveTeam,
        getLastActiveTeam: getLastActiveTeam,
        handleTeamError: handleTeamError
    };
})();
