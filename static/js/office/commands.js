/**
 * Command Registry for Propel ERP (Office UI)
 * Centralizes all actions, enabling them to be called from Ribbon, Keyboard, Search, etc.
 */

class CommandRegistry {
    constructor() {
        this.commands = new Map();
        this.context = {}; // Global app context
    }

    /**
     * Register a new command
     * @param {Object} command - Command definition
     * @param {string} command.id - Unique ID (e.g., 'file:save')
     * @param {string} command.label - Display name
     * @param {string} command.icon - Icon name/path
     * @param {Function} command.execute - Function to run
     * @param {Function} [command.isEnabled] - Function returning bool
     * @param {Function} [command.isVisible] - Function returning bool
     */
    register(command) {
        if (!command.id || !command.execute) {
            console.error('Invalid command definition:', command);
            return;
        }
        this.commands.set(command.id, command);
        console.debug(`Command registered: ${command.id}`);
    }

    /**
     * Execute a command by ID
     * @param {string} id - Command ID
     * @param {Object} [payload] - Optional data
     */
    execute(id, payload = {}) {
        const cmd = this.commands.get(id);
        if (!cmd) {
            console.warn(`Command not found: ${id}`);
            return;
        }

        // Check if enabled
        if (cmd.isEnabled && !cmd.isEnabled(this.context)) {
            console.warn(`Command is disabled: ${id}`);
            return;
        }

        console.log(`Executing: ${id}`, payload);
        try {
            cmd.execute(this.context, payload);
        } catch (error) {
            console.error(`Error executing ${id}:`, error);
        }
    }

    /**
     * Update global context (e.g. selection change)
     * @param {Object} newContext 
     */
    updateContext(newContext) {
        this.context = { ...this.context, ...newContext };
        // Dispatch event for UI updates if needed
        document.dispatchEvent(new CustomEvent('command:context-changed', { detail: this.context }));
    }

    get(id) {
        return this.commands.get(id);
    }
}

// Global Instance
window.CommandManager = new CommandRegistry();

// Initialize commands
document.addEventListener('DOMContentLoaded', () => {
    const cm = window.CommandManager;

    // --- FILE COMMANDS ---
    cm.register({
        id: 'file:toggle_backstage',
        label: 'Archivo',
        execute: () => {
            const backstage = document.getElementById('office-backstage');
            if(backstage) {
                const isHidden = backstage.classList.contains('hidden');
                if (isHidden) {
                    backstage.classList.remove('hidden');
                    // Focus search or first item
                } else {
                    backstage.classList.add('hidden');
                }
            }
        }
    });

    cm.register({
        id: 'file:save',
        label: 'Guardar',
        icon: 'save',
        execute: () => {
            alert('Guardando documento... (Mock)');
            // Check for active form and submit, or generic save event
        }
    });

    // --- UI COMMANDS ---
    cm.register({
        id: 'ui:toggle_ribbon',
        label: 'Contraer cinta',
        execute: () => {
             const ribbonContent = document.getElementById('ribbon-content');
             if (ribbonContent) {
                 if (ribbonContent.classList.contains('h-28')) {
                        ribbonContent.classList.replace('h-28', 'h-0');
                        ribbonContent.classList.add('opacity-0');
                    } else {
                        ribbonContent.classList.replace('h-0', 'h-28');
                        ribbonContent.classList.remove('opacity-0');
                    }
                    window.dispatchEvent(new Event('resize'));
             }
        }
    });

    // --- EDIT COMMANDS (Mock) ---
    cm.register({
        id: 'edit:copy',
        label: 'Copiar',
        execute: () => console.log('Action: Copy')
    });
    cm.register({
        id: 'edit:paste',
        label: 'Pegar',
        execute: () => console.log('Action: Paste')
    });
    cm.register({
        id: 'edit:cut',
        label: 'Cortar',
        execute: () => console.log('Action: Cut')
    });
    cm.register({
        id: 'edit:format_painter',
        label: 'Copiar formato',
        execute: () => console.log('Action: Format Painter')
    });
});
