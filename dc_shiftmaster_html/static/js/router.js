/* DC-ShiftMaster Pro — Client-side view router */
var Router = (function () {
    var views = ['dashboard', 'team', 'settings', 'export', 'login', 'coverage', 'my-shifts', 'profile', 'landing'];
    var loaders = {
        dashboard: function () { if (typeof loadDashboard === 'function') loadDashboard(); },
        team:      function () { if (typeof loadTeam === 'function') loadTeam(); },
        settings:  function () { if (typeof loadSettings === 'function') loadSettings(); },
        export:    function () { if (typeof loadExport === 'function') loadExport(); },
        login:     function () { if (typeof loadLogin === 'function') loadLogin(); },
        coverage:  function () { if (typeof loadCoverage === 'function') loadCoverage(); },
        'my-shifts': function () { if (typeof loadPersonalDashboard === 'function') loadPersonalDashboard(); },
        profile: function () { if (typeof loadProfile === 'function') loadProfile(); },
        landing: function () { if (typeof LandingPage !== 'undefined' && LandingPage.show) LandingPage.show(); }
    };

    function show(name) {
        // Require auth for all views except login
        if (name !== 'login' && !AppState.user) {
            show('login');
            return;
        }

        // Require active team for team-scoped views (not login, not landing)
        if (name !== 'login' && name !== 'landing' && !AppState.getActiveTeam()) {
            show('landing');
            return;
        }

        // If navigating away from landing, hide it properly
        if (name !== 'landing' && typeof LandingPage !== 'undefined' && LandingPage.hide) {
            LandingPage.hide();
        }

        views.forEach(function (v) {
            var el = document.getElementById(v + '-view');
            if (el) el.hidden = (v !== name);
        });
        // Hide sidebar and header on login and landing views
        var sidebar = document.getElementById('sidebar');
        var header = document.getElementById('header');
        var bottomNav = document.getElementById('bottom-nav');
        var hideChrome = (name === 'login' || name === 'landing');
        if (sidebar) sidebar.style.display = hideChrome ? 'none' : '';
        if (header) header.style.display = hideChrome ? 'none' : '';
        if (bottomNav) bottomNav.style.display = hideChrome ? 'none' : '';

        document.querySelectorAll('.nav-item').forEach(function (item) {
            item.classList.toggle('active', item.getAttribute('data-view') === name);
        });
        document.querySelectorAll('.bottom-nav-item').forEach(function (item) {
            item.classList.toggle('active', item.getAttribute('data-view') === name);
        });
        if (loaders[name]) loaders[name]();
    }

    /**
     * Navigate to a named route (e.g. '/landing', '/dashboard').
     * Strips leading slash and maps to view name.
     */
    function navigate(path) {
        var name = path.replace(/^\//, '') || 'dashboard';
        show(name);
    }

    function init() {
        document.querySelectorAll('.nav-item').forEach(function (item) {
            item.addEventListener('click', function () {
                show(item.getAttribute('data-view'));
            });
        });
        document.querySelectorAll('.bottom-nav-item').forEach(function (item) {
            item.addEventListener('click', function () {
                show(item.getAttribute('data-view'));
            });
        });
        AppState.updateHeader();

        // Initialize landing page DOM
        if (typeof LandingPage !== 'undefined' && LandingPage.init) LandingPage.init();

        // Initialize touch gestures for mobile swipe/pull-to-refresh
        if (typeof TouchGestures !== 'undefined') TouchGestures.init();

        // Check authentication — show login if not authenticated
        API.getCurrentUser().then(function (user) {
            AppState.user = user;
            // If no active team, show landing page for team selection
            if (!AppState.getActiveTeam()) {
                show('landing');
            } else {
                show('dashboard');
            }
        }).catch(function () {
            show('login');
        });
    }

    return { init: init, show: show, navigate: navigate };
})();

document.addEventListener('DOMContentLoaded', function () {
    Router.init();
});
