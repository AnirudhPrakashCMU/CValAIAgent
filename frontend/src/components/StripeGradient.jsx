import { useEffect } from 'react';

export default function StripeGradient() {
  useEffect(() => {
    const script = document.createElement('script');
    script.src = 'https://unpkg.com/gradient-canvas/dist/gradient-canvas.min.js';
    script.onload = () => {
      if (window.Gradient) {
        const gradient = new window.Gradient();
        gradient.initGradient('#gradient-canvas');
      }
    };
    document.body.appendChild(script);
    return () => {
      if (script.parentNode) script.parentNode.removeChild(script);
    };
  }, []);

  return (
    <div className="w-full h-64 relative mt-8">
      <canvas id="gradient-canvas" className="absolute inset-0 w-full h-full" />
      <h1 className="absolute top-0 left-0 w-full text-center text-4xl font-bold mix-blend-difference text-gray-800 p-8">
        Stripe Gradient Animation
      </h1>
    </div>
  );
}
