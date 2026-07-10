/* DC-ShiftMaster Pro — Client-side state (year, region) */
var AppState = (function () {
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
    function updateHeader() {
        var info = document.getElementById('header-info');
        if (!info) return;
        var parts = [];
        var r = getRegion();
        if (r) parts.push(r);
        parts.push(String(getYear()));
        info.textContent = parts.join(' — ');
    }
    return {
        getYear: getYear,
        setYear: setYear,
        getRegion: getRegion,
        setRegion: setRegion,
        updateHeader: updateHeader
    };
})();
