from PIL import Image
import os

# Load walnut PNG
img = Image.open('resources/icons/walnut.png')
print(f'Original walnut size: {img.size}')

# Resize to 256x256
img = img.resize((256, 256))

# Save as ICO (PIL will optimize for ICO format)
img.save('resources/walnut.ico', 'ICO')

size = os.path.getsize('resources/walnut.ico')
print(f'New walnut.ico size: {size} bytes')
