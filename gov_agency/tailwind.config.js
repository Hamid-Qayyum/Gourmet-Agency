/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
 // 1. Scans a root-level 'templates' folder (if you have one).
    './templates/**/*.html',

    // 2. Scans for 'templates' folders inside ANY app. This is the most important one.
    './**/templates/**/*.html',

    // 3. Scans for JavaScript files for dynamic classes (e.g., from AlpineJS or Stimulus).
    './**/static/**/*.js',

    // 4. Scans your forms.py files for any CSS classes added to widgets.
    './**/forms.py',

    // 5. Scans your views.py files (useful if you ever generate HTML snippets in a view).
    './**/views.py',

    // 6. Scans your admin.py files (less common, but good for completeness).
    './**/admin.py',  ],
  theme: {
    extend: {},
  },
  plugins: [
      require('daisyui'), // Activate the DaisyUI plugin
  ],
  daisyui: {
    themes: ["light", "dark"], // Specify the themes you want to use
  },
}