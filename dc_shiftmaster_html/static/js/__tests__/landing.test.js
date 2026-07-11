/**
 * Unit tests for LandingPage module — team list, create, join, select, fallback
 * Feature: multi-team-profiles
 * Requirements: 4.1, 4.3, 4.4
 */
const fs = require('fs');
const path = require('path');

function loadState() {
    const src = fs.readFileSync(
        path.resolve(__dirname, '..', 'state.js'),
        'utf-8'
    );
    const script = new Function('global', `
        with (global) {
            ${src}
            global.AppState = AppState;
        }
    `);
    script(global);
}

function loadLandingPage() {
    const src = fs.readFileSync(
        path.resolve(__dirname, '..', 'landing.js'),
        'utf-8'
    );
    const script = new Function('global', `
        with (global) {
            ${src}
            global.LandingPage = LandingPage;
        }
    `);
    script(global);
}

// Helper to set up a minimal DOM for the landing page
function setupDOM() {
    document.body.innerHTML = '<div id="landing-view"></div>';
}

// Helper to flush all pending promises
function flushPromises() {
    return new Promise(resolve => process.nextTick(resolve))
        .then(() => new Promise(resolve => process.nextTick(resolve)))
        .then(() => new Promise(resolve => process.nextTick(resolve)))
        .then(() => new Promise(resolve => process.nextTick(resolve)))
        .then(() => new Promise(resolve => process.nextTick(resolve)));
}

// Common setup for all tests
beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
});

describe('LandingPage.fetchTeams — team list rendering', () => {
    beforeEach(() => {
        setupDOM();
        global.Toast = { show: jest.fn() };
        global.Router = { show: jest.fn() };
        global.API = { setRegion: jest.fn().mockResolvedValue({}) };
        loadState();
        loadLandingPage();
        global.LandingPage.init();
    });

    afterEach(async () => {
        await flushPromises();
        delete global.LandingPage;
        delete global.AppState;
        delete global.Toast;
        delete global.Router;
        delete global.API;
        global.fetch = undefined;
    });

    it('renders team cards with site_code and display_name on successful fetch', async () => {
        const teams = [
            { id: 1, site_code: 'ATL069', display_name: 'Atlanta Warehouse 69' },
            { id: 2, site_code: 'DFW001', display_name: 'Dallas Hub 1' }
        ];
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(teams)
        });

        global.LandingPage.fetchTeams();
        await flushPromises();

        const listEl = document.getElementById('landing-team-list');
        expect(listEl.querySelectorAll('.landing-team-card').length).toBe(2);

        const cards = listEl.querySelectorAll('.landing-team-card');
        expect(cards[0].querySelector('.team-site-code').textContent).toBe('ATL069');
        expect(cards[0].querySelector('.team-display-name').textContent).toBe('Atlanta Warehouse 69');
        expect(cards[1].querySelector('.team-site-code').textContent).toBe('DFW001');
        expect(cards[1].querySelector('.team-display-name').textContent).toBe('Dallas Hub 1');
    });

    it('shows empty message when user has no teams', async () => {
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve([])
        });

        global.LandingPage.fetchTeams();
        await flushPromises();

        const listEl = document.getElementById('landing-team-list');
        expect(listEl.querySelector('.landing-empty')).not.toBeNull();
        expect(listEl.querySelector('.landing-empty').textContent).toContain('not a member of any teams');
    });

    it('displays each team card with a Select button containing team id', async () => {
        const teams = [
            { id: 5, site_code: 'ORD123', display_name: 'Chicago Site' }
        ];
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve(teams)
        });

        global.LandingPage.fetchTeams();
        await flushPromises();

        const btn = document.querySelector('.team-select-btn');
        expect(btn).not.toBeNull();
        expect(btn.getAttribute('data-team-id')).toBe('5');
    });
});


