/**
 * Draggable Clock Component
 * Allows students to set time by dragging clock hands
 */

class DraggableClock {
  constructor(container, options = {}) {
    this.container = typeof container === 'string'
      ? document.querySelector(container)
      : container;

    this.options = {
      size: options.size || 180,
      interactive: options.interactive !== false,
      showMinuteHand: options.showMinuteHand !== false,
      snapToHour: options.snapToHour || false,
      snapToFiveMinutes: options.snapToFiveMinutes || false,
      initialHour: options.initialHour || 12,
      initialMinute: options.initialMinute || 0,
      onChange: options.onChange || null
    };

    // Track total rotation (can exceed 360) for smooth hour advancement
    const initialHour = this.options.initialHour % 12;
    const initialMinute = this.options.initialMinute;
    this.totalMinuteRotation = (initialHour * 360) + (initialMinute * 6);
    this.minuteAngle = this.minuteToAngle(initialMinute);
    this.hourAngle = this.hourToAngle(this.options.initialHour, initialMinute);
    this.prevDragAngle = null;
    this.dragging = null;

    this.init();
  }

  init() {
    this.render();
    if (this.options.interactive) {
      this.attachEvents();
    }
  }

  render() {
    const size = this.options.size;
    const center = size / 2;
    const radius = center - 5;

    // Create SVG clock
    this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    this.svg.setAttribute('width', size);
    this.svg.setAttribute('height', size);
    this.svg.setAttribute('viewBox', `0 0 ${size} ${size}`);
    this.svg.classList.add('clock-svg');

    // Clock face background
    const face = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    face.setAttribute('cx', center);
    face.setAttribute('cy', center);
    face.setAttribute('r', radius);
    face.classList.add('clock-face-bg');
    this.svg.appendChild(face);

    // Minute marks
    for (let i = 0; i < 60; i++) {
      const angle = (i * 6 - 90) * Math.PI / 180;
      const isMajor = i % 5 === 0;
      const innerR = isMajor ? radius - 15 : radius - 10;
      const outerR = radius - 4;

      const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
      line.setAttribute('x1', center + innerR * Math.cos(angle));
      line.setAttribute('y1', center + innerR * Math.sin(angle));
      line.setAttribute('x2', center + outerR * Math.cos(angle));
      line.setAttribute('y2', center + outerR * Math.sin(angle));
      line.classList.add('clock-tick');
      if (isMajor) line.classList.add('major');
      this.svg.appendChild(line);
    }

    // Numbers
    for (let i = 1; i <= 12; i++) {
      const angle = (i * 30 - 90) * Math.PI / 180;
      const numRadius = radius - 28;

      const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      text.setAttribute('x', center + numRadius * Math.cos(angle));
      text.setAttribute('y', center + numRadius * Math.sin(angle));
      text.classList.add('clock-number-svg');
      text.textContent = i;
      this.svg.appendChild(text);
    }

    // Hour hand (short and thick)
    this.hourHand = this.createHand('hour', center, 40, 10);
    this.svg.appendChild(this.hourHand);

    // Minute hand (long and thin)
    if (this.options.showMinuteHand) {
      this.minuteHand = this.createHand('minute', center, 65, 5);
      this.svg.appendChild(this.minuteHand);
    }

    // Center dot
    const centerDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    centerDot.setAttribute('cx', center);
    centerDot.setAttribute('cy', center);
    centerDot.setAttribute('r', 8);
    centerDot.classList.add('center-dot');
    this.svg.appendChild(centerDot);

    this.container.appendChild(this.svg);
    this.updateHands();
  }

  createHand(type, center, length, width) {
    const hand = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    hand.setAttribute('x', center - width / 2);
    hand.setAttribute('y', center - length);
    hand.setAttribute('width', width);
    hand.setAttribute('height', length);
    hand.setAttribute('rx', width / 2);
    hand.classList.add('hand', type);
    hand.dataset.type = type;
    return hand;
  }

  attachEvents() {
    // Mouse events
    this.svg.addEventListener('mousedown', this.onDragStart.bind(this));
    document.addEventListener('mousemove', this.onDragMove.bind(this));
    document.addEventListener('mouseup', this.onDragEnd.bind(this));

    // Touch events
    this.svg.addEventListener('touchstart', this.onDragStart.bind(this), { passive: false });
    document.addEventListener('touchmove', this.onDragMove.bind(this), { passive: false });
    document.addEventListener('touchend', this.onDragEnd.bind(this));
  }

  onDragStart(e) {
    const target = e.target;
    if (target.classList.contains('hand')) {
      e.preventDefault();
      this.dragging = target.dataset.type;
      target.classList.add('dragging');
    }
  }

