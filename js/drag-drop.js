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

    // Tap-to-select mode for mobile
    this.selectedItem = null;
    this.isTapMode = false;
    this.touchStartTime = 0;
    this.touchStartPos = { x: 0, y: 0 };

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

      // Tap-to-place for mobile
      zone.addEventListener('click', this.onZoneTap.bind(this));
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

  // ==================== Touch Events (Mobile) - Tap to Select ====================

  onTouchStart(e) {
    const item = e.target.closest(this.options.itemSelector);
    if (!item) return;

    // Record touch start for tap detection
    this.touchStartTime = Date.now();
    const touch = e.touches[0];
    this.touchStartPos = { x: touch.clientX, y: touch.clientY };
    this.isTapMode = true;

    // Don't prevent default - allow scrolling
  }

  onTouchMove(e) {
    if (!this.isTapMode) return;

    // If moved more than 10px, it's a scroll not a tap
    const touch = e.touches[0];
    const dx = Math.abs(touch.clientX - this.touchStartPos.x);
    const dy = Math.abs(touch.clientY - this.touchStartPos.y);

    if (dx > 10 || dy > 10) {
      this.isTapMode = false; // Cancel tap, allow scroll
    }
  }

  onTouchEnd(e) {
    const item = e.target.closest(this.options.itemSelector);
    if (!item) return;

    // Check if it was a tap (quick, no movement)
    const tapDuration = Date.now() - this.touchStartTime;

    if (this.isTapMode && tapDuration < 300) {
      e.preventDefault();
      this.toggleItemSelection(item);
    }

    this.isTapMode = false;
  }

  toggleItemSelection(item) {
    // If already selected, deselect
    if (this.selectedItem === item) {
      this.selectedItem.classList.remove('selected');
      this.selectedItem = null;
      this.showSelectionHint(false);
      return;
    }

    // Deselect previous
    if (this.selectedItem) {
      this.selectedItem.classList.remove('selected');
    }

    // Select new item
    this.selectedItem = item;
    item.classList.add('selected');
    this.showSelectionHint(true);

    // Highlight all zones as potential targets
    this.zones.forEach(z => z.classList.add('tap-target'));
  }

  onZoneTap(e) {
    if (!this.selectedItem) return;

    const zone = e.target.closest(this.options.zoneSelector);
    if (!zone) return;

    // Place selected item in this zone
    this.placeItemInZone(this.selectedItem, zone);

    // Clear selection
    this.selectedItem.classList.remove('selected');
    this.selectedItem = null;
    this.showSelectionHint(false);
    this.zones.forEach(z => z.classList.remove('tap-target'));
  }

  placeItemInZone(item, zone) {
    const itemsContainer = zone.querySelector('.drop-zone-items') || zone;
    itemsContainer.appendChild(item);
    item.classList.add('placed');
    item.classList.add('just-dropped');

    // Random position within jar
    const randomX = Math.random() * 40;
    const randomY = Math.random() * 60;
    const randomRotate = (Math.random() - 0.5) * 30;
    item.style.left = randomX + 'px';
    item.style.top = randomY + 'px';
    item.style.transform = `scale(0.7) rotate(${randomRotate}deg)`;

    // Record placement
    const itemId = item.dataset.id;
    const zoneId = zone.dataset.zone;
    this.placements[itemId] = zoneId;

    if (this.options.onDrop) {
      this.options.onDrop(itemId, zoneId, item, zone);
    }

    // Remove animation class
    setTimeout(() => {
      item.classList.remove('just-dropped');
    }, 300);

    this.checkComplete();
  }

  showSelectionHint(show) {
    // Show/hide a hint banner for tap mode
    let hint = document.getElementById('tap-mode-hint');

    if (show && !hint) {
      hint = document.createElement('div');
      hint.id = 'tap-mode-hint';
      hint.innerHTML = 'Tap a jar to place the item';
      hint.style.cssText = `
        position: fixed;
        bottom: 100px;
        left: 50%;
        transform: translateX(-50%);
        background: #333;
        color: white;
        padding: 12px 24px;
        border-radius: 25px;
        font-size: 16px;
        font-weight: 600;
        z-index: 1000;
        animation: fadeInUp 0.3s ease;
      `;
      document.body.appendChild(hint);
    } else if (!show && hint) {
      hint.remove();
    }
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
