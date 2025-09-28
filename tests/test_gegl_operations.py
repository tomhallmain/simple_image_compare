#!/usr/bin/env python3
"""
Test script for GIMP GEGL operations integration.

This script demonstrates various GEGL operations available through the
GIMP 3 integration in the simple_image_compare project.

Usage:
    python temp_test_gegl_operations.py <input_image_path>
    
Example:
    python temp_test_gegl_operations.py /path/to/image.jpg
"""

import sys
import os
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from image.image_ops import ImageOps
from utils.logging_setup import get_logger

logger = get_logger("gegl_test")


def test_gegl_availability():
    """Test if GIMP GEGL integration is available."""
    print("Testing GIMP GEGL availability...")
    
    if not ImageOps.is_gimp_gegl_available():
        print("❌ GIMP GEGL integration is not available")
        print("   GEGL operations require GIMP 3.0 or later")
        print("   The system will automatically detect and enable GEGL if GIMP 3+ is found")
        return False
    
    print("✅ GIMP GEGL integration is available")
    print("   (Comprehensive validation has been performed)")
    
    # Get available operations
    operations = ImageOps.get_available_gegl_operations()
    print(f"   Available GEGL operations: {len(operations)}")
    for op in operations[:5]:  # Show first 5 operations
        print(f"   - {op}")
    if len(operations) > 5:
        print(f"   ... and {len(operations) - 5} more")
    
    return True


def test_basic_operations(input_path):
    """Test basic GEGL operations."""
    print(f"\nTesting basic GEGL operations on: {input_path}")
    
    if not os.path.exists(input_path):
        print(f"❌ Input file not found: {input_path}")
        return False
    
    # Get input directory and filename components for output path generation
    input_dir = os.path.dirname(input_path)
    input_name = os.path.splitext(os.path.basename(input_path))[0]
    input_ext = os.path.splitext(input_path)[1]
    
    try:
        # Test brightness/contrast
        print("   Testing brightness/contrast adjustment...")
        output_path = os.path.join(input_dir, f"{input_name}_brightness_contrast{input_ext}")
        result = ImageOps.gegl_brightness_contrast(input_path, brightness=0.2, contrast=0.1, output_path=output_path)
        print(f"   ✅ Brightness/contrast: {result}")
        
        # Test color balance
        print("   Testing color balance...")
        output_path = os.path.join(input_dir, f"{input_name}_color_balance{input_ext}")
        result = ImageOps.gegl_color_balance(input_path, cyan_red=0.1, magenta_green=-0.1, output_path=output_path)
        print(f"   ✅ Color balance: {result}")
        
        # Test hue/saturation
        print("   Testing hue/saturation...")
        output_path = os.path.join(input_dir, f"{input_name}_hue_saturation{input_ext}")
        result = ImageOps.gegl_hue_saturation(input_path, hue=10.0, saturation=20.0, output_path=output_path)
        print(f"   ✅ Hue/saturation: {result}")
        
        # Test Gaussian blur
        print("   Testing Gaussian blur...")
        output_path = os.path.join(input_dir, f"{input_name}_gaussian_blur{input_ext}")
        result = ImageOps.gegl_gaussian_blur(input_path, std_dev_x=2.0, std_dev_y=2.0, output_path=output_path)
        print(f"   ✅ Gaussian blur: {result}")
        
        # Test unsharp mask
        print("   Testing unsharp mask...")
        output_path = os.path.join(input_dir, f"{input_name}_unsharp_mask{input_ext}")
        result = ImageOps.gegl_unsharp_mask(input_path, std_dev=1.5, scale=0.8, output_path=output_path)
        print(f"   ✅ Unsharp mask: {result}")
        
        # Test noise reduction
        print("   Testing noise reduction...")
        output_path = os.path.join(input_dir, f"{input_name}_noise_reduce{input_ext}")
        result = ImageOps.gegl_noise_reduce(input_path, iterations=2, spatial_radius=1.5, output_path=output_path)
        print(f"   ✅ Noise reduction: {result}")
        
        # Test levels adjustment
        print("   Testing levels adjustment...")
        output_path = os.path.join(input_dir, f"{input_name}_levels{input_ext}")
        result = ImageOps.gegl_levels(input_path, in_low=0.1, in_high=0.9, gamma=1.2, output_path=output_path)
        print(f"   ✅ Levels: {result}")
        
        # Test exposure adjustment
        print("   Testing exposure adjustment...")
        output_path = os.path.join(input_dir, f"{input_name}_exposure{input_ext}")
        result = ImageOps.gegl_exposure(input_path, black=0.05, exposure=0.3, gamma=1.1, output_path=output_path)
        print(f"   ✅ Exposure: {result}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during GEGL operations: {e}")
        return False


