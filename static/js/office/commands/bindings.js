/**
 * Command Bindings
 * Handles Event Delegation and Keyboard Shortcuts.
 */

document.addEventListener('DOMContentLoaded', () => {
    const registry = window.CommandRegistry;

    // 1. Click Delegation
    document.addEventListener('click', (e) => {
        // Traverse up to find element with data-command
        const trigger = e.target.closest('[data-command]');
        if (!trigger) return;

        const commandId = trigger.getAttribute('data-command');
        // Parse optional args if present
        let args = {};
        if (trigger.hasAttribute('data-command-args')) {
            try {
                args = JSON.parse(trigger.getAttribute('data-command-args'));
            } catch (err) {
                console.warn('Bad command args JSON', err);
            }
        }

        if (commandId) {
            e.preventDefault(); // Prevent default link/button (e.g. submit)
            registry.execute(commandId, args);
        }
    });

    // 2. Keyboard Shortcuts (Mock implementation for Ctrl+S)
    document.addEventListener('keydown', (e) => {
        // Ctrl+S / Meta+S
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            registry.execute('file:save');
        }

        // Escape: Close Backstage or Context Menu
        if (e.key === 'Escape') {
            // Check backstage
            const backstage = document.getElementById('office-backstage');
            if (backstage && !backstage.classList.contains('hidden')) {
                registry.execute('file:toggle_backstage');
            }
        }
    });

    // 3. Context Menu Handling
    document.addEventListener('contextmenu', (e) => {
        // Only show if clicking on valid areas (e.g., text, canvas)
        // For MVP, show on .office-canvas or descendant
        if (e.target.closest('.office-canvas')) {
            e.preventDefault();
            const menu = document.getElementById('office-context-menu');
            if (menu) {
                // Position
                menu.style.left = `${e.clientX}px`;
                menu.style.top = `${e.clientY}px`;
                menu.classList.remove('hidden');
                
                // Adjust if out of bounds (basic)
                const rect = menu.getBoundingClientRect();
                if (rect.right > window.innerWidth) menu.style.left = `${window.innerWidth - rect.width - 5}px`;
                if (rect.bottom > window.innerHeight) menu.style.top = `${window.innerHeight - rect.height - 5}px`;
            }
        }
    });

    // 4. Click Anywhere to Close Overlays
    document.addEventListener('click', (e) => {
        // Close Context Menu
        const menu = document.getElementById('office-context-menu');
        if (menu && !menu.classList.contains('hidden') && !e.target.closest('#office-context-menu')) {
            menu.classList.add('hidden');
        }
    });

    // 5. Rich Tooltips (ScreenTips)
    let tooltipTimeout;
    const tooltipEl = document.getElementById('office-tooltip'); // Needs to be added to shell

    document.addEventListener('mouseover', (e) => {
        const target = e.target.closest('[data-screen-tip]');
        if (target && tooltipEl) {
            clearTimeout(tooltipTimeout);
            tooltipTimeout = setTimeout(() => {
                // Populate Tooltip
                const tip = target.getAttribute('data-screen-tip'); // JSON or plain text
                const label = target.getAttribute('title') || 'Comando'; // Fallback
                
                // Simple Parse for now (Label - Desc)
                // In production, data-screen-tip would be a JSON object id
                // Here we assume it's just the description text
                
                const titleEl = tooltipEl.querySelector('.tooltip-title');
                const descEl = tooltipEl.querySelector('.tooltip-desc');
                
                if(titleEl) titleEl.textContent = label.replace(/\(.*\)/, '').trim(); // Remove shortcut from title
                if(descEl) descEl.textContent = tip;

                // Position
                const rect = target.getBoundingClientRect();
                tooltipEl.style.left = `${rect.left}px`;
                tooltipEl.style.top = `${rect.bottom + 8}px`; // Below element
                tooltipEl.classList.remove('hidden');
            }, 600); // Delay like Office
        }
    });

    document.addEventListener('mouseout', (e) => {
        const target = e.target.closest('[data-screen-tip]');
        if (target && tooltipEl) {
            clearTimeout(tooltipTimeout);
            tooltipEl.classList.add('hidden');
        }
    });

    // 6. UI State Updates on Context Change
    document.addEventListener('command:context-changed', (e) => {
        updateCommandStates();
        updateContextualTabs(e.detail.context);
    });

    function updateContextualTabs(ctx) {
        if (!ctx || !ctx.selection) return;

        const type = ctx.selection.type;
        const tabs = document.querySelectorAll('.ribbon-tab.contextual');
        
        // Hide all first (simple toggle) or smart check
        tabs.forEach(tab => {
            const layoutType = tab.getAttribute('data-context-type');
            if (layoutType === type) {
                tab.classList.remove('hidden');
                // Auto-switch to this tab if it just appeared? 
                // Microsoft Office usually focuses it.
                if (!tab.classList.contains('active')) {
                     tab.click(); 
                }
            } else {
                tab.classList.add('hidden');
            }
        });
        
        // Toggle corresponding content
        const tableContent = document.getElementById('tab-content-table');
        const homeContent = document.getElementById('tab-content-home');
        
        if (type === 'table') {
            if(tableContent) tableContent.classList.remove('hidden');
            if(homeContent && tableContent) homeContent.classList.add('hidden');
        } else {
            if(tableContent) tableContent.classList.add('hidden');
            if(homeContent) homeContent.classList.remove('hidden');
             // Switch back to home tab visual if logic dictates, 
             // but for now simple content swap is enough for demo.
        }
    }

    // Initial Interaction to set default state
    updateCommandStates();

    function updateCommandStates() {
        // Find all elements bound to a command
        const boundElements = document.querySelectorAll('[data-command]');
        
        boundElements.forEach(el => {
            const id = el.getAttribute('data-command');
            const state = registry.evaluate(id);

            // Toggle Disabled
            if (!state.enabled) {
                el.classList.add('opacity-50', 'cursor-not-allowed', 'pointer-events-none');
                el.setAttribute('aria-disabled', 'true');
            } else {
                el.classList.remove('opacity-50', 'cursor-not-allowed', 'pointer-events-none');
                el.setAttribute('aria-disabled', 'false');
            }

            // Toggle Visible
            if (!state.visible) {
                 el.classList.add('hidden');
            } else {
                 el.classList.remove('hidden');
            }
        });
    }
});
