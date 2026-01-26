from PIL import Image
import os

# Create small ico files from PNG sources
icons = [
    ('resources/icons/banana.png', 'resources/banana.ico'),
    ('resources/icons/walnut.png', 'resources/walnut.ico'),
    ('resources/icons/coyote.png', 'resources/coyote.ico'),
    ('resources/icons/favicon.png', 'resources/favicon.ico'),
]

for png_path, ico_path in icons:
    try:
        img = Image.open(png_path)
        print(f'{png_path}: original size {img.size}')
        
        # Resize to 64x64 (small enough to avoid issues, large enough for clarity)
        img = img.resize((64, 64), Image.Resampling.LANCZOS)
        
        # Convert RGBA to RGB if needed
        if img.mode == 'RGBA':
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background
        
        # Save as ICO
        img.save(ico_path, 'ICO')
        size = os.path.getsize(ico_path)
        print(f'  → {ico_path}: {size} bytes')
    except Exception as e:
        print(f'Error processing {png_path}: {e}')

print('\nDone!')
