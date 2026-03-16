/**
 * Drag and Drop Component
 * For sorting, categorizing, and matching questions
 */

class DragDropZone {
  constructor(container, options = {}) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container;

    this.options = {
      itemSelector: options.itemSelector || '.draggable-item',
      zoneSelector: options.zoneSelector || '.drop-zone',
      sourceSelector: options.sourceSelector || '.draggable-items',
      allowReorder: options.allowReorder !== false,
      allowRemove: options.allowRemove !== false,
      snapBack: options.snapBack !== false,
      onDrop: options.onDrop || null,
      onComplete: options.onComplete || null,
      correctAnswers: options.correctAnswers || {}
    };

    this.items = [];
    this.zones = [];
    this.source = null;
    this.draggedItem = null;
    this.draggedClone = null;
    this.placements = {};

    this.init();
  }

  init() {
    this.items = Array.from(this.container.querySelectorAll(this.options.itemSelector));
    this.zones = Array.from(this.container.querySelectorAll(this.options.zoneSelector));
    this.source = this.container.querySelector(this.options.sourceSelector);

    this.attachEvents();
  }

  attachEvents() {
    // Item events
    this.items.forEach(item => {
      item.setAttribute('draggable', 'true');

      // Mouse events
      item.addEventListener('dragstart', this.onDragStart.bind(this));
      item.addEventListener('dragend', this.onDragEnd.bind(this));

      // Touch events for mobile
      item.addEventListener('touchstart', this.onTouchStart.bind(this), { passive: false });
      item.addEventListener('touchmove', this.onTouchMove.bind(this), { passive: false });
      item.addEventListener('touchend', this.onTouchEnd.bind(this));
    });

    // Zone events
    this.zones.forEach(zone => {
      zone.addEventListener('dragover', this.onDragOver.bind(this));
      zone.addEventListener('dragleave', this.onDragLeave.bind(this));
      zone.addEventListener('drop', this.onDrop.bind(this));
    });

    // Source area events (for removing items)
    if (this.source && this.options.allowRemove) {
      this.source.addEventListener('dragover', this.onDragOver.bind(this));
      this.source.addEventListener('drop', this.onDropToSource.bind(this));
    }
  }

  // ==================== Mouse Drag Events ====================

  onDragStart(e) {
    this.draggedItem = e.target.closest(this.options.itemSelector);
    if (!this.draggedItem) return;

    this.draggedItem.classList.add('dragging');
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', this.draggedItem.dataset.id || '');

    // Slight delay for visual feedback
    setTimeout(() => {
      this.draggedItem.style.opacity = '0.5';
    }, 0);
  }

  onDragEnd(e) {
    if (this.draggedItem) {
      this.draggedItem.classList.remove('dragging');
      this.draggedItem.style.opacity = '1';
      this.draggedItem = null;
    }

    // Remove all hover states
    this.zones.forEach(zone => zone.classList.remove('drag-over'));
  }

  onDragOver(e) {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';

    const zone = e.target.closest(this.options.zoneSelector) ||
                 e.target.closest(this.options.sourceSelector);
    if (zone) {
      zone.classList.add('drag-over');
    }
  }

  onDragLeave(e) {
    const zone = e.target.closest(this.options.zoneSelector);
    if (zone && !zone.contains(e.relatedTarget)) {
      zone.classList.remove('drag-over');
    }
  }

  onDrop(e) {
    e.preventDefault();
    const zone = e.target.closest(this.options.zoneSelector);
    if (!zone || !this.draggedItem) return;

    zone.classList.remove('drag-over');

    // Move item to zone
    const itemsContainer = zone.querySelector('.drop-zone-items') || zone;
    itemsContainer.appendChild(this.draggedItem);
    this.draggedItem.classList.add('placed');
    this.draggedItem.classList.add('just-dropped');

    // Random position within jar
    const randomX = Math.random() * 40;
    const randomY = Math.random() * 60;
    const randomRotate = (Math.random() - 0.5) * 30;
    this.draggedItem.style.left = randomX + 'px';
    this.draggedItem.style.top = randomY + 'px';
    this.draggedItem.style.transform = `scale(0.7) rotate(${randomRotate}deg)`;

    // Record placement
    const itemId = this.draggedItem.dataset.id;
    const zoneId = zone.dataset.zone;
    this.placements[itemId] = zoneId;

    // Trigger callback
    if (this.options.onDrop) {
      this.options.onDrop(itemId, zoneId, this.draggedItem, zone);
    }

    // Remove animation class
    setTimeout(() => {
      this.draggedItem.classList.remove('just-dropped');
    }, 300);

    // Check if all items placed
    this.checkComplete();
  }

  onDropToSource(e) {
    e.preventDefault();
    if (!this.draggedItem) return;

    this.source.classList.remove('drag-over');
    this.source.appendChild(this.draggedItem);
    this.draggedItem.classList.remove('placed');
    this.draggedItem.style.left = '';
    this.draggedItem.style.top = '';
    this.draggedItem.style.transform = '';

    // Remove from placements
    const itemId = this.draggedItem.dataset.id;
    delete this.placements[itemId];
  }

  // ==================== Touch Events (Mobile) ====================

  onTouchStart(e) {
    const item = e.target.closest(this.options.itemSelector);
    if (!item) return;

    e.preventDefault();
    this.draggedItem = item;
    this.draggedItem.classList.add('dragging');

    // Create clone for dragging visual
    const rect = item.getBoundingClientRect();
    this.draggedClone = item.cloneNode(true);
    this.draggedClone.classList.add('drag-ghost');
    this.draggedClone.style.width = rect.width + 'px';
    this.draggedClone.style.height = rect.height + 'px';
    document.body.appendChild(this.draggedClone);

    // Position clone
    const touch = e.touches[0];
    this.updateClonePosition(touch.clientX, touch.clientY);

    // Dim original
    this.draggedItem.style.opacity = '0.3';
  }

  onTouchMove(e) {
    if (!this.draggedItem || !this.draggedClone) return;
    e.preventDefault();

    const touch = e.touches[0];
    this.updateClonePosition(touch.clientX, touch.clientY);

    // Check which zone we're over
    const elemBelow = document.elementFromPoint(touch.clientX, touch.clientY);
    const zone = elemBelow?.closest(this.options.zoneSelector);

    // Update hover states
    this.zones.forEach(z => z.classList.remove('drag-over'));
    if (zone) {
      zone.classList.add('drag-over');
    }
  }

  onTouchEnd(e) {
    if (!this.draggedItem) return;

    // Find zone at drop position
    const touch = e.changedTouches[0];
    const elemBelow = document.elementFromPoint(touch.clientX, touch.clientY);
    const zone = elemBelow?.closest(this.options.zoneSelector);

    if (zone) {
      // Move item to zone
      const itemsContainer = zone.querySelector('.drop-zone-items') || zone;
      itemsContainer.appendChild(this.draggedItem);
      this.draggedItem.classList.add('placed');

      // Random position within jar
      const randomX = Math.random() * 40;
      const randomY = Math.random() * 60;
      const randomRotate = (Math.random() - 0.5) * 30;
      this.draggedItem.style.left = randomX + 'px';
      this.draggedItem.style.top = randomY + 'px';
      this.draggedItem.style.transform = `scale(0.7) rotate(${randomRotate}deg)`;

      // Record placement
      const itemId = this.draggedItem.dataset.id;
      const zoneId = zone.dataset.zone;
      this.placements[itemId] = zoneId;

      if (this.options.onDrop) {
        this.options.onDrop(itemId, zoneId, this.draggedItem, zone);
      }

      this.checkComplete();
    }

    // Cleanup
    this.draggedItem.classList.remove('dragging');
    this.draggedItem.style.opacity = '1';

    if (this.draggedClone) {
      this.draggedClone.remove();
      this.draggedClone = null;
    }

    this.zones.forEach(z => z.classList.remove('drag-over'));
    this.draggedItem = null;
  }

  updateClonePosition(x, y) {
    if (this.draggedClone) {
      this.draggedClone.style.left = (x - 30) + 'px';
      this.draggedClone.style.top = (y - 30) + 'px';
    }
  }

  // ==================== Validation ====================

  checkComplete() {
    const allPlaced = this.items.every(item => {
      const id = item.dataset.id;
      return this.placements[id] !== undefined;
    });

    if (allPlaced && this.options.onComplete) {
      this.options.onComplete(this.placements);
    }
  }

  checkAnswers() {
    const results = {};
    let allCorrect = true;

    this.items.forEach(item => {
      const itemId = item.dataset.id;
      const placedZone = this.placements[itemId];
      const correctZone = this.options.correctAnswers[itemId];
      const isCorrect = placedZone === correctZone;

      results[itemId] = {
        placed: placedZone,
        correct: correctZone,
        isCorrect
      };

      // Visual feedback
      item.classList.remove('correct', 'incorrect');
      if (placedZone) {
        item.classList.add(isCorrect ? 'correct' : 'incorrect');
      }

      if (!isCorrect) allCorrect = false;
    });

    return { results, allCorrect };
  }

  // Get current state
  getState() {
    return { ...this.placements };
  }

  // Reset all items to source
  reset() {
    this.items.forEach(item => {
      this.source.appendChild(item);
      item.classList.remove('placed', 'correct', 'incorrect');
      item.style.left = '';
      item.style.top = '';
      item.style.transform = '';
    });
    this.placements = {};
  }

  // Disable interaction
  disable() {
    this.items.forEach(item => {
      item.setAttribute('draggable', 'false');
      item.style.cursor = 'default';
    });
  }

  // Enable interaction
  enable() {
    this.items.forEach(item => {
      item.setAttribute('draggable', 'true');
      item.style.cursor = 'grab';
    });
  }
}

