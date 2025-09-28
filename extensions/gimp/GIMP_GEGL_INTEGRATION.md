# GIMP 3 GEGL Integration

This document describes the GIMP 3 GEGL (Generic Graphics Library) integration for advanced image processing operations.

## Overview

The GIMP GEGL integration provides access to professional-grade image processing operations through GIMP's powerful GEGL engine, offering high-bit-depth processing, non-destructive editing, and advanced filters.

## Modules

### New Files
- `gimp_gegl_client.py` - Main GIMP GEGL interface
- `gimp_gegl_validator.py` - Validation and error handling

## Configuration

Add to your `config.json`:

```json
{
  "gimp_exe_loc": "gimp-3.0",
  "gimp_gegl_enabled": true,
  "gimp_gegl_timeout": 60
}
```

## Installation Requirements

- GIMP 3.x installed
- Python 3.7+
- PyGObject: `pip install PyGObject`

## Usage

### Basic Usage

```python
from image.image_ops import ImageOps

# Check availability (includes automatic validation)
if ImageOps.is_gimp_gegl_available():
    # Apply brightness/contrast
    result = ImageOps.gegl_brightness_contrast("input.jpg", brightness=0.2, contrast=0.1)
    print(f"Processed: {result}")
```

### Available Methods

#### Core Methods
- `is_gimp_gegl_available()` - Check availability (with validation)
- `apply_gegl_operation()` - Generic GEGL operation interface
- `get_available_gegl_operations()` - List available operations
- `clear_gegl_validation_cache()` - Force re-validation

#### Image Processing Methods
- `gegl_brightness_contrast()` - Brightness/contrast adjustment
- `gegl_color_balance()` - Color balance correction
- `gegl_hue_saturation()` - Hue/saturation adjustment
- `gegl_levels()` - Levels adjustment
- `gegl_exposure()` - Exposure adjustment
- `gegl_gaussian_blur()` - Gaussian blur
- `gegl_unsharp_mask()` - Unsharp mask sharpening
- `gegl_noise_reduce()` - Noise reduction

### Example Operations

```python
# Color correction
result = ImageOps.gegl_color_balance(
    "input.jpg",
    cyan_red=0.1,
    magenta_green=-0.1,
    yellow_blue=0.05
)

# Advanced filtering with opacity and blend mode
result = ImageOps.apply_gegl_operation(
    "input.jpg",
    "gegl:brightness-contrast",
    {"brightness": 0.3, "contrast": 0.2},
    opacity=0.5,
    blend_mode="multiply"
)

# Get available operations
operations = ImageOps.get_available_gegl_operations()
print(f"Available: {operations}")
```

## Error Handling

```python
try:
    result = ImageOps.gegl_brightness_contrast("input.jpg", 0.2, 0.1)
except RuntimeError as e:
    print(f"GEGL operation failed: {e}")
```

Common issues:
- GIMP not installed or not accessible
- Invalid operation parameters
- Input file not found
- Operation timeout

## Testing

Run the test script:

```bash
# Test with an image
python temp_test_gegl_operations.py /path/to/image.jpg

# Show validation report
python temp_test_gegl_operations.py --report
```

## Key Features

- **Professional Operations**: Access to GIMP's GEGL processing engine
- **Automatic Validation**: Comprehensive validation with session caching
- **Error Handling**: Detailed error messages and graceful degradation
- **Performance**: Configurable timeouts and smart validation caching
- **Easy Integration**: Simple API matching existing patterns

## Troubleshooting

1. **"GIMP GEGL integration is not available"**
   - Check GIMP 3.x installation
   - Verify `gimp_exe_loc` in config.json
   - Ensure PyGObject is installed

2. **"GIMP execution failed"**
   - Check GIMP installation and permissions
   - Verify system resources (memory, disk space)

3. **"GEGL operation failed"**
   - Check operation parameters
   - Verify input file format

For detailed validation information, run:
```bash
python temp_test_gegl_operations.py --report
```