/**
 * Search Provider for "Tell Me"
 * Filters Command Registry and executes commands directly.
 */

document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('tell-me-input');
    const resultsContainer = document.getElementById('tell-me-results');
    const registry = window.CommandRegistry;
    // Mock definitions import if not available globally (In real app, export/import)
    // We assume definitions registered in registry.

    if (!input) return;

    // Create results container if missing
    let dropdown = document.getElementById('search-dropdown');
    if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.id = 'search-dropdown';
        dropdown.className = 'absolute top-full left-0 w-full bg-white shadow-flyout border border-neutral-40 rounded py-1 mt-1 hidden z-50 max-h-60 overflow-y-auto';
        input.parentElement.appendChild(dropdown);
    }

    input.addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        if (query.length < 2) {
            dropdown.classList.add('hidden');
            return;
        }

        // Search logic
        const matches = [];
        registry.commands.forEach((cmd, id) => {
            if (cmd.label && cmd.label.toLowerCase().includes(query)) {
                matches.push(cmd);
            }
        });

        renderResults(matches, dropdown);
    });

    input.addEventListener('focus', () => {
         if (input.value.length >= 2) dropdown.classList.remove('hidden');
    });

    // Hide on click outside
    document.addEventListener('click', (e) => {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.add('hidden');
        }
    });

    function renderResults(results, container) {
        container.innerHTML = '';
        if (results.length === 0) {
            const noRes = document.createElement('div');
            noRes.className = 'px-4 py-2 text-xs text-neutral-60';
            noRes.textContent = 'No se encontraron acciones';
            container.appendChild(noRes);
        } else {
            results.forEach(cmd => {
                const item = document.createElement('button');
                item.className = 'w-full text-left px-4 py-2 text-sm hover:bg-neutral-20 flex items-center gap-3 text-neutral-90';
                item.onclick = () => {
                    registry.execute(cmd.id);
                    input.value = '';
                    container.classList.add('hidden');
                };
                
                // Icon
                if (cmd.icon) {
                    item.innerHTML = `<i class="fas fa-${cmd.icon} w-4 text-center text-neutral-60"></i> <span>${cmd.label}</span>`;
                } else {
                    item.innerHTML = `<span>${cmd.label}</span>`;
                }
                
                container.appendChild(item);
            });
        }
        container.classList.remove('hidden');
    }
});
