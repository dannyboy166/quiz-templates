/**
 * Quiz Color Cycling Utility
 * Cycles through 4 background colors on each "next question" action
 * Color persists across page navigation via sessionStorage
 */

const QUIZ_COLORS = [
  '#FFE280',              // Yellow
  'rgb(209, 253, 145)',   // Light Green
  'rgb(243, 178, 221)',   // Pink
  'rgb(178, 235, 242)'    // Cyan
];

/**
 * Initialize color cycling on page load
 * Sets the background to the current saved color index
 */
function initColorCycle() {
  // Add smooth transition for background color changes
  document.body.style.transition = 'background-color 0.5s ease';

  // Also apply to quiz-container if it exists
  const quizContainer = document.querySelector('.quiz-container');
  if (quizContainer) {
    quizContainer.style.transition = 'background-color 0.5s ease';
  }

  // Get saved index or start at 0
  const index = parseInt(sessionStorage.getItem('quizColorIndex') || '0');
  setQuizColor(index);
}

/**
 * Cycle to the next color
 * Call this when moving to the next question
 */
function cycleColor() {
  let index = parseInt(sessionStorage.getItem('quizColorIndex') || '0');
  index = (index + 1) % QUIZ_COLORS.length;
  sessionStorage.setItem('quizColorIndex', index.toString());
  setQuizColor(index);
}

/**
 * Set the background color by index
 */
function setQuizColor(index) {
  const color = QUIZ_COLORS[index];
  document.body.style.backgroundColor = color;

  // Also update quiz-container if it exists (some templates use this)
  const quizContainer = document.querySelector('.quiz-container');
  if (quizContainer) {
    quizContainer.style.backgroundColor = color;
  }
}

/**
 * Reset color index to 0 (optional - for testing or restart)
 */
function resetColorCycle() {
  sessionStorage.setItem('quizColorIndex', '0');
  setQuizColor(0);
}
