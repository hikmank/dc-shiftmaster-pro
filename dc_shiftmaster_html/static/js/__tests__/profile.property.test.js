/**
 * Property-based tests for Profile UI
 * Feature: profile-ui
 *
 * Uses fast-check to verify correctness properties across many random inputs.
 */
const fc = require('fast-check');
const fs = require('fs');
const path = require('path');

const VIEWS = ['dashboard', 'team', 'settings', 'export', 'login', 'coverage', 'my-shifts', 'profile'];

/**
 * Build a minimal DOM that mirrors the relevant parts of index.html:
 * - view sections with ids like "dashboard-view", "team-view", etc.
 * - sidebar nav items with data-view attributes
 * - bottom nav items with data-view attributes
 * - sidebar, header, bottom-nav elements (Router.show toggles their display)
 * - toast-container (Toast.show needs it)
 */
function buildDOM() {
  // Sidebar
  const sidebarItems = VIEWS
    .filter(v => v !== 'login') // login has no sidebar nav item
    .map(v => `<li class="nav-item" data-view="${v}"><span>${v}</span></li>`)
    .join('');

  // Bottom nav items
  const bottomNavItems = ['dashboard', 'coverage', 'my-shifts', 'team', 'settings', 'profile']
    .map(v => `<li class="bottom-nav-item" data-view="${v}"><span>${v}</span></li>`)
    .join('');

  // View sections
  const sections = VIEWS
    .map(v => `<section id="${v}-view" class="view" ${v !== 'dashboard' ? 'hidden' : ''}></section>`)
    .join('');

  document.body.innerHTML = `
    <nav id="sidebar" class="sidebar">
      <ul class="nav-list">${sidebarItems}</ul>
    </nav>
    <header id="header" class="header"></header>
    <main id="content" class="content">${sections}</main>
    <nav class="bottom-nav" id="bottom-nav">
      <ul class="bottom-nav-list">${bottomNavItems}</ul>
    </nav>
    <div id="toast-container" class="toast-container"></div>
  `;
}

/**
 * Set up global stubs that router.js depends on.
 */
function setupGlobals() {
  // AppState stub — user must be truthy for non-login views
  global.AppState = {
    user: { id: 1, username: 'testuser', display_name: 'Test User', email: 'test@example.com', email_notifications_enabled: true },
    updateHeader: function () {},
    getYear: function () { return 2025; },
    setYear: function () {},
    getRegion: function () { return ''; },
    setRegion: function () {}
  };

  // API stub
  global.API = {
    getCurrentUser: function () { return Promise.resolve(global.AppState.user); },
    updateProfile: function () { return Promise.resolve(global.AppState.user); },
    logout: function () { return Promise.resolve(); },
    setRegion: function () { return Promise.resolve(); }
  };

  // Toast stub
  global.Toast = {
    show: function () {}
  };

  // Loader function stubs — Router calls these but we don't need them to do anything
  global.loadDashboard = function () {};
  global.loadTeam = function () {};
  global.loadSettings = function () {};
  global.loadExport = function () {};
  global.loadLogin = function () {};
  global.loadCoverage = function () {};
  global.loadPersonalDashboard = function () {};
  global.loadProfile = function () {};
  global.TouchGestures = { init: function () {} };
}

/**
 * Load router.js by evaluating its source in the current global scope.
 * This makes the Router IIFE execute and attach Router to global.
 */
function loadRouter() {
  const routerSrc = fs.readFileSync(
    path.resolve(__dirname, '..', 'router.js'),
    'utf-8'
  );
  // Remove the DOMContentLoaded listener so Router.init() doesn't auto-fire
  const stripped = routerSrc.replace(
    /document\.addEventListener\('DOMContentLoaded',\s*function\s*\(\)\s*\{[\s\S]*?\}\);/,
    ''
  );
  // Evaluate in global scope so `var Router` attaches to global
  const script = new Function('global', `
    with (global) {
      ${stripped}
      global.Router = Router;
    }
  `);
  script(global);
}

/**
 * Load profile.js by evaluating its source in the current global scope.
 * This makes the Profile IIFE execute and attach Profile + loadProfile to global.
 */
function loadProfileModule() {
  const profileSrc = fs.readFileSync(
    path.resolve(__dirname, '..', 'profile.js'),
    'utf-8'
  );
  const script = new Function('global', `
    with (global) {
      ${profileSrc}
      global.Profile = Profile;
      global.loadProfile = loadProfile;
    }
  `);
  script(global);
}

// ─── Test Suite ───────────────────────────────────────────────────────────────

