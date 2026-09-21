/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef2fb",
          100: "#dbe4f5",
          200: "#b9c9ea",
          300: "#8fa7db",
          400: "#6380c7",
          500: "#415da8",
          600: "#33497f",
          700: "#29395f",
          800: "#1e2a45",
          900: "#141d30",
          950: "#0c1322",
        },
        attention: {
          high: "#b42318",
          medium: "#b54708",
          low: "#067647",
        },
        ink: "#0f172a",
        paper: "#f8fafc",
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.05), 0 1px 3px 0 rgb(15 23 42 / 0.08)",
        lift: "0 6px 20px -6px rgb(15 23 42 / 0.18)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
      },
      animation: {
        "fade-up": "fade-up 0.4s ease-out both",
        "fade-in": "fade-in 0.3s ease-out both",
      },
    },
  },
  plugins: [],
};