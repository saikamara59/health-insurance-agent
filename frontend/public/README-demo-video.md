# Demo video for the landing page

The home page (`src/pages/HomePage.jsx`, section **05 — See it in action**) renders a
video player whose source is `/product-demo.mp4` (this folder, served at the site root).

## Swapping the clip

1. Export as **MP4 (H.264)** — plays in every browser. HEVC/H.265 `.mov` (the default
   for macOS screen recordings) only plays in Safari, so convert it first, e.g.:

   ```sh
   ffmpeg -i input.mov -c:v libx264 -crf 20 -preset medium -pix_fmt yuv420p \
     -movflags +faststart -an frontend/public/product-demo.mp4
   ```

2. Save it here as exactly **`product-demo.mp4`** (or update the `<source>` in HomePage.jsx).

## Gotcha — don't name it `healthflow-*.mp4`

`vite.config.js` proxies the `/health` path prefix to the backend, and Vite matches
proxy rules by prefix. A file named `healthflow-demo.mp4` is requested at
`/healthflow-demo.mp4`, which **starts with `/health`** → Vite forwards it to the
backend → 404, and the video silently fails to load. Keep the name free of that
prefix (`product-demo.mp4` is fine).

## Notes

- The `<video>` is `preload="none"`, so visitors fetch zero video bytes until they
  click play. Until a file is present, a click-to-play placeholder shows.
- The file is committed and deployed inside the built image, so don't add `*.mp4`
  to `.gitignore` if you want it live on healthflow.work.
