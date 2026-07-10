/* DC-ShiftMaster Pro — Compliance Warning Modal */
var ComplianceModal = (function () {
    // Cached DOM references
    var modal = document.getElementById('compliance-modal');
    var heading = document.getElementById('compliance-heading');
    var violationsContainer = document.getElementById('compliance-violations');
    var acknowledgeBtn = document.getElementById('compliance-acknowledge');
    var cancelBtn = document.getElementById('compliance-cancel');

    // State
    var previousFocus = null;
    var currentOptions = null;
    var isLoading = false;

    // Rule label mapping
    var RULE_LABELS = {
        weekly_hours: 'Weekly Hours Exceeded',
        weekly_days: 'Weekly Days Exceeded',
        daily_hours: 'Daily Hours Exceeded'
    };

    /**
     * Map a violation rule string to a human-readable label.
     * @param {string} rule - One of 'weekly_hours', 'weekly_days', 'daily_hours'
     * @returns {string} Human-readable label or "Unknown Rule" for unrecognized rules
     */
    function ruleLabel(rule) {
        return RULE_LABELS[rule] || 'Unknown Rule';
    }

    /**
     * Render a single violation card element.
     * @param {Object} violation - {rule, projected, limit, window_start, window_end}
     * @returns {HTMLElement} The violation card DOM element
     */
    function renderViolationCard(violation) {
        var card = document.createElement('div');
        card.className = 'violation-card';
        card.setAttribute('role', 'alert');

        // Rule label
        var ruleSpan = document.createElement('span');
        ruleSpan.className = 'violation-rule';
        ruleSpan.textContent = ruleLabel(violation && violation.rule ? violation.rule : null);
        card.appendChild(ruleSpan);

        // Projected / Limit detail
        var detailSpan = document.createElement('span');
        detailSpan.className = 'violation-detail';
        var projected = (violation && violation.projected != null) ? violation.projected : 'N/A';
        var limit = (violation && violation.limit != null) ? violation.limit : 'N/A';
        detailSpan.textContent = 'Projected: ' + projected + ' | Limit: ' + limit;
        card.appendChild(detailSpan);

        // Date range (only if both window_start and window_end are non-null)
        if (violation && violation.window_start != null && violation.window_end != null) {
            var rangeSpan = document.createElement('span');
            rangeSpan.className = 'violation-range';
            rangeSpan.textContent = violation.window_start + ' \u2013 ' + violation.window_end;
            card.appendChild(rangeSpan);
        }

        return card;
    }

    /**
     * Show the compliance warning modal with violation details.
     * @param {Object} options
     * @param {Array} options.violations - Array of violation objects from API response
     * @param {Object} options.overrideData - Original override request data {date, shift_type, name}
     * @param {Function} options.onSuccess - Callback after successful acknowledgment resubmission
     */
    function show(options) {
        currentOptions = options || {};
        var violations = currentOptions.violations || [];

        // Store the currently focused element to restore later
        previousFocus = document.activeElement;

        // Clear any existing violation cards
        violationsContainer.innerHTML = '';

        // Render violation cards
        for (var i = 0; i < violations.length; i++) {
            var card = renderViolationCard(violations[i]);
            violationsContainer.appendChild(card);
        }

        // Show the modal by removing the hidden attribute
        modal.removeAttribute('hidden');

        // Move focus to the first focusable element inside the modal
        var firstFocusable = getFirstFocusableElement();
        if (firstFocusable) {
            firstFocusable.focus();
        }
    }

    /**
     * Close the compliance warning modal and restore focus.
     */
    function close() {
        // Hide the modal
        modal.setAttribute('hidden', '');

        // Clear violations container
        violationsContainer.innerHTML = '';

        // Restore focus to the previously focused element
        if (previousFocus && previousFocus.focus) {
            previousFocus.focus();
        }

        previousFocus = null;
        currentOptions = null;
    }

    // Cancel button closes modal without sending any API requests
    cancelBtn.addEventListener('click', function () {
        close();
    });

    // --- Focus Management ---

    var FOCUSABLE_SELECTOR = 'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

    /**
     * Get all focusable elements inside the modal.
     * @returns {Array} Array of focusable DOM elements
     */
    function getFocusableElements() {
        if (!modal) return [];
        return Array.prototype.slice.call(modal.querySelectorAll(FOCUSABLE_SELECTOR));
    }

    /**
     * Get the first focusable element inside the modal.
     * @returns {HTMLElement|null}
     */
    function getFirstFocusableElement() {
        var elements = getFocusableElements();
        return elements.length > 0 ? elements[0] : null;
    }

    /**
     * Handle keydown events for focus trapping and Escape to close.
     * @param {KeyboardEvent} e
     */
    function handleKeyDown(e) {
        // Only handle keys when modal is visible
        if (!modal || modal.hasAttribute('hidden')) return;

        if (e.key === 'Escape') {
            // Close on Escape only when not in loading state
            if (!isLoading) {
                e.preventDefault();
                close();
            }
            return;
        }

        if (e.key === 'Tab') {
            var focusableElements = getFocusableElements();
            if (focusableElements.length === 0) return;

            var firstElement = focusableElements[0];
            var lastElement = focusableElements[focusableElements.length - 1];

            if (e.shiftKey) {
                // Shift+Tab: if on first element, wrap to last
                if (document.activeElement === firstElement) {
                    e.preventDefault();
                    lastElement.focus();
                }
            } else {
                // Tab: if on last element, wrap to first
                if (document.activeElement === lastElement) {
                    e.preventDefault();
                    firstElement.focus();
                }
            }
        }
    }

    // Attach keydown listener to document for focus trapping and Escape handling
    document.addEventListener('keydown', handleKeyDown);

    // Acknowledge & Proceed click handler
    acknowledgeBtn.addEventListener('click', function () {
        if (isLoading || !currentOptions) return;

        // Store callback before close() resets currentOptions
        var onSuccess = currentOptions.onSuccess;
        var overrideData = currentOptions.overrideData || {};

        // Build resubmission payload with acknowledge_violations flag
        var payload = {};
        var keys = Object.keys(overrideData);
        for (var i = 0; i < keys.length; i++) {
            payload[keys[i]] = overrideData[keys[i]];
        }
        payload.acknowledge_violations = true;

        // Set loading state
        isLoading = true;
        acknowledgeBtn.disabled = true;
        cancelBtn.disabled = true;
        acknowledgeBtn.textContent = 'Submitting...';

        API.setOverrideRaw(payload)
            .then(function (result) {
                if (result.status === 201) {
                    close();
                    if (typeof onSuccess === 'function') {
                        onSuccess();
                    }
                    Toast.show('Override saved', 'success');
                } else {
                    close();
                    var errorMsg = (result.body && result.body.error) ? result.body.error : 'Request failed';
                    Toast.show(errorMsg, 'error');
                }
            })
            .catch(function () {
                close();
                Toast.show('Request failed', 'error');
            })
            .finally(function () {
                isLoading = false;
                acknowledgeBtn.disabled = false;
                cancelBtn.disabled = false;
                acknowledgeBtn.textContent = 'Acknowledge & Proceed';
            });
    });

    return {
        show: show,
        close: close,
        ruleLabel: ruleLabel,
        renderViolationCard: renderViolationCard,
        get isLoading() { return isLoading; }
    };
})();
