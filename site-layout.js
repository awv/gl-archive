// site-layout.js — Global Layout, Dark/Light Theme & Search Palette for GL Archive

// 0. IMMEDIATE THEME INITIALIZATION (Prevents white flash, defaults to dark)
(function() {
    const stored = localStorage.getItem('gl_theme');
    const theme = (stored === 'light') ? 'light' : 'dark';
    if (theme === 'dark') {
        document.documentElement.classList.add('dark');
    } else {
        document.documentElement.classList.remove('dark');
    }

    // Ensure theme.css is dynamically appended if not already in document
    if (!document.querySelector('link[href*="theme.css"]')) {
        const link = document.createElement('link');
        link.rel = 'stylesheet';
        link.href = 'assets/css/theme.css';
        document.head.appendChild(link);
    }
})();

document.addEventListener("DOMContentLoaded", () => {
    // 1. INJECT GLOBAL NAV & FOOTER
    const navContainer = document.getElementById('global-nav');
    const footerContainer = document.getElementById('global-footer');

    if (navContainer) {
        fetch('components/nav.html')
            .then(res => res.text())
            .then(html => {
                navContainer.innerHTML = html;
                initNavEvents();
            })
            .catch(err => console.error("Error loading nav:", err));
    }

    if (footerContainer) {
        fetch('components/footer.html')
            .then(res => res.text())
            .then(html => {
                footerContainer.innerHTML = html;
            })
            .catch(err => console.error("Error loading footer:", err));
    }

    // 2. SETUP COMMAND PALETTE / SEARCH MODAL
    initSearchPalette();
});

function initNavEvents() {
    const toggleBtn = document.getElementById('mobile-nav-toggle');
    const tray = document.getElementById('mobile-nav-tray');
    if (toggleBtn && tray) {
        toggleBtn.addEventListener('click', () => {
            tray.classList.toggle('hidden');
        });
    }

    const searchBtn = document.getElementById('nav-search-btn');
    if (searchBtn) {
        searchBtn.addEventListener('click', () => {
            window.openSearchPalette();
        });
    }

    // Theme Toggle Handler
    const themeBtn = document.getElementById('theme-toggle-btn');
    const mobileThemeBtn = document.getElementById('mobile-theme-toggle-btn');
    
    function updateThemeUI() {
        const isDark = document.documentElement.classList.contains('dark');
        const darkIcon = document.getElementById('theme-toggle-dark-icon');
        const lightIcon = document.getElementById('theme-toggle-light-icon');
        if (darkIcon && lightIcon) {
            if (isDark) {
                darkIcon.classList.add('hidden');
                lightIcon.classList.remove('hidden');
            } else {
                darkIcon.classList.remove('hidden');
                lightIcon.classList.add('hidden');
            }
        }
    }

    function toggleTheme() {
        const isDark = document.documentElement.classList.contains('dark');
        if (isDark) {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('gl_theme', 'light');
        } else {
            document.documentElement.classList.add('dark');
            localStorage.setItem('gl_theme', 'dark');
        }
        updateThemeUI();
    }

    if (themeBtn) {
        themeBtn.addEventListener('click', toggleTheme);
    }
    if (mobileThemeBtn) {
        mobileThemeBtn.addEventListener('click', toggleTheme);
    }
    updateThemeUI();

    // Highlight active nav item
    const currentPath = window.location.pathname.split('/').pop() || 'index.html';
    document.querySelectorAll('#global-nav nav a, #mobile-nav-tray a').forEach(a => {
        const href = a.getAttribute('href');
        if (!href) return;
        const hrefBase = href.split('?')[0];
        const isDirect = hrefBase === currentPath || (currentPath === '' && hrefBase === 'index.html');
        if (isDirect) {
            a.classList.add('text-emerald-700', 'dark:text-emerald-400', 'border-emerald-600', 'dark:border-emerald-500', 'font-bold');
            a.classList.remove('border-transparent', 'text-slate-600', 'dark:text-slate-400');
        }
    });
}

