#!/usr/bin/env python3
import subprocess
import time

builds = [
    ('banana', 'restim-banana.spec'),
    ('walnut', 'restim-walnut.spec'),
    ('coyote', 'restim-coyote.spec'),
]

# Read the original settings file
with open('qt_ui/settings.py', 'r') as f:
    original_settings = f.read()

for icon_name, spec_file in builds:
    print(f"\n{'='*60}")
    print(f"Building {icon_name} version...")
    print(f"{'='*60}")
    
    # Modify settings.py to use this icon as default
    modified_settings = original_settings.replace(
        "icon_theme = Setting('theme/icon_theme', 'favicon', str)",
        f"icon_theme = Setting('theme/icon_theme', '{icon_name}', str)"
    )
    
    with open('qt_ui/settings.py', 'w') as f:
        f.write(modified_settings)
    
    # Build
    subprocess.run(
        ['.\\venv\\Scripts\\python.exe', '-m', 'PyInstaller', spec_file, '--noconfirm'],
        check=False
    )
    
    print(f"Build {icon_name} complete!")
    time.sleep(5)

# Restore original settings
print(f"\n{'='*60}")
print("Restoring original settings...")
print(f"{'='*60}")
with open('qt_ui/settings.py', 'w') as f:
    f.write(original_settings)

print("\nAll builds complete!")
