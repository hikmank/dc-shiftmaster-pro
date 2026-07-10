/* DC-ShiftMaster Pro — Client-side view router */
var Router = (function () {
    var views = ['dashboard', 'team', 'settings', 'export', 'login', 'coverage', 'my-shifts', 'profile'];
    var loaders = {
        dashboard: function () { if (typeof loadDashboard === 'function') loadDashboard(); },
        team:      function () { if (typeof loadTeam === 'function') loadTeam(); },
        settings:  function () { if (typeof loadSettings === 'function') loadSettings(); },
        export:    function () { if (typeof loadExport === 'function') loadExport(); },
        login:     function () { if (typeof loadLogin === 'function') loadLogin(); },
        coverage:  function () { if (typeof loadCoverage === 'function') loadCoverage(); },
        'my-shifts': function () { if (typeof loadPersonalDashboard === 'function') loadPersonalDashboard(); },
        profile: function () { if (typeof loadProfile === 'function') loadProfile(); }
    };

    function show(name) {
        // Require auth for all views except login
        if (name !== 'login' && !AppState.user) {
            show('login');
            return;
        }
        views.forEach(function (v) {
            var el = document.getElementById(v + '-view');
            if (el) el.hidden = (v !== name);
        });
        // Hide sidebar and header on login view
        var sidebar = document.getElementById('sidebar');
        var header = document.getElementById('header');
        var bottomNav = document.getElementById('bottom-nav');
        if (sidebar) sidebar.style.display = (name === 'login') ? 'none' : '';
        if (header) header.style.display = (name === 'login') ? 'none' : '';
        if (bottomNav) bottomNav.style.display = (name === 'login') ? 'none' : '';

        document.querySelectorAll('.nav-item').forEach(function (item) {
            item.classList.toggle('active', item.getAttribute('data-view') === name);
        });
        document.querySelectorAll('.bottom-nav-item').forEach(function (item) {
            item.classList.toggle('active', item.getAttribute('data-view') === name);
        });
        if (loaders[name]) loaders[name]();
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

        // Initialize touch gestures for mobile swipe/pull-to-refresh
        if (typeof TouchGestures !== 'undefined') TouchGestures.init();

        // Check authentication — show login if not authenticated
        API.getCurrentUser().then(function (user) {
            AppState.user = user;
            show('dashboard');
        }).catch(function () {
            show('login');
        });
    }

    return { init: init, show: show };
})();

document.addEventListener('DOMContentLoaded', function () {
    Router.init();
});
