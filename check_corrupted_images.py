import os
import argparse
from pathlib import Path
try:
    from PIL import Image
    from PIL import UnidentifiedImageError
except ImportError:
    print("Please install Pillow first using: pip install Pillow")
    exit(1)

# List of common image extensions to check
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}

def check_image(file_path):
    try:
        # First pass: verify without decoding the image data
        with Image.open(file_path) as img:
            img.verify()
        
        # Second pass: actually load the image data to catch deeper corruptions
        with Image.open(file_path) as img:
            img.load()
            
        return True, None
    except UnidentifiedImageError:
        return False, "Cannot identify image file"
    except Exception as e:
        return False, str(e)

def find_corrupted_images(directory, check_all_files=False):
    corrupted_files = []
    
    directory_path = Path(directory)
    if not directory_path.exists():
        print(f"Error: Directory '{directory}' does not exist.")
        return []

    print(f"Scanning '{directory}' for corrupted images...")
    
    count = 0

    for root, _, files in os.walk(directory):
        for file in files:
            file_path = Path(root) / file
            
            # Skip non-image files unless --all is specified
            if not check_all_files and file_path.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            
            count += 1
            is_valid, error_msg = check_image(file_path)
            
            if not is_valid:
                print(f"[Corrupted] {file_path} - Reason: {error_msg}")
                corrupted_files.append(str(file_path))
                
    print(f"\nFinished! Scanned {count} images in total.")
    return corrupted_files

def main():
    parser = argparse.ArgumentParser(description="Find corrupted images in a directory and save them to a file.")
    parser.add_argument(
        "directory", 
        nargs="?", 
        default=".", 
        help="Directory to scan (default: current directory)"
    )
    parser.add_argument(
        "-o", "--output", 
        default="corrupted_images_report.txt", 
        help="Output text file to save the list (default: corrupted_images_report.txt)"
    )
    parser.add_argument(
        "--all", 
        action="store_true", 
        help="Check all files, not just those with common image extensions (.jpg, .png, etc.)"
    )
    
    args = parser.parse_args()
    
    corrupted_images = find_corrupted_images(args.directory, args.all)
    
    if corrupted_images:
        print(f"Found {len(corrupted_images)} corrupted images.")
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                for file_path in corrupted_images:
                    f.write(file_path + "\n")
            print(f"Saved the list of corrupted images to: {args.output}")
        except Exception as e:
            print(f"Error saving to {args.output}: {e}")
    else:
        print("No corrupted images found.")

if __name__ == "__main__":
    main()