function initSearchPalette() {
    // Inject modal DOM if not already present
    if (document.getElementById('search-palette-modal')) return;

    const modal = document.createElement('div');
    modal.id = 'search-palette-modal';
    modal.className = 'hidden fixed inset-0 z-[9999] flex items-start justify-center pt-[12vh] px-4';
    modal.innerHTML = `
        <div id="search-backdrop" class="fixed inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity"></div>
        <div class="relative w-full max-w-xl bg-white border border-slate-200 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[75vh] z-10 animate-in fade-in zoom-in-95 duration-150">
            
            <!-- Search Input Header -->
            <div class="flex items-center px-4 py-3 border-b border-slate-100 gap-3">
                <svg class="w-5 h-5 text-slate-400 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
                <input type="text" id="palette-search-input" placeholder="Search athletes, clubs, or venues..." autocomplete="off"
                    class="w-full bg-transparent border-0 text-slate-900 placeholder-slate-400 text-sm focus:outline-none focus:ring-0 font-medium">
                <kbd class="text-[10px] font-mono font-semibold bg-slate-100 text-slate-500 px-2 py-0.5 rounded border border-slate-200 shrink-0">ESC</kbd>
            </div>

            <!-- Search Results Scroll Area -->
            <div id="palette-results" class="overflow-y-auto divide-y divide-slate-100 max-h-[55vh] p-2 empty:hidden">
                <!-- Dynamic results injected here -->
            </div>

            <!-- Empty / Help State -->
            <div id="palette-empty" class="p-8 text-center text-xs text-slate-400">
                Type an athlete's name (e.g. <em>Robert Gale</em> or <em>Dewi Griffiths</em>) or a club...
            </div>

            <!-- Footer Hint -->
            <div class="bg-slate-50 px-4 py-2 border-t border-slate-100 flex justify-between items-center text-[10px] font-mono text-slate-400">
                <span>Select with &uarr;&darr; and Enter</span>
                <span>Press ESC to close</span>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // Event listeners
    const input = document.getElementById('palette-search-input');
    const resultsContainer = document.getElementById('palette-results');
    const emptyState = document.getElementById('palette-empty');
    const backdrop = document.getElementById('search-backdrop');

    window.openSearchPalette = () => {
        modal.classList.remove('hidden');
        input.value = '';
        resultsContainer.innerHTML = '';
        emptyState.classList.remove('hidden');
        setTimeout(() => input.focus(), 50);
    };

    window.closeSearchPalette = () => {
        modal.classList.add('hidden');
    };

    backdrop.addEventListener('click', window.closeSearchPalette);

    document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            if (modal.classList.contains('hidden')) {
                window.openSearchPalette();
            } else {
                window.closeSearchPalette();
            }
        }
        if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
            window.closeSearchPalette();
        }
    });

    // Lazy index runners and clubs
    let indexedRunners = null;
    let indexedClubs = null;

    const buildIndex = () => {
        if (indexedRunners && indexedClubs) return;
        const results = window.glResults || [];
        const runnerMap = new Map();
        const clubMap = new Map();
        const nameChanges = window.glNameChanges || {};

        results.forEach(r => {
            // Runner
            const name = r.athlete;
            if (name && r.pos > 0) {
                const key = name.toLowerCase();
                if (!runnerMap.has(key)) {
                    runnerMap.set(key, {
                        name: name,
                        club: r.club,
                        finishes: 0,
                        gender: r.gender,
                        latestSeason: r.season,
                        aliases: new Set()
                    });
                }
                const entry = runnerMap.get(key);
                entry.finishes++;
                entry.club = r.club; // latest club
                entry.latestSeason = r.season;
                if (r.raw_name && r.raw_name.toLowerCase() !== key) {
                    entry.aliases.add(r.raw_name);
                }
            }

            // Club
            const club = r.club;
            if (club && club !== "Unattached") {
                const cKey = club.toLowerCase();
                if (!clubMap.has(cKey)) {
                    clubMap.set(cKey, { club: club, finishes: 0 });
                }
                clubMap.get(cKey).finishes++;
            }
        });

        // Add confirmed maiden/former names into runner aliases
        Object.values(nameChanges).forEach(nc => {
            if (nc.primary_name && nc.maiden_name) {
                const pKey = nc.primary_name.toLowerCase();
                if (runnerMap.has(pKey)) {
                    runnerMap.get(pKey).aliases.add(nc.maiden_name);
                }
            }
        });

        indexedRunners = Array.from(runnerMap.values());
        indexedClubs = Array.from(clubMap.values());
    };

    input.addEventListener('input', (e) => {
        buildIndex();
        const query = e.target.value.trim().toLowerCase();
        if (!query || query.length < 2) {
            resultsContainer.innerHTML = '';
            emptyState.classList.remove('hidden');
            return;
        }

        emptyState.classList.add('hidden');

        // Match runners (primary name, club, or alias/maiden name)
        const matchedRunners = indexedRunners.filter(r => {
            if (r.name.toLowerCase().includes(query)) return true;
            if (r.club.toLowerCase().includes(query)) return true;
            if (r.aliases) {
                for (const alias of r.aliases) {
                    if (alias.toLowerCase().includes(query)) return true;
                }
            }
            return false;
        }).slice(0, 10);

        // Match clubs
        const matchedClubs = indexedClubs.filter(c => 
            c.club.toLowerCase().includes(query)
        ).slice(0, 5);

        // Match venues
        const venuesData = window.VENUE_PROFILES || [];
        const matchedVenues = venuesData.filter(v =>
            v.name.toLowerCase().includes(query) || (v.region && v.region.toLowerCase().includes(query))
        ).slice(0, 3);

        let html = '';

        if (matchedVenues.length > 0) {
            html += `<div class="px-2.5 py-1 text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">Courses & Venues</div>`;
            html += matchedVenues.map(v => `
                <a href="venues.html" class="flex items-center justify-between p-2.5 rounded-lg hover:bg-slate-50 dark:hover:bg-slate-800 transition-colors group">
                    <div>
                        <div class="text-xs font-serif font-bold text-slate-900 dark:text-slate-100 group-hover:text-emerald-700 dark:group-hover:text-emerald-400 transition-colors">
                            📍 ${v.name}
                        </div>
                        <div class="text-[10px] text-slate-500 font-mono">
                            ${v.region} • ${v.tagline}
                        </div>
                    </div>
                    <div class="text-right">
                        <span class="text-[10px] font-mono font-semibold bg-emerald-50 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 px-2 py-0.5 rounded border border-emerald-200 dark:border-emerald-800">
                            ${v.fixture_count} fixtures
                        </span>
                    </div>
                </a>
            `).join('');
        }

        if (matchedRunners.length > 0) {
            html += `<div class="px-2.5 py-1 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400">Athletes</div>`;
            html += matchedRunners.map(r => {
                let aliasBadge = '';
                if (r.aliases && r.aliases.size > 0 && !r.name.toLowerCase().includes(query)) {
                    for (const alias of r.aliases) {
                        if (alias.toLowerCase().includes(query)) {
                            aliasBadge = `<span class="text-[9px] font-mono text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded border border-purple-200 ml-1.5 font-normal">matches: ${alias}</span>`;
                            break;
                        }
                    }
                }
                return `
                <a href="athlete.html?name=${encodeURIComponent(r.name)}&club=${encodeURIComponent(r.club)}&gender=${r.gender}" class="flex items-center justify-between p-2.5 rounded-lg hover:bg-slate-50 transition-colors group">
                    <div>
                        <div class="text-xs font-serif font-bold text-slate-900 group-hover:text-emerald-800 transition-colors flex items-center">
                            <span>${r.name}</span>
                            ${aliasBadge}
                        </div>
                        <div class="text-[11px] text-slate-500 font-sans">
                            ${r.club}
                        </div>
                    </div>
                    <div class="text-right">
                        <span class="text-[10px] font-mono font-semibold bg-slate-100 text-slate-600 px-2 py-0.5 rounded">
                            ${r.finishes} ${r.finishes === 1 ? 'race' : 'races'}
                        </span>
                    </div>
                </a>
            `;
            }).join('');
        }

        if (matchedClubs.length > 0) {
            html += `<div class="px-2.5 py-1 text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400 mt-2">Clubs</div>`;
            html += matchedClubs.map(c => `
                <a href="club.html?club=${encodeURIComponent(c.club)}" class="flex items-center justify-between p-2.5 rounded-lg hover:bg-slate-50 transition-colors group">
                    <div class="text-xs font-sans font-semibold text-slate-900 group-hover:text-emerald-800 transition-colors">
                        ${c.club}
                    </div>
                    <div class="text-[10px] font-mono text-slate-400">
                        ${c.finishes} total finishes
                    </div>
                </a>
            `).join('');
        }

        if (matchedRunners.length === 0 && matchedClubs.length === 0 && matchedVenues.length === 0) {
            html = `<div class="p-6 text-center text-xs text-slate-400">No athletes, clubs, or courses found matching "${query}".</div>`;
        }

        resultsContainer.innerHTML = html;
    });
}