// ==================== Shape SVGs ====================

const ShapeSVGs = {
  triangle: `<svg viewBox="0 0 60 60"><polygon points="30,5 55,55 5,55"/></svg>`,
  square: `<svg viewBox="0 0 60 60"><rect x="5" y="5" width="50" height="50"/></svg>`,
  rectangle: `<svg viewBox="0 0 60 60"><rect x="5" y="15" width="50" height="30"/></svg>`,
  pentagon: `<svg viewBox="0 0 60 60"><polygon points="30,5 55,25 45,55 15,55 5,25"/></svg>`,
  hexagon: `<svg viewBox="0 0 60 60"><polygon points="30,5 52,17 52,43 30,55 8,43 8,17"/></svg>`,
  diamond: `<svg viewBox="0 0 60 60"><polygon points="30,5 55,30 30,55 5,30"/></svg>`,
  trapezoid: `<svg viewBox="0 0 60 60"><polygon points="15,15 45,15 55,45 5,45"/></svg>`,
  parallelogram: `<svg viewBox="0 0 60 60"><polygon points="15,15 55,15 45,45 5,45"/></svg>`,
  circle: `<svg viewBox="0 0 60 60"><circle cx="30" cy="30" r="25" fill="none" stroke-width="3"/></svg>`,
  oval: `<svg viewBox="0 0 60 60"><ellipse cx="30" cy="30" rx="25" ry="15" fill="none" stroke-width="3"/></svg>`
};

// Helper to create shape element
function createShapeItem(shapeType, id) {
  const div = document.createElement('div');
  div.className = 'draggable-item shape-item';
  div.dataset.id = id || shapeType;
  div.innerHTML = ShapeSVGs[shapeType] || ShapeSVGs.square;
  return div;
}

// Export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { DragDropZone, ShapeSVGs, createShapeItem };
}
