/* DC-ShiftMaster Pro — Bulk Delete Confirmation Dialog */
var ConfirmDialog = (function () {
    // Cached DOM references (set lazily to support testing without full DOM)
    var modal = null;
    var heading = null;
    var messageEl = null;
    var phraseContainer = null;
    var phraseInput = null;
    var confirmBtn = null;
    var cancelBtn = null;

    // State
    var previousFocus = null;
    var onConfirmCallback = null;
    var onCancelCallback = null;
    var requiresPhrase = false;
    var CONFIRMATION_PHRASE = 'DELETE ALL';

    /**
     * Lazily initialize DOM references. Returns false if critical elements are missing.
     */
    function ensureDom() {
        if (modal) return true;
        modal = document.getElementById('bulk-delete-confirm-modal');
        heading = document.getElementById('bulk-delete-confirm-heading');
        messageEl = document.getElementById('bulk-delete-confirm-message');
        phraseContainer = document.getElementById('bulk-delete-phrase-container');
        phraseInput = document.getElementById('bulk-delete-phrase-input');
        confirmBtn = document.getElementById('bulk-delete-confirm-btn');
        cancelBtn = document.getElementById('bulk-delete-cancel-btn');

        if (!modal || !messageEl || !confirmBtn || !cancelBtn) {
            // Reset references since initialization failed
            modal = null;
            return false;
        }

        // Bind events once
        confirmBtn.addEventListener('click', handleConfirm);
        cancelBtn.addEventListener('click', handleCancel);
        document.addEventListener('keydown', handleKeyDown);

        if (phraseInput) {
            phraseInput.addEventListener('input', handlePhraseInput);
        }

        return true;
    }

    /**
     * Show the confirmation dialog.
     *
     * @param {Object} options
     * @param {string} options.title - Dialog heading text
     * @param {string} options.message - Body message (can include count info)
     * @param {boolean} options.requirePhrase - If true, requires user to type "DELETE ALL"
     * @param {Function} options.onConfirm - Called when user confirms
     * @param {Function} options.onCancel - Called when user cancels (optional)
     * @returns {boolean} true if dialog rendered successfully, false if it failed (fail-safe)
     */
    function show(options) {
        if (!ensureDom()) {
            // Fail-safe: dialog could not render, block deletion
            return false;
        }

        options = options || {};
        onConfirmCallback = options.onConfirm || null;
        onCancelCallback = options.onCancel || null;
        requiresPhrase = !!options.requirePhrase;

        // Store previous focus for restoration
        previousFocus = document.activeElement;

        // Set title
        if (heading) {
            heading.textContent = options.title || 'Confirm Deletion';
        }

        // Set message
        messageEl.textContent = options.message || '';

        // Handle phrase input visibility
        if (phraseContainer && phraseInput) {
            if (requiresPhrase) {
                phraseContainer.removeAttribute('hidden');
                phraseInput.value = '';
                confirmBtn.disabled = true;
            } else {
                phraseContainer.setAttribute('hidden', '');
                phraseInput.value = '';
                confirmBtn.disabled = false;
            }
        } else if (requiresPhrase) {
            // If phrase elements are missing but phrase is required, fail-safe
            return false;
        } else {
            confirmBtn.disabled = false;
        }

        // Show the modal
        modal.removeAttribute('hidden');

        // Focus management: move focus into the dialog
        if (requiresPhrase && phraseInput) {
            phraseInput.focus();
        } else {
            cancelBtn.focus();
        }

        return true;
    }

    /**
     * Close the dialog and restore focus.
     */
    function close() {
        if (!modal) return;

        modal.setAttribute('hidden', '');

        // Clear state
        if (phraseInput) phraseInput.value = '';
        if (phraseContainer) phraseContainer.setAttribute('hidden', '');
        if (confirmBtn) confirmBtn.disabled = false;

        onConfirmCallback = null;
        onCancelCallback = null;
        requiresPhrase = false;

        // Restore focus
        if (previousFocus && previousFocus.focus) {
            previousFocus.focus();
        }
        previousFocus = null;
    }

    /**
     * Handle confirmation button click.
     */
    function handleConfirm() {
        var callback = onConfirmCallback;
        close();
        if (typeof callback === 'function') {
            callback();
        }
    }

    /**
     * Handle cancel button click.
     */
    function handleCancel() {
        var callback = onCancelCallback;
        close();
        if (typeof callback === 'function') {
            callback();
        }
    }

    /**
     * Handle phrase input changes — enable confirm only when exact phrase is typed.
     */
    function handlePhraseInput() {
        if (!requiresPhrase || !phraseInput || !confirmBtn) return;
        var value = phraseInput.value.trim();
        confirmBtn.disabled = (value !== CONFIRMATION_PHRASE);
    }

    /**
     * Handle keydown for Escape to close and Tab focus trapping.
     */
    function handleKeyDown(e) {
        if (!modal || modal.hasAttribute('hidden')) return;

        if (e.key === 'Escape') {
            e.preventDefault();
            handleCancel();
            return;
        }

        if (e.key === 'Tab') {
            var focusableSelector = 'button:not([disabled]):not([hidden]), input:not([disabled]):not([hidden]), [tabindex]:not([tabindex="-1"])';
            var focusable = Array.prototype.slice.call(modal.querySelectorAll(focusableSelector));
            // Filter out elements in hidden containers
            focusable = focusable.filter(function (el) {
                var parent = el.closest('[hidden]');
                return !parent || parent === modal;
            });

            if (focusable.length === 0) return;

            var first = focusable[0];
            var last = focusable[focusable.length - 1];

            if (e.shiftKey) {
                if (document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                }
            } else {
                if (document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            }
        }
    }

    // --- Public API ---
    return {
        show: show,
        close: close,
        CONFIRMATION_PHRASE: CONFIRMATION_PHRASE
    };
})();