describe('Feature: profile-ui, Property 1: Router view switching shows exactly one view and activates correct nav items', () => {
  beforeEach(() => {
    buildDOM();
    setupGlobals();
    loadRouter();
  });

  afterEach(() => {
    // Clean up globals
    delete global.Router;
    delete global.AppState;
    delete global.API;
    delete global.Toast;
    delete global.loadDashboard;
    delete global.loadTeam;
    delete global.loadSettings;
    delete global.loadExport;
    delete global.loadLogin;
    delete global.loadCoverage;
    delete global.loadPersonalDashboard;
    delete global.loadProfile;
    delete global.TouchGestures;
  });

  /**
   * **Validates: Requirements 1.3, 1.4**
   *
   * Property 1: For any view name in the registered views list, calling
   * Router.show(name) results in exactly one section being visible,
   * and the correct nav items having the 'active' class.
   */
  it('shows exactly one view section and activates correct nav items for any view', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...VIEWS),
        (viewName) => {
          // Act
          global.Router.show(viewName);

          // Assert: exactly one section is visible
          const sections = VIEWS.map(v => document.getElementById(v + '-view'));
          const visibleSections = sections.filter(s => !s.hidden);
          expect(visibleSections.length).toBe(1);
          expect(visibleSections[0].id).toBe(viewName + '-view');

          // Assert: all other sections are hidden
          const hiddenSections = sections.filter(s => s.hidden);
          expect(hiddenSections.length).toBe(VIEWS.length - 1);

          // Assert: correct sidebar nav items have 'active' class
          const sidebarItems = document.querySelectorAll('.nav-item');
          sidebarItems.forEach(item => {
            const dv = item.getAttribute('data-view');
            if (dv === viewName) {
              expect(item.classList.contains('active')).toBe(true);
            } else {
              expect(item.classList.contains('active')).toBe(false);
            }
          });

          // Assert: correct bottom nav items have 'active' class
          const bottomItems = document.querySelectorAll('.bottom-nav-item');
          bottomItems.forEach(item => {
            const dv = item.getAttribute('data-view');
            if (dv === viewName) {
              expect(item.classList.contains('active')).toBe(true);
            } else {
              expect(item.classList.contains('active')).toBe(false);
            }
          });
        }
      ),
      { numRuns: 100 }
    );
  });
});


describe('Feature: profile-ui, Property 2: Profile data population matches user object', () => {
  beforeEach(() => {
    buildDOM();
    setupGlobals();
    loadProfileModule();
  });

  afterEach(() => {
    delete global.Profile;
    delete global.Router;
    delete global.AppState;
    delete global.API;
    delete global.Toast;
    delete global.loadDashboard;
    delete global.loadTeam;
    delete global.loadSettings;
    delete global.loadExport;
    delete global.loadLogin;
    delete global.loadCoverage;
    delete global.loadPersonalDashboard;
    delete global.loadProfile;
    delete global.TouchGestures;
  });

  /**
   * **Validates: Requirements 2.2, 2.3, 2.4**
   *
   * Property 2: For any user object with arbitrary display_name, username,
   * email strings and random email_notifications_enabled booleans returned
   * by API.getCurrentUser(), after the profile view loads, the form fields
   * should match the user object values.
   */
  it('populates form fields matching the user object for any user data', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.record({
          id: fc.constant(1),
          display_name: fc.string({ minLength: 0, maxLength: 50 }),
          username: fc.string({ minLength: 1, maxLength: 30 }),
          // type="email" inputs sanitize values by stripping leading/trailing
          // whitespace and collapsing CR/LF per the HTML spec, so we generate
          // trimmed single-line strings to match real browser behavior.
          email: fc.string({ minLength: 0, maxLength: 60 })
            .map(s => s.replace(/[\r\n]/g, '').trim()),
          email_notifications_enabled: fc.boolean()
        }),
        async (user) => {
          // Re-build DOM for each iteration so we start fresh
          buildDOM();

          // Mock API.getCurrentUser to return the generated user
          let resolveGetUser;
          const getUserPromise = new Promise((resolve) => { resolveGetUser = resolve; });
          global.API.getCurrentUser = function () { return getUserPromise; };

          // Call loadProfile which renders HTML and calls API.getCurrentUser()
          global.loadProfile();

          // Resolve the mock with our generated user
          resolveGetUser(user);

          // Wait for the .then() handler to execute
          await getUserPromise;
          // Yield to microtask queue so .then() completes
          await new Promise((r) => setTimeout(r, 0));

          // Assert: email input value matches user.email
          const emailInput = document.getElementById('profile-email');
          expect(emailInput.value).toBe(user.email);

          // Assert: notification checkbox matches user.email_notifications_enabled
          const notifCheckbox = document.getElementById('profile-notifications');
          expect(notifCheckbox.checked).toBe(user.email_notifications_enabled);

          // Assert: display name text matches user.display_name
          const displayNameSpan = document.getElementById('profile-display-name');
          expect(displayNameSpan.textContent).toBe(user.display_name);

          // Assert: username text matches user.username
          const usernameSpan = document.getElementById('profile-username');
          expect(usernameSpan.textContent).toBe(user.username);
        }
      ),
      { numRuns: 100 }
    );
  });
});


