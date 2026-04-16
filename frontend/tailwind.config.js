/** @type {import('tailwindcss').Config} */
export default {
    content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
    theme: {
        extend: {
            colors: {
                customer: {
                    primary: '#35d47a',
                    dark: '#27B966',
                    light: '#BCFFD9s',
                    bg: '#eeeeee',
                    shadow: '#b1b1b1',
                    card: '#ffffff',
                    active: 'scale-105'
                },
                staff: {
                    primary: '#F97316',
                    dark: '#C2410C',
                    light: '#ecc18f',
                    bg: '#FFFBF5',
                    card: '#FFF8F0',
                }
            }
        }
    },
    plugins: [],
}