describe('LandingPage.createTeam — site code validation', () => {
    beforeEach(() => {
        setupDOM();
        global.Toast = { show: jest.fn() };
        global.Router = { show: jest.fn() };
        global.API = { setRegion: jest.fn().mockResolvedValue({}) };
        loadState();
        loadLandingPage();
        global.LandingPage.init();
        global.fetch = jest.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    });

    afterEach(async () => {
        await flushPromises();
        delete global.LandingPage;
        delete global.AppState;
        delete global.Toast;
        delete global.Router;
        delete global.API;
        global.fetch = undefined;
    });

    it('shows error for invalid site code format (lowercase letters)', () => {
        document.getElementById('create-site-code').value = 'atl069';
        document.getElementById('create-display-name').value = 'Test Team';

        document.getElementById('create-team-btn').click();

        const errorEl = document.getElementById('create-site-code-error');
        expect(errorEl.hidden).toBe(false);
    });

    it('shows error for site code that is too short', () => {
        document.getElementById('create-site-code').value = 'AT';
        document.getElementById('create-display-name').value = 'Test Team';

        document.getElementById('create-team-btn').click();

        const errorEl = document.getElementById('create-site-code-error');
        expect(errorEl.hidden).toBe(false);
    });

    it('shows error for site code with wrong pattern (digits first)', () => {
        document.getElementById('create-site-code').value = '069ATL';
        document.getElementById('create-display-name').value = 'Test Team';

        document.getElementById('create-team-btn').click();

        const errorEl = document.getElementById('create-site-code-error');
        expect(errorEl.hidden).toBe(false);
    });

    it('shows error for site code with special characters', () => {
        document.getElementById('create-site-code').value = 'AT!069';
        document.getElementById('create-display-name').value = 'Test Team';

        document.getElementById('create-team-btn').click();

        const errorEl = document.getElementById('create-site-code-error');
        expect(errorEl.hidden).toBe(false);
    });

    it('does not show error for valid site code format', async () => {
        document.getElementById('create-site-code').value = 'ATL069';
        document.getElementById('create-display-name').value = 'Atlanta 69';

        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ id: 1, site_code: 'ATL069' })
        });

        document.getElementById('create-team-btn').click();
        await flushPromises();

        const errorEl = document.getElementById('create-site-code-error');
        expect(errorEl.hidden).toBe(true);
    });

    it('does not call fetch when site code is invalid', () => {
        document.getElementById('create-site-code').value = 'invalid';
        document.getElementById('create-display-name').value = 'Test Team';

        const fetchSpy = jest.fn();
        global.fetch = fetchSpy;

        document.getElementById('create-team-btn').click();

        const postCalls = fetchSpy.mock.calls.filter(
            call => call[1] && call[1].method === 'POST'
        );
        expect(postCalls.length).toBe(0);
    });
});


describe('LandingPage.joinTeam — form submission', () => {
    beforeEach(() => {
        setupDOM();
        global.Toast = { show: jest.fn() };
        global.Router = { show: jest.fn() };
        global.API = { setRegion: jest.fn().mockResolvedValue({}) };
        loadState();
        loadLandingPage();
        global.LandingPage.init();
        global.fetch = jest.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    });

    afterEach(async () => {
        await flushPromises();
        delete global.LandingPage;
        delete global.AppState;
        delete global.Toast;
        delete global.Router;
        delete global.API;
        global.fetch = undefined;
    });

    it('calls fetch with correct body when joining a valid site code', async () => {
        document.getElementById('join-site-code').value = 'DFW001';

        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ team_id: 3, site_code: 'DFW001' })
        });

        document.getElementById('join-team-btn').click();
        await flushPromises();

        const joinCall = global.fetch.mock.calls.find(
            call => call[0] === '/api/teams/0/join' && call[1] && call[1].method === 'POST'
        );
        expect(joinCall).toBeDefined();

        const body = JSON.parse(joinCall[1].body);
        expect(body.site_code).toBe('DFW001');
    });

    it('rejects invalid site code in join form', () => {
        document.getElementById('join-site-code').value = 'bad';

        const fetchSpy = jest.fn();
        global.fetch = fetchSpy;

        document.getElementById('join-team-btn').click();

        const errorEl = document.getElementById('join-site-code-error');
        expect(errorEl.hidden).toBe(false);

        const postCalls = fetchSpy.mock.calls.filter(
            call => call[1] && call[1].method === 'POST'
        );
        expect(postCalls.length).toBe(0);
    });

    it('shows success toast after successful join', async () => {
        document.getElementById('join-site-code').value = 'ATL070';

        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ team_id: 4 })
        });

        document.getElementById('join-team-btn').click();
        await flushPromises();

        expect(global.Toast.show).toHaveBeenCalledWith(
            expect.stringContaining('ATL070'),
            'success'
        );
    });
});


