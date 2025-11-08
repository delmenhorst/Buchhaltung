from PIL import Image
from pathlib import Path
from pillow_heif import register_heif_opener

# Register HEIF/HEIC support for PIL
register_heif_opener()

class ImageConverter:
    """Convert images to PDF"""

    @staticmethod
    def convert_to_pdf(image_path, output_path=None):
        """
        Convert an image file to PDF on A4 paper format (centered)

        Args:
            image_path: Path to the image file
            output_path: Optional output path for PDF. If None, replaces extension with .pdf

        Returns:
            Path to the created PDF file
        """
        image_path = Path(image_path)

        if output_path is None:
            output_path = image_path.with_suffix('.pdf')
        else:
            output_path = Path(output_path)

        # Open image and convert to RGB (PDF doesn't support RGBA)
        image = Image.open(image_path)

        # Convert RGBA to RGB if necessary
        if image.mode == 'RGBA':
            # Create white background
            rgb_image = Image.new('RGB', image.size, (255, 255, 255))
            rgb_image.paste(image, mask=image.split()[3])  # Use alpha channel as mask
            image = rgb_image
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        # A4 size at 300 DPI: 2480 x 3508 pixels
        a4_width, a4_height = 2480, 3508

        # Create A4-sized white canvas
        a4_canvas = Image.new('RGB', (a4_width, a4_height), (255, 255, 255))

        # Calculate scaling to fit image within A4 with margins (50px margin on each side)
        margin = 100
        max_width = a4_width - (2 * margin)
        max_height = a4_height - (2 * margin)

        # Calculate scale factor to fit image within A4
        scale_w = max_width / image.width
        scale_h = max_height / image.height
        scale = min(scale_w, scale_h, 1.0)  # Don't upscale, only downscale if needed

        # Resize image if needed
        if scale < 1.0:
            new_width = int(image.width * scale)
            new_height = int(image.height * scale)
            image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Calculate position to center image on A4 canvas
        x = (a4_width - image.width) // 2
        y = (a4_height - image.height) // 2

        # Paste image onto A4 canvas
        a4_canvas.paste(image, (x, y))

        # Save as PDF with A4 dimensions
        a4_canvas.save(output_path, 'PDF', resolution=300.0)

        return output_path

    @staticmethod
    def is_image(file_path):
        """Check if file is an image"""
        return Path(file_path).suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
