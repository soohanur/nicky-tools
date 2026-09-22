/** @type {import('tailwindcss').Config} */
const config = {
  content: ["./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Scraply brand: blue #2196F3 on cream #F2EFE7 (see globals.css tokens)
        blue: {
          50: "#E3F2FD",
          100: "#BBDEFB",
          200: "#90CAF9",
          300: "#64B5F6",
          400: "#42A5F5",
          500: "#2196F3",
          600: "#1E88E5",
          700: "#1976D2",
          800: "#1565C0",
          900: "#0D47A1",
        },
        cream: "#F2EFE7",
        ink: {
          DEFAULT: "#10233b",
          2: "#54627a",
          3: "#94a0b3",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "Segoe UI", "system-ui", "sans-serif"],
      },
      letterSpacing: {
        tightest: "-0.04em",
      },
    },
  },
  plugins: [],
};

export default config;
