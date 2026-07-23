/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        canvas: '#ffffff',
        'surface-soft': '#f1f4f7',
        'ink-deep': '#0a1317',
        ink: '#1c1e21',
        charcoal: '#444950',
        slate: '#4b4c4f',
        steel: '#5d6c7b',
        stone: '#8595a4',
        hairline: '#ced0d4',
        'hairline-soft': '#dee3e9',
        primary: '#0064e0',
        'primary-deep': '#0457cb',
        'primary-soft': '#0091ff',
        success: '#31a24c',
        attention: '#f2a918',
        warning: '#f7b928',
        critical: '#e41e3f',
        'critical-strong': '#f0284a',
      },
      borderRadius: {
        xs: '2px',
        sm: '4px',
        md: '6px',
        lg: '8px',
        xl: '16px',
        xxl: '24px',
        xxxl: '32px',
        full: '100px',
      },
    },
  },
  plugins: [],
}