  onDragMove(e) {
    if (!this.dragging) return;
    e.preventDefault();

    const rect = this.svg.getBoundingClientRect();
    const center = rect.width / 2;

    let clientX, clientY;
    if (e.touches) {
      clientX = e.touches[0].clientX;
      clientY = e.touches[0].clientY;
    } else {
      clientX = e.clientX;
      clientY = e.clientY;
    }

    const x = clientX - rect.left - center;
    const y = clientY - rect.top - center;
    let angle = Math.atan2(y, x) * 180 / Math.PI + 90;

    if (angle < 0) angle += 360;

    if (this.dragging === 'hour') {
      if (this.options.snapToHour) {
        angle = Math.round(angle / 30) * 30;
      }
      this.hourAngle = angle;
      // Sync totalMinuteRotation when hour is dragged manually
      const hour = Math.round(angle / 30) % 12;
      const currentMinutes = Math.round(this.minuteAngle / 6) % 60;
      this.totalMinuteRotation = (hour * 360) + (currentMinutes * 6);
    } else if (this.dragging === 'minute') {
      // Calculate delta from previous position
      if (this.prevDragAngle !== null) {
        let delta = angle - this.prevDragAngle;

        // Handle wrap-around at 0/360 boundary
        if (delta > 180) delta -= 360;      // Went counter-clockwise across 12
        if (delta < -180) delta += 360;     // Went clockwise across 12

        this.totalMinuteRotation += delta;

        // Keep totalMinuteRotation positive (0 to 4320 = 12 hours)
        if (this.totalMinuteRotation < 0) this.totalMinuteRotation += 4320;
        this.totalMinuteRotation = this.totalMinuteRotation % 4320;
      }
      this.prevDragAngle = angle;

      // Apply snapping to the display angle
      let displayAngle = angle;
      if (this.options.snapToFiveMinutes) {
        displayAngle = Math.round(angle / 30) * 30;
      }
      this.minuteAngle = displayAngle;

      // Hour angle is derived from total rotation (1 hour = 360° of minute hand)
      this.hourAngle = (this.totalMinuteRotation / 12) % 360;
    }

    this.updateHands();
    this.triggerChange();
  }

  onDragEnd() {
    if (this.dragging) {
      const hand = this.svg.querySelector(`.hand.${this.dragging}`);
      if (hand) hand.classList.remove('dragging');
      this.dragging = null;
      this.prevDragAngle = null; // Reset for next drag
    }
  }

  updateHands() {
    const center = this.options.size / 2;

    if (this.hourHand) {
      this.hourHand.setAttribute('transform', `rotate(${this.hourAngle}, ${center}, ${center})`);
    }
    if (this.minuteHand) {
      this.minuteHand.setAttribute('transform', `rotate(${this.minuteAngle}, ${center}, ${center})`);
    }
  }

  // Convert hour (1-12) and minute to angle
  hourToAngle(hour, minute = 0) {
    const h = hour % 12;
    return (h * 30) + (minute / 60 * 30);
  }

  minuteToAngle(minute) {
    return minute * 6;
  }

  // Convert angle to hour (1-12)
  angleToHour(angle) {
    let hour = Math.round(angle / 30) % 12;
    return hour === 0 ? 12 : hour;
  }

  // Convert angle to minute (0-59)
  angleToMinute(angle) {
    return Math.round(angle / 6) % 60;
  }

  // Get current time
  getTime() {
    const hour = this.angleToHour(this.hourAngle);
    const minute = this.options.showMinuteHand ? this.angleToMinute(this.minuteAngle) : 0;
    return { hour, minute };
  }

  // Set time programmatically
  setTime(hour, minute = 0) {
    const h = hour % 12;
    this.totalMinuteRotation = (h * 360) + (minute * 6);
    this.hourAngle = this.hourToAngle(hour, minute);
    this.minuteAngle = this.minuteToAngle(minute);
    this.updateHands();
  }

  // Format time as string
  getTimeString() {
    const { hour, minute } = this.getTime();
    if (minute === 0) {
      return `${hour} o'clock`;
    }
    return `${hour}:${minute.toString().padStart(2, '0')}`;
  }

  triggerChange() {
    if (this.options.onChange) {
      this.options.onChange(this.getTime());
    }
  }

  // Check if time matches target
  checkAnswer(targetHour, targetMinute = 0) {
    const { hour, minute } = this.getTime();
    const hourMatch = hour === targetHour;
    const minuteMatch = !this.options.showMinuteHand || minute === targetMinute;
    return hourMatch && minuteMatch;
  }

  // Add visual feedback
  setFeedback(isCorrect) {
    this.svg.classList.remove('correct', 'incorrect');
    this.svg.classList.add(isCorrect ? 'correct' : 'incorrect');
  }

  // Disable interaction
  disable() {
    this.options.interactive = false;
    this.svg.style.pointerEvents = 'none';
  }

  // Enable interaction
  enable() {
    this.options.interactive = true;
    this.svg.style.pointerEvents = 'auto';
  }
}

/**
 * Clock Display (non-interactive, for showing time)
 */
class ClockDisplay extends DraggableClock {
  constructor(container, hour, minute = 0, options = {}) {
    super(container, {
      ...options,
      interactive: false,
      initialHour: hour,
      initialMinute: minute
    });
  }
}

// Export for use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { DraggableClock, ClockDisplay };
}
