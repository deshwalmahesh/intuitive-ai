/**
 * navigation.js - Slide navigation system
 * Handles section pills, slide navigation, and keyboard controls
 */

const Navigation = {
    // Configuration from JSON
    config: { sections: [] },
    
    // Current state
    currentSectionIndex: 0,
    currentSlideIndex: 0,

    /**
     * Initialize navigation with config
     * @param {Object} navConfig - Navigation config from JSON
     */
    init(navConfig) {
        this.config = navConfig || { sections: [] };
        this.currentSectionIndex = 0;
        this.currentSlideIndex = 0;
        
        // Generate section pills
        this.generatePills();
        
        // Setup button handlers
        this.setupButtons();
        
        // Setup keyboard navigation
        this.setupKeyboard();
        
        // Show first slide
        this.goToSlide(0, 0);
    },

    /**
     * Generate section pill buttons
     */
    generatePills() {
        const container = document.getElementById('section-pills');
        if (!container) return;
        
        container.innerHTML = this.config.sections.map((section, index) => `
            <div class="section-pill ${index === 0 ? 'active' : 'inactive'}" 
                 data-section="${index}">
                ${section.title}
            </div>
        `).join('');
        
        // Bind click handlers
        container.querySelectorAll('.section-pill').forEach((pill, index) => {
            pill.addEventListener('click', () => this.goToSection(index));
        });
    },

    /**
     * Setup navigation button handlers
     */
    setupButtons() {
        const prevBtn = document.getElementById('prev-slide-btn');
        const nextBtn = document.getElementById('next-slide-btn');
        
        prevBtn?.addEventListener('click', () => this.prevSlide());
        nextBtn?.addEventListener('click', () => this.nextSlide());
    },

    /**
     * Setup keyboard navigation
     */
    setupKeyboard() {
        document.addEventListener('keydown', (e) => {
            // Don't navigate if modal is open
            const modal = document.getElementById('modal-overlay');
            if (modal?.classList.contains('active')) return;
            
            switch (e.key) {
                case 'ArrowRight':
                case ' ':
                    e.preventDefault();
                    this.nextSlide();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    this.prevSlide();
                    break;
                case 'ArrowDown':
                    e.preventDefault();
                    this.nextSection();
                    break;
                case 'ArrowUp':
                    e.preventDefault();
                    this.prevSection();
                    break;
            }
        });
    },

    /**
     * Navigate to a specific slide
     * @param {number} sectionIndex 
     * @param {number} slideIndex 
     */
    goToSlide(sectionIndex, slideIndex) {
        // Hide all slides
        document.querySelectorAll('.slide').forEach(slide => {
            slide.classList.remove('active');
        });
        
        // Update state
        this.currentSectionIndex = sectionIndex;
        this.currentSlideIndex = slideIndex;
        
        // Get target slide
        const section = this.config.sections[sectionIndex];
        if (!section) return;
        
        const slideId = section.slides[slideIndex];
        const slideElement = document.getElementById(slideId);
        
        if (slideElement) {
            slideElement.classList.add('active');
        }
        
        // Scroll content area to top
        const contentArea = document.getElementById('slide-content-area');
        if (contentArea) contentArea.scrollTop = 0;
        
        // Update UI
        this.updateUI();
        
        // Rebind popup handlers
        Popup.bindAllTermHandlers();
    },

    /**
     * Navigate to a section (first slide)
     * @param {number} sectionIndex 
     */
    goToSection(sectionIndex) {
        if (sectionIndex >= 0 && sectionIndex < this.config.sections.length) {
            this.goToSlide(sectionIndex, 0);
        }
    },

    /**
     * Go to next slide
     */
    nextSlide() {
        const section = this.config.sections[this.currentSectionIndex];
        
        if (this.currentSlideIndex < section.slides.length - 1) {
            // More slides in current section
            this.goToSlide(this.currentSectionIndex, this.currentSlideIndex + 1);
        } else if (this.currentSectionIndex < this.config.sections.length - 1) {
            // Go to next section
            this.goToSlide(this.currentSectionIndex + 1, 0);
        }
    },

    /**
     * Go to previous slide
     */
    prevSlide() {
        if (this.currentSlideIndex > 0) {
            // Previous slide in current section
            this.goToSlide(this.currentSectionIndex, this.currentSlideIndex - 1);
        } else if (this.currentSectionIndex > 0) {
            // Last slide of previous section
            const prevSection = this.config.sections[this.currentSectionIndex - 1];
            this.goToSlide(this.currentSectionIndex - 1, prevSection.slides.length - 1);
        }
    },

    /**
     * Go to next section
     */
    nextSection() {
        if (this.currentSectionIndex < this.config.sections.length - 1) {
            this.goToSlide(this.currentSectionIndex + 1, 0);
        }
    },

    /**
     * Go to previous section
     */
    prevSection() {
        if (this.currentSectionIndex > 0) {
            this.goToSlide(this.currentSectionIndex - 1, 0);
        }
    },

    /**
     * Update navigation UI elements
     */
    updateUI() {
        const section = this.config.sections[this.currentSectionIndex];
        if (!section) return;
        
        const slideId = section.slides[this.currentSlideIndex];
        const slideElement = document.getElementById(slideId);
        
        // Update title
        const slideTitle = slideElement?.querySelector('.slide-card-title')?.textContent 
            || slideElement?.querySelector('h2')?.textContent 
            || section.title;
        
        const titleEl = document.getElementById('section-title');
        if (titleEl) titleEl.textContent = slideTitle;
        
        // Update counter
        const counterEl = document.getElementById('slide-counter');
        if (counterEl) {
            counterEl.textContent = `${this.currentSlideIndex + 1} / ${section.slides.length}`;
        }
        
        // Update pills
        document.querySelectorAll('.section-pill').forEach((pill, index) => {
            pill.classList.remove('active', 'inactive');
            pill.classList.add(index === this.currentSectionIndex ? 'active' : 'inactive');
        });
        
        // Scroll active pill into view
        this.scrollActivePill();
        
        // Update button states
        this.updateButtons();
    },

    /**
     * Scroll active pill to center
     */
    scrollActivePill() {
        const container = document.getElementById('section-pills');
        const activePill = container?.querySelector('.section-pill.active');
        
        if (activePill && container) {
            const scrollLeft = activePill.offsetLeft - (container.offsetWidth / 2) + (activePill.offsetWidth / 2);
            container.scrollTo({ left: Math.max(0, scrollLeft), behavior: 'smooth' });
        }
    },

    /**
     * Update button disabled states
     */
    updateButtons() {
        const prevBtn = document.getElementById('prev-slide-btn');
        const nextBtn = document.getElementById('next-slide-btn');
        const section = this.config.sections[this.currentSectionIndex];
        
        // Disable prev if first slide of first section
        if (prevBtn) {
            prevBtn.disabled = (this.currentSectionIndex === 0 && this.currentSlideIndex === 0);
        }
        
        // Disable next if last slide of last section
        if (nextBtn && section) {
            const isLastSection = this.currentSectionIndex === this.config.sections.length - 1;
            const isLastSlide = this.currentSlideIndex === section.slides.length - 1;
            nextBtn.disabled = (isLastSection && isLastSlide);
        }
    }
};

// Export for use in other scripts
window.Navigation = Navigation;
