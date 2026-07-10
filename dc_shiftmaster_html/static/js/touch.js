/* DC-ShiftMaster Pro — Touch gesture handlers (mobile) */
var TouchGestures = (function () {
    var SWIPE_THRESHOLD = 50;   // min px to count as swipe
    var SWIPE_MAX_Y = 80;       // max vertical drift for horizontal swipe
    var PULL_THRESHOLD = 80;    // px to trigger pull-to-refresh

    var startX = 0;
    var startY = 0;
    var pulling = false;
    var pullIndicator = null;

    /* Swipeable views in order (login excluded) */
    var swipeViews = ['dashboard', 'coverage', 'my-shifts', 'team', 'settings'];

    function currentView() {
        for (var i = 0; i < swipeViews.length; i++) {
            var el = document.getElementById(swipeViews[i] + '-view');
            if (el && !el.hidden) return swipeViews[i];
        }
        return null;
    }

    function isMobile() {
        return window.innerWidth < 480;
    }

    /* ── Pull-to-refresh indicator ── */
    function ensureIndicator() {
        if (pullIndicator) return pullIndicator;
        pullIndicator = document.createElement('div');
        pullIndicator.className = 'pull-refresh-indicator';
        pullIndicator.textContent = '↻ Release to refresh';
        pullIndicator.setAttribute('aria-live', 'polite');
        var content = document.getElementById('content');
        if (content) content.insertBefore(pullIndicator, content.firstChild);
        return pullIndicator;
    }

    function showIndicator(dy) {
        var ind = ensureIndicator();
        var progress = Math.min(dy / PULL_THRESHOLD, 1);
        ind.style.height = Math.round(progress * 40) + 'px';
        ind.style.opacity = progress;
        ind.textContent = progress >= 1 ? '↻ Release to refresh' : '↓ Pull to refresh';
    }

    function hideIndicator() {
        if (pullIndicator) {
            pullIndicator.style.height = '0';
            pullIndicator.style.opacity = '0';
        }
    }

    function reloadCurrentView() {
        var view = currentView();
        if (!view) return;
        var loaders = {
            dashboard: 'loadDashboard',
            team: 'loadTeam',
            settings: 'loadSettings',
            export: 'loadExport',
            coverage: 'loadCoverage',
            'my-shifts': 'loadPersonalDashboard'
        };
        var fn = loaders[view];
        if (fn && typeof window[fn] === 'function') window[fn]();
    }

    /* ── Touch event handlers ── */
    function onTouchStart(e) {
        if (!isMobile()) return;
        var t = e.touches[0];
        startX = t.clientX;
        startY = t.clientY;
        pulling = false;
    }

    function onTouchMove(e) {
        if (!isMobile()) return;
        var t = e.touches[0];
        var dx = t.clientX - startX;
        var dy = t.clientY - startY;

        /* Pull-to-refresh: only when scrolled to top */
        var content = document.getElementById('content');
        if (dy > 0 && content && content.scrollTop <= 0 && Math.abs(dx) < 40) {
            pulling = true;
            showIndicator(dy);
            if (dy > 10) e.preventDefault();
        }
    }

    function onTouchEnd(e) {
        if (!isMobile()) return;
        var t = e.changedTouches[0];
        var dx = t.clientX - startX;
        var dy = t.clientY - startY;

        /* Pull-to-refresh */
        if (pulling) {
            if (dy >= PULL_THRESHOLD) reloadCurrentView();
            hideIndicator();
            pulling = false;
            return;
        }

        /* Swipe left/right between views */
        if (Math.abs(dx) >= SWIPE_THRESHOLD && Math.abs(dy) <= SWIPE_MAX_Y) {
            var cur = currentView();
            if (!cur) return;
            var idx = swipeViews.indexOf(cur);
            if (idx === -1) return;
            var next = dx < 0 ? idx + 1 : idx - 1;
            if (next >= 0 && next < swipeViews.length) {
                Router.show(swipeViews[next]);
            }
        }
    }

    function init() {
        var content = document.getElementById('content');
        if (!content) return;
        content.addEventListener('touchstart', onTouchStart, { passive: true });
        content.addEventListener('touchmove', onTouchMove, { passive: false });
        content.addEventListener('touchend', onTouchEnd, { passive: true });
    }

    return { init: init };
})();
