/* DC-ShiftMaster Pro — Shared WebSocket client for real-time coverage events */
var WS = (function () {
    var callbacks = [];
    var socket = null;
    var reconnectTimer = null;
    var indicator = null;

    function getUrl() {
        var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
        return proto + '//' + location.host + '/ws/coverage';
    }

    function createIndicator() {
        if (indicator) return;
        indicator = document.createElement('div');
        indicator.className = 'ws-status ws-disconnected';
        indicator.title = 'Real-time updates disconnected';
        document.body.appendChild(indicator);
    }

    function setConnected(connected) {
        createIndicator();
        if (connected) {
            indicator.className = 'ws-status ws-connected';
            indicator.title = 'Real-time updates active';
        } else {
            indicator.className = 'ws-status ws-disconnected';
            indicator.title = 'Real-time updates disconnected';
        }
    }

    function connect() {
        if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
            return;
        }

        try {
            socket = new WebSocket(getUrl());
        } catch (e) {
            scheduleReconnect();
            return;
        }

        socket.onopen = function () {
            setConnected(true);
        };

        socket.onmessage = function (evt) {
            var data;
            try {
                data = JSON.parse(evt.data);
            } catch (e) {
                return;
            }
            for (var i = 0; i < callbacks.length; i++) {
                try { callbacks[i](data); } catch (e) { /* ignore listener errors */ }
            }
        };

        socket.onclose = function () {
            setConnected(false);
            scheduleReconnect();
        };

        socket.onerror = function () {
            setConnected(false);
            try { socket.close(); } catch (e) { /* already closing */ }
        };
    }

    function scheduleReconnect() {
        if (reconnectTimer) return;
        reconnectTimer = setTimeout(function () {
            reconnectTimer = null;
            connect();
        }, 3000);
    }

    function onCoverageEvent(callback) {
        if (typeof callback === 'function') {
            callbacks.push(callback);
        }
    }

    // Auto-connect on script load
    connect();

    return { onCoverageEvent: onCoverageEvent };
})();
