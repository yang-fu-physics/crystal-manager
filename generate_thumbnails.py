import os
import sys
from PIL import Image

# Add current directory to path so we can import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

def generate_thumbnails_for_existing():
    uploads_dir = config.UPLOAD_FOLDER
    if not os.path.exists(uploads_dir):
        print(f"Uploads directory {uploads_dir} does not exist.")
        return

    count = 0
    for root, _, files in os.walk(uploads_dir):
        for file in files:
            # Skip existing thumbnails
            if file.startswith('thumb_'):
                continue
                
            ext = os.path.splitext(file)[1].lower()
            if ext in ['.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff']:
                original_path = os.path.join(root, file)
                thumb_path = os.path.join(root, f"thumb_{file}")
                
                # Check if thumbnail already exists
                if not os.path.exists(thumb_path):
                    try:
                        img = Image.open(original_path)
                        if img.mode in ("RGBA", "P"):
                            img = img.convert("RGB")
                        img.thumbnail((300, 300))
                        img.save(thumb_path)
                        print(f"Generated thumbnail for: {original_path}")
                        count += 1
                    except Exception as e:
                        print(f"Failed to generate thumbnail for {original_path}: {e}")
                        
    print(f"Finished generating {count} missing thumbnails.")

if __name__ == '__main__':
    generate_thumbnails_for_existing()
