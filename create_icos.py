#!/usr/bin/env python3
from PIL import Image
import os

# Create ico files from PNG icons
for icon_name in ['banana', 'walnut', 'coyote', 'cherries', 'favicon']:
    png_path = f'resources/icons/{icon_name}.png'
    ico_path = f'resources/{icon_name}.ico'
    
    if os.path.exists(png_path):
        img = Image.open(png_path).convert('RGBA')
        img_resized = img.resize((256, 256), Image.Resampling.LANCZOS)
        img_resized.save(ico_path, 'ICO')
        print(f'Created {ico_path}')
    else:
        print(f'Error: {png_path} not found')

# Create non-transparent (opaque) version of favicon for Windows app icon
favicon_png = 'resources/icons/favicon.png'
if os.path.exists(favicon_png):
    # Create white background
    background = Image.new('RGB', (256, 256), (255, 255, 255))
    img = Image.open(favicon_png).convert('RGBA')
    img_resized = img.resize((256, 256), Image.Resampling.LANCZOS)
    # Composite the icon onto the white background
    background.paste(img_resized, (0, 0), img_resized)
    background.save('resources/favicon-opaque.ico', 'ICO')
    print('Created resources/favicon-opaque.ico')
else:
    print(f'Error: {favicon_png} not found')
