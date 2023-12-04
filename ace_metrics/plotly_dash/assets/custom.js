// Helper function to determine the plot element and toggle drag mode
function toggleDragMode(plotElement, key) {
    if (key === 'z') {
        var currentMode = plotElement.layout.dragmode;
        Plotly.relayout(plotElement, { 'dragmode': currentMode === 'pan' ? 'zoom' : 'pan' });
    }
}

// Helper function to reset axes to auto-range
function resetAxes(plotElement, key) {
    if (key === 'x') {
        var update = {};
        Object.keys(plotElement._fullLayout).forEach((axis) => {
            if (axis.includes('xaxis') || axis.includes('yaxis')) {
                update[axis + '.autorange'] = true;
            }
        });
        Plotly.relayout(plotElement, update);
    }
}

// Add shortcut keys for charts: 'z' to switch between zoom/pan, 'x' to reset both axes
function keydownToggle(event) {
    // Only proceed if the plot element is currently being hovered over
    var plotElement = document.querySelector('.js-plotly-plot:hover');
    if (plotElement) {
        toggleDragMode(plotElement, event.key);
        resetAxes(plotElement, event.key);
    }
}

// Add keydown event listener to document
document.addEventListener('keydown', keydownToggle);

// IIFE to check and update fill based on theme
(function checkAndUpdateFill() {
    var rects = document.querySelectorAll('.updatemenu-item-rect');
    var theme = document.documentElement.getAttribute('data-bs-theme');
    var fillColor = theme === 'dark' ? 'rgba(255, 255, 255, 0.5)' : 'rgba(200, 200, 200, 0.9)';

    rects.forEach(function (rect) {
        if (rect.style.fill === 'rgb(244, 250, 255)') {
            rect.style.fill = fillColor;
        }
    });

    requestAnimationFrame(checkAndUpdateFill);
})();