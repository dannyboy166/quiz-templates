# Image corruption after WebP conversion — diagnosis for Victor

**Date:** 8 Sep 2026
**Symptom:** After the image library was converted to WebP (this morning), some question
images render broken in the student portal:
- Some show as a **solid black rectangle**.
- Some show as a **white silhouette on a black background** (subject outline only, all detail gone).
- Images that were fully opaque to begin with (full illustrations) render **fine**.

Examples seen: PDHPE questions — ItemID **141001** ("Why do we wash our hands?") and
**141004** ("How long should we brush our teeth?") — both show the white-silhouette artifact.

## MOST LIKELY root cause: the "fake SVGs" (PNG embedded inside an SVG) didn't convert

~85% of the old library were **"fake SVGs"**: a full-resolution PNG base64-embedded inside an SVG
wrapper (the Canva export format, ~2 MB each). A WebP converter does **not** render an SVG unless it
has a proper SVG rasterizer that also decodes the embedded base64 PNG. If Victor's conversion ran a
straight image→WebP on these files:
- it likely rendered only the SVG's **structure/mask/clip-path** (not the embedded photo) → the
  **white silhouette** or **black box**, OR
- rasterized onto a transparent canvas and flattened alpha to black (below).

**The images that render fine are the REAL images (not fake-SVG-wrapped).** The broken ones are the
SVG-wrapped-PNG ones. This is the same fake-SVG liability that motivated bypassing Canva
(see docs — image approve now pushes real WebP directly). Best fix: re-convert from the **real
underlying image** (the OpenAI PNG / Airtable original), not the SVG wrapper.

## Secondary mechanism: transparency (alpha channel) mishandled during conversion

The affected images had a **transparent background** (alpha channel). The conversion dropped or
misused the alpha. Reproduced both failure modes locally with Pillow:

- **Black rectangle** = image converted RGBA → RGB **without compositing onto a background**, so
  every transparent pixel became black `(0,0,0)`.
- **White silhouette on black** = the **alpha channel itself was saved as the image** (or the image
  was multiplied by alpha with no color), so the opaque subject becomes white and the transparent
  area becomes black.

Opaque images (no transparency) are unaffected — which is exactly why the full illustrations look
fine and only the transparent-background ones broke.

## The fix (conversion side)

When converting to WebP, either:
1. **Preserve alpha** — WebP fully supports RGBA. Keep the image in RGBA and save as WebP
   (`im.save(out, "WEBP", quality=85)` with the RGBA image intact). This is what our app's
   `png_to_webp` does and it round-trips transparency correctly. **Recommended** (matches how the
   images were designed — transparent bg so they sit on the question's coloured card).
2. **Or composite onto a known background first** — if flattening is desired, paste the RGBA image
   onto an explicit background (e.g. white) *before* converting to RGB, so transparent areas become
   that colour instead of black:
   `bg = Image.new("RGB", im.size, (255,255,255)); bg.paste(im, mask=im.split()[-1])`.

**Do NOT** `im.convert("RGB")` directly on a transparent image (→ black), and **do not** save the
alpha channel as the image (→ white silhouette).

## Verification snippet (what we used to confirm)
```python
from PIL import Image, ImageDraw
im = Image.new("RGBA",(200,200),(0,0,0,0)); ImageDraw.Draw(im).ellipse((50,50,150,150),fill=(200,120,60,255))
im.convert("RGB").save("bugA.webp","WEBP")          # transparent -> BLACK
im.split()[-1].convert("RGB").save("bugB.webp","WEBP")  # alpha-as-image -> WHITE silhouette on black
im.save("correct.webp","WEBP")                        # RGBA preserved -> correct
```

## Scope to re-convert
Only images that had transparency are affected (the SVG-origin / transparent-bg ones). The originals
still exist (Airtable library / source), so a re-conversion preserving alpha fixes it — no content lost.
