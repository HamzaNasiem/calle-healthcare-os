/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Manrope",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "sans-serif",
        ],
      },
      colors: {
        primary: {
          DEFAULT: "#396a00",
          container: "#7dbd42",
          on: "#ffffff",
        },
        surface: {
          DEFAULT: "#f7faf9",
          variant: "#edf1ef",
          container: {
            DEFAULT: "#edf1ef",
            low: "#edf1ef",
            lowest: "#ffffff",
            high: "#e1e6e4",
            highest: "#d5dbd8",
          },
          high: "#e1e6e4",
        },
        "on-surface": {
          DEFAULT: "#181c1c",
          variant: "#3d4946",
        },
        secondary: "#585d77",
        tertiary: "#006493",
        outline: {
          DEFAULT: "#6f7975",
          variant: "#bec9c4",
        },
        sidebar: {
          DEFAULT: "#1a3a2e",
          hover: "#1e4535",
          active: "#7FCD4D",
        },
      },
      boxShadow: {
        card: "0px 10px 30px rgba(24, 28, 28, 0.06)",
        premium: "0px 16px 40px rgba(24, 28, 28, 0.10)",
        sm: "0px 4px 12px rgba(24, 28, 28, 0.04)",
      },
      backgroundImage: {
        "sidebar-gradient": "linear-gradient(180deg, #1e4535 0%, #1a3a2e 50%, #112d22 100%)",
        "primary-gradient": "linear-gradient(135deg, #396a00 0%, #7dbd42 100%)",
        "hero-gradient": "linear-gradient(135deg, #1a3a2e 0%, #1e4535 100%)",
      },
      backdropBlur: {
        glass: "20px",
      },
      letterSpacing: {
        widest2: "0.12em",
      },
    },
  },
  plugins: [],
};