def test_opacity_and_blend_modes(input_path):
    """Test opacity and blend mode features."""
    print(f"\nTesting opacity and blend mode features on: {input_path}")
    
    if not os.path.exists(input_path):
        print(f"❌ Input file not found: {input_path}")
        return False
    
    # Get input directory and filename components for output path generation
    input_dir = os.path.dirname(input_path)
    input_name = os.path.splitext(os.path.basename(input_path))[0]
    input_ext = os.path.splitext(input_path)[1]
    
    try:
        # Test with opacity
        print("   Testing brightness/contrast with 50% opacity...")
        output_path = os.path.join(input_dir, f"{input_name}_brightness_contrast_opacity{input_ext}")
        result = ImageOps.apply_gegl_operation(
            input_path, 
            "gegl:brightness-contrast", 
            {"brightness": 0.3, "contrast": 0.2},
            output_path=output_path,
            opacity=0.5
        )
        print(f"   ✅ Brightness/contrast with opacity: {result}")
        
        # Test with blend mode
        print("   Testing color balance with multiply blend mode...")
        output_path = os.path.join(input_dir, f"{input_name}_color_balance_multiply{input_ext}")
        result = ImageOps.apply_gegl_operation(
            input_path,
            "gegl:color-balance",
            {"cyan-red": 0.2, "magenta-green": -0.1},
            output_path=output_path,
            blend_mode="multiply"
        )
        print(f"   ✅ Color balance with multiply: {result}")
        
        # Test with both opacity and blend mode
        print("   Testing hue/saturation with overlay blend and 75% opacity...")
        output_path = os.path.join(input_dir, f"{input_name}_hue_saturation_overlay_opacity{input_ext}")
        result = ImageOps.apply_gegl_operation(
            input_path,
            "gegl:hue-saturation",
            {"hue": 15.0, "saturation": 25.0},
            output_path=output_path,
            opacity=0.75,
            blend_mode="overlay"
        )
        print(f"   ✅ Hue/saturation with overlay + opacity: {result}")
        
        # Test available blend modes
        print("   Testing blend mode enumeration...")
        blend_modes = ImageOps.get_available_blend_modes()
        print(f"   ✅ Available blend modes: {len(blend_modes)} modes")
        print(f"   ✅ First 10 blend modes: {blend_modes[:10]}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during opacity/blend mode tests: {e}")
        return False


