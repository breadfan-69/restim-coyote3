from PIL import Image
import os

# Open cherries.ico
cherries = Image.open('resources/cherries.ico')
print(f"Original cherries mode: {cherries.mode}, size: {cherries.size}")

# Get size
size = cherries.size

# Convert cherries to RGBA to access alpha channel
cherries_rgba = cherries.convert('RGBA')

# Get the pixel data
pixels = cherries_rgba.load()
width, height = size

# Create NEW image starting with pure white background (RGB - no alpha)
favicon = Image.new('RGB', size, (255, 255, 255))
favicon_pixels = favicon.load()

# Copy pixels from cherries, blending with white background using alpha
for y in range(height):
    for x in range(width):
        r, g, b, a = cherries_rgba.getpixel((x, y))
        # Blend with white using alpha
        alpha = a / 255.0
        new_r = int(r * alpha + 255 * (1 - alpha))
        new_g = int(g * alpha + 255 * (1 - alpha))
        new_b = int(b * alpha + 255 * (1 - alpha))
        favicon_pixels[x, y] = (new_r, new_g, new_b)

# Verify mode is RGB (no alpha)
print(f"Created favicon mode: {favicon.mode}, has alpha: {'A' in favicon.mode}")

# Save as favicon.ico
favicon.save('resources/favicon.ico', 'ICO')
print('Created favicon.ico with fully opaque white background (manually blended)')

# Verify saved file
test = Image.open('resources/favicon.ico')
print(f"Saved favicon mode: {test.mode}, has alpha: {'A' in test.mode}")
