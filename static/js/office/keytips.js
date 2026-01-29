/**
 * KeyTips / Access Keys Implementation
 * Handles 'Alt' key navigation and command execution.
 */

document.addEventListener('DOMContentLoaded', () => {
    const registry = window.CommandRegistry;
    let keyTipMode = false;
    let sequence = '';

    // Mock KeyMap for demo (In real app, comes from definitions)
    const keyMap = {
        'A': 'file:toggle_backstage', // Archivo
        'O': 'tab:home', // Inicio (Hypothetical ID)
        'B': 'tab:insert', // Insertar
    };
    
    // Quick Access Toolbar keys
    const qatMap = {
        '1': 'file:save',
        '2': 'edit:undo',
        '3': 'edit:redo'
    };

    // Container for badges
    const overlay = document.createElement('div');
    overlay.id = 'keytip-overlay';
    overlay.className = 'fixed inset-0 pointer-events-none z-[100] hidden';
    document.body.appendChild(overlay);

    document.addEventListener('keydown', (e) => {
        // Toggle Mode with Alt
        if (e.key === 'Alt') {
            e.preventDefault(); // Prevent browser menu
            if (keyTipMode) {
                disableKeyTips();
            } else {
                enableKeyTips();
            }
            return;
        }

        if (!keyTipMode) return;

        // Handle navigation
        if (e.key === 'Escape') {
            disableKeyTips();
            return;
        }

        const char = e.key.toUpperCase();
        sequence += char;

        // Check Match
        // 1. Check QAT
        if (qatMap[char]) {
            registry.execute(qatMap[char]);
            disableKeyTips();
            return;
        }
        
        // 2. Check Tabs (Mock)
        if (keyMap[char]) {
            // If it's a tab, we switch tab then show tab-children keytips
            // For MVP: Just execute straightforward commands like Backstage
            if (keyMap[char] === 'file:toggle_backstage') {
                registry.execute('file:toggle_backstage');
                disableKeyTips();
            } else {
                console.log(`KeyTip navigated to: ${keyMap[char]}`);
                disableKeyTips(); // For now just close
            }
        }
        
    });

    document.addEventListener('click', () => {
        if (keyTipMode) disableKeyTips();
    });

    function enableKeyTips() {
        keyTipMode = true;
        sequence = '';
        overlay.innerHTML = '';
        overlay.classList.remove('hidden');

        // Render Badges
        // 1. File Button
        renderBadge(document.querySelector('[data-command="file:toggle_backstage"]'), 'A');
        
        // 2. Tabs (Mock selectors)
        // Ideally we select by ID or index
        const tabs = document.querySelectorAll('.ribbon-tab:not([data-command])');
        // Inicio=O, Insertar=B, etc.
        if(tabs[0]) renderBadge(tabs[0], 'O');
        if(tabs[1]) renderBadge(tabs[1], 'B');
        
        // 3. QAT
        // We find QAT buttons and assign 1, 2, 3
        const qatBtns = document.querySelectorAll('#title-bar [data-command]');
        qatBtns.forEach((btn, idx) => {
            if (idx < 9) renderBadge(btn, (idx + 1).toString());
        });
    }

    function disableKeyTips() {
        keyTipMode = false;
        sequence = '';
        overlay.classList.add('hidden');
        overlay.innerHTML = '';
    }

    function renderBadge(target, label) {
        if (!target) return;
        const rect = target.getBoundingClientRect();
        
        const badge = document.createElement('div');
        badge.className = 'absolute bg-neutral-90 text-white text-[10px] font-bold px-1 rounded-sm shadow-sm border border-white leading-tight flex items-center justify-center animate__animated animate__fadeIn animate__faster';
        badge.textContent = label;
        
        // Center Badge relative to target
        const top = rect.bottom - 10;
        const left = rect.left + (rect.width / 2) - 8;
        
        badge.style.top = `${top}px`;
        badge.style.left = `${left}px`;
        
        overlay.appendChild(badge);
    }
});
