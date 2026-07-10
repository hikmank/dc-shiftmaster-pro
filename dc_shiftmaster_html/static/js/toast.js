/* DC-ShiftMaster Pro — Toast notifications */
var Toast = (function () {
    function show(message, type) {
        type = type || 'success';
        var container = document.getElementById('toast-container');
        var el = document.createElement('div');
        el.className = 'toast ' + type;
        el.textContent = message;
        container.appendChild(el);

        var delay = type === 'error' ? 5000 : 3000;
        setTimeout(function () {
            el.classList.add('removing');
            setTimeout(function () { el.remove(); }, 300);
        }, delay);
    }

    return { show: show };
})();
