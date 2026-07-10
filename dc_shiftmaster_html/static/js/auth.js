/* DC-ShiftMaster Pro — Login / Register form logic */
var Auth = (function () {
    var currentForm = 'login'; // 'login' or 'register'

    function render() {
        var container = document.getElementById('login-view');
        if (!container) return;

        container.innerHTML =
            '<div class="auth-wrapper">' +
                '<div class="auth-card">' +
                    '<h2 class="auth-title">DC-ShiftMaster Pro</h2>' +
                    '<div id="auth-error" class="auth-error" hidden></div>' +
                    '<div id="auth-form-container"></div>' +
                    '<p class="auth-toggle" id="auth-toggle-link"></p>' +
                '</div>' +
            '</div>';

        renderForm();
        document.getElementById('auth-toggle-link').addEventListener('click', toggleForm);
    }

    function renderForm() {
        var formContainer = document.getElementById('auth-form-container');
        if (!formContainer) return;

        hideError();

        if (currentForm === 'login') {
            formContainer.innerHTML =
                '<form id="auth-form">' +
                    '<div class="form-group">' +
                        '<label for="auth-username">Username</label>' +
                        '<input type="text" id="auth-username" class="form-control" required autocomplete="username">' +
                    '</div>' +
                    '<div class="form-group">' +
                        '<label for="auth-password">Password</label>' +
                        '<input type="password" id="auth-password" class="form-control" required autocomplete="current-password">' +
                    '</div>' +
                    '<button type="submit" class="btn btn-primary auth-submit">Login</button>' +
                '</form>';
            document.getElementById('auth-toggle-link').innerHTML =
                'Don\'t have an account? <a href="#" class="auth-link">Register</a>';
        } else {
            formContainer.innerHTML =
                '<form id="auth-form">' +
                    '<div class="form-group">' +
                        '<label for="auth-username">Username</label>' +
                        '<input type="text" id="auth-username" class="form-control" required autocomplete="username">' +
                    '</div>' +

                    '<div class="form-group">' +
                        '<label for="auth-password">Password</label>' +
                        '<input type="password" id="auth-password" class="form-control" required autocomplete="new-password">' +
                    '</div>' +
                    '<div class="form-group">' +
                        '<label for="auth-display-name">Display Name</label>' +
                        '<input type="text" id="auth-display-name" class="form-control" required>' +
                    '</div>' +
                    '<div class="form-group">' +
                        '<label for="auth-teammate-name">Link to Teammate (optional)</label>' +
                        '<select id="auth-teammate-name" class="form-control">' +
                            '<option value="">-- None --</option>' +
                        '</select>' +
                    '</div>' +
                    '<button type="submit" class="btn btn-primary auth-submit">Register</button>' +
                '</form>';

            // Populate teammate dropdown from public API (names only)
            API.getPublicTeammateNames().then(function (names) {
                var sel = document.getElementById('auth-teammate-name');
                if (sel && names && names.length) {
                    names.forEach(function (name) {
                        var opt = document.createElement('option');
                        opt.value = name;
                        opt.textContent = name;
                        sel.appendChild(opt);
                    });
                }
            }).catch(function () { /* ignore — dropdown stays with just "None" */ });
            document.getElementById('auth-toggle-link').innerHTML =
                'Already have an account? <a href="#" class="auth-link">Login</a>';
        }

        document.getElementById('auth-form').addEventListener('submit', handleSubmit);
    }

    function toggleForm(e) {
        e.preventDefault();
        currentForm = currentForm === 'login' ? 'register' : 'login';
        renderForm();
    }

    function showError(msg) {
        var el = document.getElementById('auth-error');
        if (el) {
            el.textContent = msg;
            el.hidden = false;
        }
    }

    function hideError() {
        var el = document.getElementById('auth-error');
        if (el) el.hidden = true;
    }

    async function handleSubmit(e) {
        e.preventDefault();
        hideError();

        var username = document.getElementById('auth-username').value.trim();
        var password = document.getElementById('auth-password').value;

        if (!username || !password) {
            showError('Username and password are required.');
            return;
        }

        try {
            var user;
            if (currentForm === 'login') {
                user = await API.login({ username: username, password: password });
            } else {
                var displayName = document.getElementById('auth-display-name').value.trim();
                if (!displayName) {
                    showError('Display name is required.');
                    return;
                }
                var teammateName = document.getElementById('auth-teammate-name').value.trim();
                user = await API.register({
                    username: username,
                    password: password,
                    display_name: displayName,
                    teammate_name: teammateName
                });
            }

            // Store user info in AppState
            AppState.user = user;
            Router.show('dashboard');
        } catch (err) {
            showError(err.message || 'An error occurred. Please try again.');
        }
    }

    return { render: render };
})();

/* Global loader called by Router */
function loadLogin() {
    Auth.render();
}
