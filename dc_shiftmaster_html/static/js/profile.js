/* DC-ShiftMaster Pro — Profile view */
var Profile = (function () {
    function load() {
        var view = document.getElementById('profile-view');
        view.innerHTML =
            '<h2>Profile</h2>' +
            '<div class="settings-section">' +
            '<div class="form-group">' +
            '<label>Display Name</label>' +
            '<span id="profile-display-name"></span>' +
            '</div>' +
            '<div class="form-group">' +
            '<label>Username</label>' +
            '<span id="profile-username"></span>' +
            '</div>' +
            '</div>' +
            '<div class="settings-section">' +
            '<div class="form-group">' +
            '<label>Email Address</label>' +
            '<input type="email" id="profile-email" class="form-control">' +
            '</div>' +
            '<div class="form-group">' +
            '<label>' +
            '<input type="checkbox" id="profile-notifications"> ' +
            'Enable email notifications' +
            '</label>' +
            '</div>' +
            '<button id="profile-save" class="btn btn-primary">Save</button>' +
            '</div>';

        API.getCurrentUser().then(function (user) {
            document.getElementById('profile-display-name').textContent = user.display_name;
            document.getElementById('profile-username').textContent = user.username;
            document.getElementById('profile-email').value = user.email;
            document.getElementById('profile-notifications').checked = user.email_notifications_enabled;
        }).catch(function (err) {
            Toast.show(err.message, 'error');
        });

        document.getElementById('profile-save').addEventListener('click', function () {
            var btn = document.getElementById('profile-save');
            btn.disabled = true;

            var email = document.getElementById('profile-email').value;
            var emailNotificationsEnabled = document.getElementById('profile-notifications').checked;

            API.updateProfile({ email: email, email_notifications_enabled: emailNotificationsEnabled })
                .then(function (data) {
                    Toast.show('Profile updated', 'success');
                    AppState.user = data;
                })
                .catch(function (err) {
                    Toast.show(err.message, 'error');
                })
                .finally(function () {
                    btn.disabled = false;
                });
        });
    }

    return { load: load };
})();

function loadProfile() { Profile.load(); }
