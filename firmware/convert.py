import os
import sys
import re
from PIL import Image

def png_to_h_format(input_path, output_path=None):
    # Determine output path if not explicitly provided
    if not output_path:
        name, _ = os.path.splitext(input_path)
        output_path = name + ".h"

    base_name = os.path.basename(input_path)
    name_no_ext, _ = os.path.splitext(base_name)

    # Sanitize filename into a valid C variable name
    var_name = re.sub(r'[^a-zA-Z0-9_]', '_', name_no_ext)

    try:
        img = Image.open(input_path)
    except Exception as e:
        print(f"Error opening image: {e}")
        sys.exit(1)

    # Handle images with Alpha (transparency) by pasting over a white background
    if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
        bg = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        bg.paste(img, mask=img.convert('RGBA').split()[3])
        img = bg

    # Convert to grayscale 
    img = img.convert('L')
    width, height = img.size

    # 1 bit per pixel (monochrome), padded to the nearest full byte per line
    bytes_per_row = (width + 7) // 8
    total_bytes = bytes_per_row * height

    # Convert pixel data to bits
    data = []
    for y in range(height):
        for x_byte in range(bytes_per_row):
            byte_val = 0
            for bit in range(8):
                x = x_byte * 8 + bit
                if x < width:
                    pixel = img.getpixel((x, y))
                    # Threshold for white/black. White mapping to 1, Black to 0
                    if pixel > 127: 
                        byte_val |= (1 << (7 - bit)) # Set bit (MSB first)
            data.append(byte_val)

    # Create the metadata comment block
    # Little-endian formatting for standard e-paper format configs 
    w_lsb = width & 0xFF
    w_msb = (width >> 8) & 0xFF
    h_lsb = height & 0xFF
    h_msb = (height >> 8) & 0xFF

    header_comment = f"/* 0X00,0X01,0X{w_lsb:02X},0X{w_msb:02X},0X{h_lsb:02X},0X{h_msb:02X}, */"

    # Write out the formatted .h file
    try:
        with open(output_path, "w") as f:
            f.write(f"uint8_t gImage_{var_name}[{total_bytes}] = {{ {header_comment}\n")

            # Batch by 16 values per line (as in the example)
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                line = ",".join(f"0X{b:02X}" for b in chunk)
                f.write(line + ",\n")

            f.write("};\n")
    except Exception as e:
        print(f"Error writing to file: {e}")
        sys.exit(1)

    print(f"Success! Image converted and saved to '{output_path}'")
    print(f" > Dimensions: {width} x {height}")
    print(f" > Array Size: {total_bytes} bytes")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python img2h.py <image.png> [output.h]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    png_to_h_format(input_file, output_file)