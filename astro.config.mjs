import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  site: "https://mrbonzo.com",
  vite: {
    plugins: [tailwindcss()]
  }
});