describe('LandingPage.selectTeam — team selection triggers view switch', () => {
    beforeEach(() => {
        setupDOM();
        global.Toast = { show: jest.fn() };
        global.Router = { show: jest.fn() };
        global.API = { setRegion: jest.fn().mockResolvedValue({}) };
        loadState();
        loadLandingPage();
        global.LandingPage.init();
        global.fetch = jest.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    });

    afterEach(async () => {
        await flushPromises();
        delete global.LandingPage;
        delete global.AppState;
        delete global.Toast;
        delete global.Router;
        delete global.API;
        global.fetch = undefined;
    });

    it('calls /api/teams/select with the correct team_id', async () => {
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ active_team_id: 7 })
        });

        global.LandingPage.selectTeam(7);
        await flushPromises();

        const selectCall = global.fetch.mock.calls.find(
            call => call[0] === '/api/teams/select'
        );
        expect(selectCall).toBeDefined();
        const body = JSON.parse(selectCall[1].body);
        expect(body.team_id).toBe(7);
    });

    it('calls AppState.setActiveTeam after successful selection', async () => {
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ active_team_id: 7 })
        });

        const spy = jest.spyOn(global.AppState, 'setActiveTeam');

        global.LandingPage.selectTeam(7);
        await flushPromises();

        expect(spy).toHaveBeenCalledWith({ id: 7 });
    });

    it('calls Router.show("dashboard") after successful selection', async () => {
        global.fetch = jest.fn().mockResolvedValue({
            ok: true,
            json: () => Promise.resolve({ active_team_id: 7 })
        });

        global.LandingPage.selectTeam(7);
        await flushPromises();

        expect(global.Router.show).toHaveBeenCalledWith('dashboard');
    });

    it('shows error toast when selection fails', async () => {
        global.fetch = jest.fn().mockResolvedValue({
            ok: false,
            json: () => Promise.resolve({ error: 'Team not found' })
        });

        global.LandingPage.selectTeam(999);
        await flushPromises();

        expect(global.Toast.show).toHaveBeenCalledWith('Team not found', 'error');
    });
});


describe('LandingPage fallback — auto-select last active team on fetch failure (Req 4.1)', () => {
    afterEach(async () => {
        await flushPromises();
        delete global.LandingPage;
        delete global.AppState;
        delete global.Toast;
        delete global.Router;
        delete global.API;
        global.fetch = undefined;
    });

    it('triggers Router.show("dashboard") when fetch fails and last active team exists', async () => {
        setupDOM();
        global.Toast = { show: jest.fn() };
        global.Router = { show: jest.fn() };
        global.API = { setRegion: jest.fn().mockResolvedValue({}) };

        // Set last active team in real localStorage
        localStorage.setItem('sm_last_active_team_id', '5');

        loadState();
        loadLandingPage();
        global.LandingPage.init();

        global.fetch = jest.fn(function (url) {
            if (url === '/api/teams') {
                return Promise.reject(new Error('Network error'));
            }
            if (url === '/api/teams/select') {
                return Promise.resolve({
                    ok: true,
                    json: () => Promise.resolve({ active_team_id: 5 })
                });
            }
            return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
        });

        global.LandingPage.fetchTeams();
        await flushPromises();

        // Fallback should select last active team and navigate to dashboard
        expect(global.Router.show).toHaveBeenCalledWith('dashboard');
    });

    it('shows error state when fetch fails and no last active team exists', async () => {
        setupDOM();
        global.Toast = { show: jest.fn() };
        global.Router = { show: jest.fn() };
        global.API = { setRegion: jest.fn().mockResolvedValue({}) };

        // Ensure no last active team in localStorage (already cleared by top-level beforeEach)
        loadState();
        loadLandingPage();
        global.LandingPage.init();

        global.fetch = jest.fn(function (url) {
            if (url === '/api/teams') {
                return Promise.reject(new Error('Network error'));
            }
            return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
        });

        global.LandingPage.fetchTeams();
        await flushPromises();

        var errorEl = document.getElementById('landing-error');
        expect(errorEl).not.toBeNull();
        expect(errorEl.hidden).toBe(false);
    });

    it('shows error state when fetch returns non-ok response and no last active team', async () => {
        setupDOM();
        global.Toast = { show: jest.fn() };
        global.Router = { show: jest.fn() };
        global.API = { setRegion: jest.fn().mockResolvedValue({}) };

        loadState();
        loadLandingPage();
        global.LandingPage.init();

        global.fetch = jest.fn(function (url) {
            if (url === '/api/teams') {
                return Promise.resolve({
                    ok: false,
                    json: () => Promise.resolve({ error: 'Server error' })
                });
            }
            return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
        });

        global.LandingPage.fetchTeams();
        await flushPromises();

        var errorEl = document.getElementById('landing-error');
        expect(errorEl).not.toBeNull();
        expect(errorEl.hidden).toBe(false);
    });
});
