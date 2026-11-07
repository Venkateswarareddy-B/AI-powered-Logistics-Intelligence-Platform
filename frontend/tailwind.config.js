/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        navy: {
          950: '#0B1530',
          900: '#0f1729',
          800: '#152238',
          700: '#1a2d4a',
          600: '#1e3a5f',
        },
        brand: {
          50: '#EAF2FF',
          100: '#dbeafe',
          200: '#bfdbfe',
          500: '#2563EB',
          600: '#1d4ed8',
          700: '#1e40af',
        },
        ink: {
          900: '#172033',
          700: '#334155',
          500: '#64748B',
          300: '#cbd5e1',
        },
        surface: '#F4F7FF',
        card: '#FFFFFF',
        purple: { 500: '#8B5CF6', 600: '#7c3aed' },
        emerald: { 500: '#10B981', 600: '#059669' },
        amber: { 500: '#F59E0B', 600: '#d97706' },
        rose: { 500: '#F43F5E', 600: '#e11d48' },
        sky: { 500: '#0ea5e9', 600: '#0284c7' },
      },
      borderRadius: {
        'xl2': '20px',
      },
      boxShadow: {
        'soft': '0 1px 3px 0 rgb(0 0 0 / 0.04), 0 1px 2px 0 rgb(0 0 0 / 0.02)',
        'card': '0 2px 8px -2px rgb(0 0 0 / 0.06), 0 4px 12px -4px rgb(0 0 0 / 0.04)',
        'card-hover': '0 8px 24px -4px rgb(37 99 235 / 0.12), 0 4px 12px -2px rgb(0 0 0 / 0.06)',
        'sidebar': '4px 0 24px -4px rgb(0 0 0 / 0.08)',
      },
    }
  },
  plugins: []
}
