from PIL import Image
import os

# Load walnut PNG
img = Image.open('resources/icons/walnut.png')
print(f'Original walnut size: {img.size}')

# Resize to 128x128 first (smaller than 256x256)
img = img.resize((128, 128), Image.Resampling.LANCZOS)
print(f'Resized to: {img.size}')

# Convert to RGB (not RGBA) to avoid extra data in ICO
if img.mode == 'RGBA':
    background = Image.new('RGB', img.size, (255, 255, 255))
    background.paste(img, mask=img.split()[3])
    img = background

# Save as ICO
img.save('resources/walnut.ico', 'ICO', sizes=[(128, 128)])

size = os.path.getsize('resources/walnut.ico')
print(f'Created walnut.ico: {size} bytes')
