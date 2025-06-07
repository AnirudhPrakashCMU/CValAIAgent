// Simple stripe animation using CSS and JS
const stripes = document.getElementById('stripes');
let offset = 0;
function animate() {
  offset = (offset + 2) % 100;
  stripes.style.backgroundPosition = `${offset}px 0`;
  requestAnimationFrame(animate);
}
animate();