def test_custom_operation(input_path):
    """Test custom GEGL operation with custom parameters."""
    print(f"\nTesting custom GEGL operation...")
    
    # Get input directory and filename components for output path generation
    input_dir = os.path.dirname(input_path)
    input_name = os.path.splitext(os.path.basename(input_path))[0]
    input_ext = os.path.splitext(input_path)[1]
    
    try:
        # Test a custom operation with specific parameters
        custom_params = {
            "brightness": 0.3,
            "contrast": 0.2,
            "cyan-red": 0.1,
            "magenta-green": -0.1,
            "yellow-blue": 0.05
        }
        
        # Apply multiple operations in sequence
        print("   Testing custom brightness/contrast operation...")
        intermediate_output = os.path.join(input_dir, f"{input_name}_custom_brightness_contrast{input_ext}")
        result = ImageOps.apply_gegl_operation(
            input_path, 
            "gegl:brightness-contrast", 
            {"brightness": custom_params["brightness"], "contrast": custom_params["contrast"]},
            output_path=intermediate_output
        )
        print(f"   ✅ Custom brightness/contrast: {result}")
        
        # Apply color balance to the result
        print("   Testing custom color balance operation...")
        final_output = os.path.join(input_dir, f"{input_name}_custom_color_balance{input_ext}")
        result = ImageOps.apply_gegl_operation(
            result,
            "gegl:color-balance",
            {
                "cyan-red": custom_params["cyan-red"],
                "magenta-green": custom_params["magenta-green"],
                "yellow-blue": custom_params["yellow-blue"]
            },
            output_path=final_output
        )
        
        print(f"   ✅ Custom operation sequence: {result}")
        return True
        
    except Exception as e:
        print(f"❌ Error during custom operation: {e}")
        return False


def test_operation_schemas():
    """Test getting operation schemas."""
    print(f"\nTesting operation schemas...")
    
    try:
        # Test getting schema for brightness-contrast
        schema = ImageOps.get_gegl_operation_schema("gegl:brightness-contrast")
        print(f"   ✅ Brightness-contrast schema: {schema}")
        
        # Test getting schema for color-balance
        schema = ImageOps.get_gegl_operation_schema("gegl:color-balance")
        print(f"   ✅ Color-balance schema: {schema}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error getting operation schemas: {e}")
        return False


def test_validation_features():
    """Test validation and debugging features."""
    print(f"\nTesting validation features...")
    
    try:
        # Test cache clearing (for demonstration)
        print("   Testing validation cache clearing...")
        ImageOps.clear_gegl_validation_cache()
        print("   ✅ Validation cache cleared")
        
        # Re-check availability (should re-validate)
        print("   Re-validating GEGL availability...")
        available = ImageOps.is_gimp_gegl_available()
        if available:
            print("   ✅ GEGL re-validation successful")
        else:
            print("   ❌ GEGL re-validation failed")
            return False
        
        # Test validation report
        print("   Testing validation report...")
        report = ImageOps.get_gegl_validation_report()
        if report and "Error" not in report:
            print("   ✅ Validation report generated successfully")
        else:
            print("   ⚠️  Validation report may have issues")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing validation features: {e}")
        return False


def show_validation_report():
    """Show detailed validation report."""
    print("\nDetailed Validation Report:")
    print("-" * 40)
    report = ImageOps.get_gegl_validation_report()
    print(report)


def main():
    """Main test function."""
    print("GIMP GEGL Operations Test")
    print("=" * 40)
    
    if len(sys.argv) < 2:
        print("Usage: python temp_test_gegl_operations.py <input_image_path>")
        print("Example: python temp_test_gegl_operations.py /path/to/image.jpg")
        print("\nTo show validation report only:")
        print("python temp_test_gegl_operations.py --report")
        return 1
    
    input_path = sys.argv[1]
    
    # Handle report-only mode
    if input_path == "--report":
        show_validation_report()
        return 0
    
    # Test availability
    if not test_gegl_availability():
        print("\nFor detailed validation information, run:")
        print("python temp_test_gegl_operations.py --report")
        return 1
    
    # Test operation schemas
    if not test_operation_schemas():
        return 1
    
    # Test validation features
    if not test_validation_features():
        return 1
    
    # Test basic operations
    if not test_basic_operations(input_path):
        return 1
    
    # Test opacity and blend modes
    if not test_opacity_and_blend_modes(input_path):
        return 1
    
    # Test custom operation
    if not test_custom_operation(input_path):
        return 1
    
    print("\n🎉 All GEGL tests completed successfully!")
    print("   Check the output directory for processed images.")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