describe('Feature: profile-ui, Property 3: Form submission sends correct payload', () => {
  beforeEach(() => {
    buildDOM();
    setupGlobals();
    loadProfileModule();
  });

  afterEach(() => {
    delete global.Profile;
    delete global.Router;
    delete global.AppState;
    delete global.API;
    delete global.Toast;
    delete global.loadDashboard;
    delete global.loadTeam;
    delete global.loadSettings;
    delete global.loadExport;
    delete global.loadLogin;
    delete global.loadCoverage;
    delete global.loadPersonalDashboard;
    delete global.loadProfile;
    delete global.TouchGestures;
  });

  /**
   * **Validates: Requirements 3.2, 4.2, 5.1, 6.2**
   *
   * Property 3: For any email string entered in the email input and any
   * boolean state of the notification checkbox, clicking the Save button
   * should produce a call to API.updateProfile whose argument contains
   * {email: <input value>, email_notifications_enabled: <checkbox state>}.
   */
  it('sends the correct payload with email and notification preference for any input', async () => {
    await fc.assert(
      fc.asyncProperty(
        // Generate trimmed single-line email strings to match HTML input sanitization
        fc.string({ minLength: 0, maxLength: 60 })
          .map(s => s.replace(/[\r\n]/g, '').trim()),
        fc.boolean(),
        async (email, notificationsEnabled) => {
          // Re-build DOM for each iteration so we start fresh
          buildDOM();

          // Mock API.getCurrentUser to resolve immediately so the form renders
          global.API.getCurrentUser = function () {
            return Promise.resolve({
              id: 1,
              display_name: 'Test User',
              username: 'testuser',
              email: 'original@example.com',
              email_notifications_enabled: false
            });
          };

          // Capture the payload sent to API.updateProfile
          let capturedPayload = null;
          global.API.updateProfile = function (data) {
            capturedPayload = data;
            return Promise.resolve(data);
          };

          // Load the profile form
          global.loadProfile();

          // Wait for API.getCurrentUser() to resolve and populate the form
          await new Promise((r) => setTimeout(r, 0));

          // Set the form input values to the generated values
          document.getElementById('profile-email').value = email;
          document.getElementById('profile-notifications').checked = notificationsEnabled;

          // Click the Save button
          document.getElementById('profile-save').click();

          // Assert the captured payload matches the form values
          expect(capturedPayload).not.toBeNull();
          expect(capturedPayload).toEqual({
            email: email,
            email_notifications_enabled: notificationsEnabled
          });
        }
      ),
      { numRuns: 100 }
    );
  });
});


describe('Feature: profile-ui, Property 4: Successful save updates AppState.user', () => {
  beforeEach(() => {
    buildDOM();
    setupGlobals();
    loadProfileModule();
  });

  afterEach(() => {
    delete global.Profile;
    delete global.Router;
    delete global.AppState;
    delete global.API;
    delete global.Toast;
    delete global.loadDashboard;
    delete global.loadTeam;
    delete global.loadSettings;
    delete global.loadExport;
    delete global.loadLogin;
    delete global.loadCoverage;
    delete global.loadPersonalDashboard;
    delete global.loadProfile;
    delete global.TouchGestures;
  });

  /**
   * **Validates: Requirements 5.4**
   *
   * Property 4: For any profile update response containing email and
   * email_notifications_enabled values, after a successful PUT /api/auth/profile,
   * AppState.user.email should equal the response's email and
   * AppState.user.email_notifications_enabled should equal the response's
   * email_notifications_enabled.
   */
  it('updates AppState.user to match the server response for any successful save', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.record({
          id: fc.constant(1),
          display_name: fc.string({ minLength: 0, maxLength: 50 }),
          username: fc.string({ minLength: 1, maxLength: 30 }),
          email: fc.string({ minLength: 0, maxLength: 60 })
            .map(s => s.replace(/[\r\n]/g, '').trim()),
          email_notifications_enabled: fc.boolean()
        }),
        async (response) => {
          // Re-build DOM for each iteration so we start fresh
          buildDOM();

          // Mock API.getCurrentUser to resolve immediately so the form renders
          global.API.getCurrentUser = function () {
            return Promise.resolve({
              id: 1,
              display_name: 'Original User',
              username: 'origuser',
              email: 'original@example.com',
              email_notifications_enabled: false
            });
          };

          // Mock API.updateProfile to return the generated response object
          global.API.updateProfile = function () {
            return Promise.resolve(response);
          };

          // Load the profile form
          global.loadProfile();

          // Wait for API.getCurrentUser() to resolve and populate the form
          await new Promise((r) => setTimeout(r, 0));

          // Click the Save button
          document.getElementById('profile-save').click();

          // Wait for the updateProfile promise chain to resolve
          await new Promise((r) => setTimeout(r, 0));

          // Assert AppState.user fields match the response
          expect(global.AppState.user.email).toBe(response.email);
          expect(global.AppState.user.email_notifications_enabled).toBe(response.email_notifications_enabled);
        }
      ),
      { numRuns: 100 }
    );
  });
});
