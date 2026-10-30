# Application logo

The application mark is the project owner's supplied trophy and four-point
sparkle, adapted to the existing charcoal-and-blue interface with the built-in
imagegen editor. The design remains a trophy with its original handle openings,
rim notch, stem and pedestal. The palette direction is a light-blue trophy,
soft-white sparkle and charcoal background.

- Approved raster master: `assets/logo-master.png`.
- PNG for documentation: `assets/app.png` (256 × 256).
- Windows icon: `assets/app.ico` (16, 24, 32, 48, 64, 128 and 256 pixels).

The header reads the same Windows icon used by the application and installer.
To regenerate the exported sizes from the committed master, without any image
generation service or API key:

```powershell
python tools/build_assets.py
```

## Final edit prompt

Built-in imagegen mode; supplied logo as the edit target; opaque output.

Edit the provided logo by changing its COLORS ONLY, preserving the exact trophy-plus-four-point-sparkle silhouette and all original geometry. Make a polished flat icon for Achievement Desk's dark header. Replace the nearly black background with a perfectly flat solid charcoal #242426 across the entire square image. Replace the gold trophy with a perfectly flat solid light blue #93C5FF. Replace the gold sparkle above it with a perfectly flat soft white #F5F5F7. Preserve the source's exact trophy handles, cup rim V notch, stem, pedestal and single four-point sparkle. Do not add white outlines or any stroke. No shading, gradients, lighting, texture, speckles, halos, white fringes, added shapes, shadows, rounded tile or text. The entire background including the handle openings and negative space must be exactly the same charcoal color. Extract the central symbol only: the footer at the bottom is outside the logo and is not included. Enlarge and center that unchanged symbol on the square canvas with approximately 8% clear padding above and below. Crisp smooth vector-like antialiasing. Opaque image, no transparency.
