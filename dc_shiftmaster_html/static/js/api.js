/* DC-ShiftMaster Pro — API fetch wrapper */
var API = (function () {
    async function request(url, opts) {
        opts = opts || {};
        opts.credentials = 'same-origin';
        var res = await fetch(url, opts);
        if (!res.ok) {
            var body;
            try { body = await res.json(); } catch (_) { body = {}; }
            throw new Error(body.error || 'Request failed (' + res.status + ')');
        }
        if (res.status === 204) return null;
        return res.json();
    }

    function json(method, url, data) {
        return request(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            credentials: 'same-origin',
            body: JSON.stringify(data)
        });
    }

    return {
        getSchedule: function (year, month) {
            return request('/api/schedule/' + year + '/' + month);
        },
        getTeammates: function () { return request('/api/teammates'); },
        addTeammate: function (data) { return json('POST', '/api/teammates', data); },
        updateTeammate: function (id, data) { return json('PUT', '/api/teammates/' + id, data); },
        deleteTeammate: function (id) { return request('/api/teammates/' + id, { method: 'DELETE' }); },
        clearAllTeammates: function () { return request('/api/teammates/all', { method: 'DELETE' }); },
        importCsv: function (file) {
            var fd = new FormData();
            fd.append('file', file);
            return request('/api/teammates/import-csv', { method: 'POST', body: fd });
        },
        getOverrides: function (year) { return request('/api/overrides/' + year); },
        setOverride: function (data) { return json('POST', '/api/overrides', data); },
        setOverrideRaw: function (data) {
            return fetch('/api/overrides', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            }).then(function (res) {
                return res.json().then(function (body) {
                    return { status: res.status, body: body };
                });
            });
        },
        removeOverride: function (data) {
            return request('/api/overrides', {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        },
        getShiftWindows: function () { return request('/api/settings/shift-windows'); },
        updateShiftWindow: function (type, data) {
            return json('PUT', '/api/settings/shift-windows/' + type, data);
        },
        getRegion: function () { return request('/api/settings/region'); },
        setRegion: function (region) { return json('PUT', '/api/settings/region', { region: region }); },
        importDb: function (file) {
            var fd = new FormData();
            fd.append('file', file);
            return request('/api/import-db', { method: 'POST', body: fd });
        },

        /* --- Auth --- */
        register: function (data) { return json('POST', '/api/auth/register', data); },
        login: function (data) { return json('POST', '/api/auth/login', data); },
        logout: function () { return request('/api/auth/logout', { method: 'POST' }); },
        getCurrentUser: function () { return request('/api/auth/me'); },
        updateProfile: function (data) { return json('PUT', '/api/auth/profile', data); },

        /* --- Public (no auth) --- */
        getPublicTeammateNames: function () { return request('/api/public/teammate-names'); },

        /* --- Bulk Override Delete --- */
        bulkDeleteOverrides: function (payload) {
            return json('DELETE', '/api/overrides/bulk', payload);
        },
        previewBulkDelete: function (payload) {
            return json('POST', '/api/overrides/bulk/preview', payload);
        },

        /* --- Coverage --- */
        getCoverageRequests: function (status) {
            var url = '/api/coverage';
            if (status) url += '?status=' + encodeURIComponent(status);
            return request(url);
        },
        createCoverageRequest: function (data) { return json('POST', '/api/coverage', data); },
        claimCoverage: function (id) { return json('POST', '/api/coverage/' + id + '/claim'); },
        unclaimCoverage: function (id) { return json('POST', '/api/coverage/' + id + '/unclaim'); },
        cancelCoverage: function (id) { return json('POST', '/api/coverage/' + id + '/cancel'); },
        getMyCoverageRequests: function () { return request('/api/coverage/my-requests'); },
        getMyShifts: function () { return request('/api/coverage/my-shifts'); }
    };
})();
