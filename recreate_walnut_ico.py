from PIL import Image
import os

# Load walnut PNG (should already have transparency)
img = Image.open('resources/icons/walnut.png')
print(f'Walnut PNG: mode={img.mode}, size={img.size}')

# Resize to 64x64
img = img.resize((64, 64), Image.Resampling.LANCZOS)

# Save as ICO preserving any transparency/alpha
img.save('resources/walnut.ico', 'ICO')

size = os.path.getsize('resources/walnut.ico')
print(f'Created walnut.ico: {size} bytes')
