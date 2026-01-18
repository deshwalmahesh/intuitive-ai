/**
 * popup.js - Modal popup system for term definitions
 * Handles displaying and managing popup content
 */

const Popup = {
    // DOM elements
    overlay: null,
    modal: null,
    title: null,
    body: null,
    closeBtn: null,
    
    // Popup data
    popupData: {},

    /**
     * Initialize popup system
     * @param {Object} popups - Popup definitions from JSON
     */
    init(popups) {
        this.popupData = popups || {};
        
        // Get DOM elements
        this.overlay = document.getElementById('modal-overlay');
        this.modal = document.getElementById('modal');
        this.title = document.getElementById('modal-title');
        this.body = document.getElementById('modal-body');
        this.closeBtn = document.getElementById('modal-close');
        
        // Setup event listeners
        this.setupEventListeners();
    },

    /**
     * Setup event listeners for popup interactions
     */
    setupEventListeners() {
        // Close button
        this.closeBtn?.addEventListener('click', () => this.close());
        
        // Click outside to close
        this.overlay?.addEventListener('click', (e) => {
            if (e.target === this.overlay) this.close();
        });
        
        // Escape key to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.close();
        });
        
        // Prevent modal content clicks from closing
        this.modal?.addEventListener('click', (e) => e.stopPropagation());
    },

    /**
     * Show popup for a given term key
     * @param {string} key - The popup key to display
     */
    show(key) {
        const data = this.popupData[key];
        if (!data) {
            console.warn(`No popup data for key: ${key}`);
            return;
        }
        
        // Set title with color
        this.title.textContent = data.title;
        this.title.style.color = data.color;
        
        // Build body content
        let bodyHTML = '';
        for (const section of data.sections || []) {
            bodyHTML += this.renderSection(section);
        }
        
        this.body.innerHTML = bodyHTML;
        
        // Show modal
        this.overlay.classList.add('active');
        
        // Style example sections
        this.body.querySelectorAll('.modal-section').forEach(section => {
            const titleEl = section.querySelector('.modal-section-title');
            if (titleEl && titleEl.textContent.includes('Example')) {
                const content = section.querySelector('.modal-section-content');
                if (content && !content.querySelector('.code-block') && !content.querySelector('.insight-box')) {
                    content.classList.add('modal-example');
                }
            }
        });
        
        // Bind click handlers for terms inside popup
        this.bindTermHandlers();
    },

    /**
     * Render a popup section
     * @param {Object} section - Section definition
     * @returns {string} - HTML string
     */
    renderSection(section) {
        // Handle divider type
        if (section.type === 'divider') {
            return `
                <div class="modal-section">
                    <div class="modal-section-content">
                        <div style="text-align: center; color: #94a3b8; font-size: 14px;">━━━━━━ Scientific Definition ━━━━━━</div>
                    </div>
                </div>
            `;
        }
        
        // Handle equation display
        if (section.type === 'equation-display') {
            return `
                <div class="modal-section">
                    <div class="modal-section-content">
                        <div class="popup-equation">${Renderer.parseTerms(section.content)}</div>
                    </div>
                </div>
            `;
        }
        
        // Standard section
        const icon = section.icon || '';
        const title = section.title || '';
        const content = Renderer.parseTerms(section.content || '');
        const formula = section.formula ? 
            `<div class="modal-formula">${Renderer.parseTerms(section.formula)}</div>` : '';
        
        return `
            <div class="modal-section">
                <div class="modal-section-title">${icon} ${title}</div>
                <div class="modal-section-content">
                    ${content}
                    ${formula}
                </div>
            </div>
        `;
    },

    /**
     * Bind click handlers for terms inside popup content
     * This enables nested popups (clicking term inside a popup)
     */
    bindTermHandlers() {
        this.body.querySelectorAll('[data-popup]').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                this.show(el.dataset.popup);
            });
        });
    },

    /**
     * Close the popup
     */
    close() {
        this.overlay?.classList.remove('active');
    },

    /**
     * Bind popup handlers to all terms in the document
     * Should be called after rendering content
     */
    bindAllTermHandlers() {
        document.querySelectorAll('[data-popup]').forEach(el => {
            // Remove existing to avoid duplicates
            el.removeEventListener('click', this.handleTermClick);
            el.addEventListener('click', this.handleTermClick.bind(this));
        });
    },

    /**
     * Handle term click
     * @param {Event} e - Click event
     */
    handleTermClick(e) {
        e.stopPropagation();
        const key = e.currentTarget.dataset.popup;
        this.show(key);
    }
};

// Export for use in other scripts
window.Popup = Popup;
