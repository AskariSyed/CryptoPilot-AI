/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#070b16",
        panel: "#0d1424",
        line: "#1d2a42",
        cyan: "#52e0d0",
        rose: "#ff718b",
        amber: "#f6c453",
      },
    },
  },
  plugins: [],
};
