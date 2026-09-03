module.exports = {
  content: ['./src/ui/index.html', './src/ui/assets/app.js'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#ecfdf5',
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
        },
        fluent: {
          app: '#0A0D14',
          sidebar: '#0D111A',
          card: '#131824',
          cardHover: '#182030',
          accent: '#22C55E',
          accentLight: '#4ADE80',
        }
      },
      animation: {
        'pulse-fast': 'pulse 1.2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
      }
    }
  }
};
