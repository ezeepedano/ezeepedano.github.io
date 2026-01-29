/**
 * Command Definitions
 * Single source of truth for command metadata and logic.
 */

(function() {
    const registry = window.CommandRegistry;

    const commands = [
        // --- NAVIGATION ---
        {
            id: 'nav:goto',
            execute: (ctx, args) => {
                if (args && args.url) {
                    window.location.href = args.url;
                } else {
                    console.warn('nav:goto called without URL', args);
                }
            }
        },
        
        // --- FILE OPERATIONS ---
        {
            id: 'file:toggle_backstage',
            label: 'Archivo',
            description: 'Abre el menú Archivo (Backstage).',
            icon: 'fa-th', 
            execute: (ctx) => {
                const backstage = document.getElementById('office-backstage');
                if (backstage) {
                    const isHidden = backstage.classList.contains('hidden');
                    if (isHidden) {
                        backstage.classList.remove('hidden');
                        // Focus trap logic would go here
                    } else {
                        backstage.classList.add('hidden');
                    }
                }
            }
        },
        {
            id: 'file:save',
            label: 'Guardar',
            description: 'Guardar el documento actual (Ctrl+G).',
            icon: 'save',
            shortcut: 'Ctrl+S',
            execute: (ctx) => {
                // Check if current page has a save form?
                // For MVP, if there is a form #main-form, submit it.
                const form = document.querySelector('form[method="post"]') || document.getElementById('main-form');
                if (form) {
                    form.submit();
                } else {
                    alert('No hay formulario activo para guardar.');
                }
            }
        },

        // --- EDITING ---
        {
            id: 'edit:undo',
            label: 'Deshacer',
            icon: 'undo',
            execute: () => window.history.back() // Simple browser undo for nav
        },
        {
            id: 'edit:redo',
            label: 'Rehacer',
            icon: 'redo',
            execute: () => window.history.forward()
        },
        
        // --- HELPERS ---
        {
            id: 'app:print',
            label: 'Imprimir',
            icon: 'print',
            execute: () => window.print()
        }
    ];

    registry.register(commands);
})();
