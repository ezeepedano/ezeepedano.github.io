/**
 * Core Command Registry for Propel ERP (Office UI)
 * Handles command registration, execution, and state evaluation (enabled/visible).
 */

class CommandRegistry {
    constructor() {
        this.commands = new Map();
        this.context = {
            selection: { type: 'none', data: null }, // e.g. { type: 'text', data: '...' }
            dirty: false,
            viewMode: 'normal',
            permissions: []
        };
        this.debug = true;
    }

    /**
     * Register a single command or a list of commands
     * @param {Object|Object[]} cmds 
     */
    register(cmds) {
        const list = Array.isArray(cmds) ? cmds : [cmds];
        list.forEach(cmd => {
            if (!cmd.id) {
                console.error('Command missing ID:', cmd);
                return;
            }
            this.commands.set(cmd.id, {
                ...cmd,
                // Default implementations if missing
                isEnabled: cmd.isEnabled || (() => true),
                isVisible: cmd.isVisible || (() => true),
                execute: cmd.execute || (() => console.warn(`Command ${cmd.id} has no execute method`))
            });
            if (this.debug) console.debug(`Registered: ${cmd.id}`);
        });
    }

    get(id) {
        return this.commands.get(id);
    }

    /**
     * Execute a command
     * @param {string} id 
     * @param {Object} payload - Arguments from UI
     */
    async execute(id, payload = {}) {
        const cmd = this.commands.get(id);
        if (!cmd) {
            console.warn(`Command not found: ${id}`);
            return;
        }

        const state = this.evaluate(id);
        if (!state.enabled) {
            console.warn(`Command ${id} is disabled in current context.`);
            return;
        }

        if (this.debug) console.log(`[EXEC] ${id}`, payload, this.context);

        try {
            await cmd.execute(this.context, payload);
        } catch (error) {
            console.error(`Error executing ${id}:`, error);
        }
    }

    /**
     * Evaluate command state against current context
     * @param {string} id 
     * @returns {Object} { enabled: boolean, visible: boolean, checked: boolean }
     */
    evaluate(id) {
        const cmd = this.commands.get(id);
        if (!cmd) return { enabled: false, visible: false };

        return {
            enabled: cmd.isEnabled(this.context),
            visible: cmd.isVisible(this.context),
            checked: cmd.isChecked ? cmd.isChecked(this.context) : false
        };
    }

    /**
     * Update application context and trigger UI refresh
     * @param {Object} newContext Partial context update
     */
    setContext(newContext) {
        this.context = { ...this.context, ...newContext };
        if (this.debug) console.debug('Context updated:', this.context);
        this.notifyContextChange();
    }

    notifyContextChange() {
        // Dispatch event for Bindings to Pick up and re-render UI states
        document.dispatchEvent(new CustomEvent('command:context-changed', { 
            detail: { context: this.context } 
        }));
    }
}

// Singleton
window.CommandRegistry = new CommandRegistry();
