/**
 * renderer.js - JSON to HTML rendering engine
 * Converts topic JSON data into HTML components
 */

const Renderer = {
    // Store loaded topic data
    topicData: null,
    colorPalette: {},
    terms: {},
    popups: {},
    sharedDefinitions: null,

    /**
     * Load shared definitions from centralized file
     * This is the SINGLE SOURCE OF TRUTH for all common definitions
     * @returns {Object} - Shared definitions (colorPalette, terms, popups)
     */
    async loadSharedDefinitions() {
        if (this.sharedDefinitions) {
            return this.sharedDefinitions;
        }
        
        const response = await fetch('definitions/shared.json');
        if (!response.ok) {
            throw new Error('Failed to load shared definitions: ' + response.statusText);
        }
        this.sharedDefinitions = await response.json();
        return this.sharedDefinitions;
    },

    /**
     * Initialize renderer with topic data
     * Merges shared definitions with topic-specific definitions
     * Topic definitions OVERRIDE shared (for customization flexibility)
     * @param {Object} data - The parsed JSON topic data
     * @param {Object} shared - Shared definitions (optional, for when already loaded)
     */
    init(data, shared = null) {
        this.topicData = data;
        
        // Merge: shared first, then topic overrides
        const sharedDefs = shared || this.sharedDefinitions || { colorPalette: {}, terms: {}, popups: {} };
        
        this.colorPalette = { ...sharedDefs.colorPalette, ...(data.colorPalette || {}) };
        this.terms = { ...sharedDefs.terms, ...(data.terms || {}) };
        this.popups = { ...sharedDefs.popups, ...(data.popups || {}) };
        
        // Generate CSS color classes dynamically
        this.injectColorStyles();
    },

    /**
     * Generate and inject CSS for color classes
     */
    injectColorStyles() {
        let css = '';
        for (const [key, color] of Object.entries(this.colorPalette)) {
            css += `.c-${key} { color: ${color}; }\n`;
        }
        
        const style = document.createElement('style');
        style.id = 'dynamic-colors';
        style.textContent = css;
        
        // Remove existing if present
        const existing = document.getElementById('dynamic-colors');
        if (existing) existing.remove();
        
        document.head.appendChild(style);
    },

    /**
     * Parse term syntax {term:key:display} and render as clickable span
     * @param {string} text - Text containing term syntax
     * @returns {string} - HTML with rendered terms
     */
    parseTerms(text) {
        if (!text) return '';
        
        // Match {term:key:display} pattern
        const termRegex = /\{term:([^:}]+):([^}]+)\}/g;
        
        return text.replace(termRegex, (match, key, display) => {
            const termData = this.terms[key];
            const colorKey = termData?.colorKey || key;
            const popupKey = termData?.popupKey || key;
            
            return `<span class="term c-${colorKey}" data-popup="${popupKey}">${display}</span>`;
        });
    },

    /**
     * Render a single slide
     * @param {Object} slideData - Slide definition from JSON
     * @returns {HTMLElement} - Rendered slide element
     */
    renderSlide(slideData) {
        const slide = document.createElement('div');
        slide.className = 'slide';
        slide.id = slideData.id;
        slide.dataset.section = slideData.sectionIndex;
        
        const card = document.createElement('div');
        card.className = 'slide-card';
        if (slideData.customClass) card.classList.add(slideData.customClass);
        if (slideData.customStyle) card.style.cssText = slideData.customStyle;
        
        // Title (hidden in nav bar, but still in DOM for navigation to read)
        const title = document.createElement('div');
        title.className = 'slide-card-title';
        title.textContent = slideData.title;
        card.appendChild(title);
        
        // Content area
        const content = document.createElement('div');
        content.className = 'slide-card-content';
        
        // Render each content block
        for (const block of slideData.content || []) {
            const rendered = this.renderContentBlock(block);
            if (rendered) content.appendChild(rendered);
        }
        
        card.appendChild(content);
        slide.appendChild(card);
        
        return slide;
    },

    /**
     * Render a content block based on its type
     * @param {Object} block - Content block definition
     * @returns {HTMLElement|null} - Rendered element
     */
    renderContentBlock(block) {
        switch (block.type) {
            case 'html':
                return this.renderHTML(block);
            case 'image':
                return this.renderImage(block);
            case 'table':
                return this.renderTable(block);
            case 'insight-box':
                return this.renderInsightBox(block);
            case 'equation':
                return this.renderEquation(block);
            case 'term-grid':
                return this.renderTermGrid(block);
            default:
                console.warn(`Unknown block type: ${block.type}`);
                return null;
        }
    },

    /**
     * Render raw HTML content (with term parsing)
     */
    renderHTML(block) {
        const div = document.createElement('div');
        div.innerHTML = this.parseTerms(block.content);
        if (block.customClass) div.className = block.customClass;
        if (block.customStyle) div.style.cssText = block.customStyle;
        return div;
    },

    /**
     * Render an image
     */
    renderImage(block) {
        const img = document.createElement('img');
        img.src = block.src;
        img.alt = block.alt || '';
        img.className = 'slide-image';
        if (block.style) img.style.cssText = block.style;
        return img;
    },

    /**
     * Render a table
     */
    renderTable(block) {
        const wrapper = document.createElement('div');
        wrapper.className = 'table-wrapper';
        
        const table = document.createElement('table');
        table.className = block.class || 'uncertainty-table';
        
        // Header row
        if (block.headers) {
            const headerRow = document.createElement('tr');
            for (const header of block.headers) {
                const th = document.createElement('th');
                th.innerHTML = this.parseTerms(header);
                headerRow.appendChild(th);
            }
            table.appendChild(headerRow);
        }
        
        // Data rows
        for (const row of block.rows || []) {
            const tr = document.createElement('tr');
            for (const cell of row) {
                const td = document.createElement('td');
                td.innerHTML = this.parseTerms(cell);
                tr.appendChild(td);
            }
            table.appendChild(tr);
        }
        
        wrapper.appendChild(table);
        return wrapper;
    },

    /**
     * Render an insight box
     */
    renderInsightBox(block) {
        const box = document.createElement('div');
        box.className = 'insight-box';
        if (block.style) box.style.cssText = block.style;
        
        if (block.title) {
            const title = document.createElement('div');
            title.className = 'insight-title';
            title.innerHTML = this.parseTerms(block.title);
            box.appendChild(title);
        }
        
        if (block.content) {
            const content = document.createElement('p');
            content.innerHTML = this.parseTerms(block.content);
            box.appendChild(content);
        }
        
        return box;
    },

    /**
     * Render an equation with labeled parts
     */
    renderEquation(block) {
        const container = document.createElement('div');
        
        // Label/heading
        if (block.label) {
            const label = document.createElement('h3');
            label.style.marginTop = '20px';
            label.style.marginBottom = '10px';
            label.innerHTML = this.parseTerms(block.label);
            container.appendChild(label);
        }
        
        const box = document.createElement('div');
        box.className = 'equation-box';
        
        const equation = document.createElement('div');
        equation.className = 'equation';
        
        // Render equation parts
        for (const part of block.parts || []) {
            const rendered = this.renderEquationPart(part);
            if (rendered) equation.appendChild(rendered);
        }
        
        box.appendChild(equation);
        
        // Explanation
        if (block.explanation) {
            const explain = document.createElement('div');
            explain.className = 'eq-explain';
            explain.innerHTML = (block.explanation.prefix || '') + 
                this.parseTerms(block.explanation.template);
            box.appendChild(explain);
        }
        
        container.appendChild(box);
        return container;
    },

    /**
     * Render a single equation part
     */
    renderEquationPart(part) {
        switch (part.type) {
            case 'term':
                const term = document.createElement('span');
                term.className = `eq-part`;
                term.innerHTML = `<span class="term c-${this.terms[part.key]?.colorKey || part.key}" data-popup="${this.terms[part.key]?.popupKey || part.key}">${part.text}</span>`;
                return term;
                
            case 'operator':
                const op = document.createElement('span');
                op.className = 'eq-symbol';
                op.textContent = part.symbol;
                return op;
                
            case 'raw':
                const raw = document.createElement('span');
                raw.textContent = part.text;
                return raw;
                
            case 'subscript':
                const sub = document.createElement('sub');
                for (const subPart of part.content || []) {
                    const rendered = this.renderEquationPart(subPart);
                    if (rendered) sub.appendChild(rendered);
                }
                return sub;
                
            case 'labeled-expression':
                const label = document.createElement('div');
                label.className = 'eq-label';
                label.dataset.popup = part.popupKey;
                
                const expr = document.createElement('span');
                expr.className = `eq-part eq-underline-${part.underline || 'blue'}`;
                
                for (const exprPart of part.content || []) {
                    const rendered = this.renderEquationPart(exprPart);
                    if (rendered) expr.appendChild(rendered);
                }
                
                label.appendChild(expr);
                
                // Arrow and label text
                const arrow = document.createElement('span');
                arrow.className = `eq-label-arrow c-${part.labelColor}`;
                arrow.textContent = '↑';
                label.appendChild(arrow);
                
                const labelText = document.createElement('span');
                labelText.className = `eq-label-text c-${part.labelColor}`;
                labelText.textContent = part.label;
                label.appendChild(labelText);
                
                return label;
                
            default:
                return null;
        }
    },

    /**
     * Render a grid of all terms as clickable colored boxes
     * Used for glossary/dictionary view
     */
    renderTermGrid(block) {
        const container = document.createElement('div');
        container.className = 'term-grid-container';
        if (block.columns) {
            container.style.gridTemplateColumns = `repeat(${block.columns}, 1fr)`;
        }

        // Get all terms that have popup definitions
        const termEntries = [];
        for (const [key, termData] of Object.entries(this.terms)) {
            // Only include terms that have popup definitions
            const popupKey = termData.popupKey || key;
            if (this.popups[popupKey]) {
                termEntries.push({
                    key: key,
                    display: termData.display,
                    colorKey: termData.colorKey || key,
                    popupKey: popupKey,
                    popupTitle: this.popups[popupKey].title || termData.display
                });
            }
        }

        // Sort alphabetically by popup title (the full name)
        termEntries.sort((a, b) => a.popupTitle.localeCompare(b.popupTitle));

        // Render each term as a colored box
        for (const term of termEntries) {
            const box = document.createElement('div');
            box.className = 'term-grid-box';
            box.dataset.popup = term.popupKey;

            const color = this.colorPalette[term.colorKey] || '#667eea';
            box.style.borderColor = color;
            box.style.setProperty('--term-color', color);

            // Symbol/display
            const symbol = document.createElement('span');
            symbol.className = 'term-grid-symbol';
            symbol.style.color = color;
            symbol.textContent = term.display;
            box.appendChild(symbol);

            // Title (from popup)
            const title = document.createElement('span');
            title.className = 'term-grid-title';
            title.textContent = term.popupTitle.replace(/^[^-]+ - /, ''); // Remove symbol prefix if present
            box.appendChild(title);

            container.appendChild(box);
        }

        return container;
    },

    /**
     * Render all slides into the container
     * @param {HTMLElement} container - Container element to render into
     */
    renderAllSlides(container) {
        container.innerHTML = '';
        
        for (const slide of this.topicData.slides || []) {
            const rendered = this.renderSlide(slide);
            container.appendChild(rendered);
        }
    }
};

// Export for use in other scripts
window.Renderer = Renderer;
