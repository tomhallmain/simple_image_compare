#!/usr/bin/env python3
"""
Test script to demonstrate the new texture functionality in image rotation.
This script creates a simple test image and rotates it with different texture backgrounds.
"""

import cv2
import numpy as np
import os
from image.image_ops import ImageOps

def create_test_image():
    """Create a simple test image for rotation testing."""
    # Create a colorful test image
    img = np.zeros((300, 400, 3), dtype=np.uint8)
    
    # Add some colored rectangles
    cv2.rectangle(img, (50, 50), (150, 150), (255, 0, 0), -1)  # Blue
    cv2.rectangle(img, (200, 50), (350, 150), (0, 255, 0), -1)  # Green
    cv2.rectangle(img, (50, 200), (200, 250), (0, 0, 255), -1)  # Red
    cv2.rectangle(img, (250, 200), (350, 250), (255, 255, 0), -1)  # Cyan
    
    # Add some text
    cv2.putText(img, "TEST IMAGE", (100, 280), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    
    return img

def test_texture_generation():
    """Test the texture generation methods."""
    print("Testing texture generation methods...")
    
    # Test each texture type
    texture_types = ["perlin", "gaussian", "gradient", "cellular"]
    
    for texture_type in texture_types:
        print(f"Generating {texture_type} texture...")
        texture = ImageOps.generate_noise_texture(200, 200, texture_type)
        
        # Save the texture for visual inspection
        filename = f"test_texture_{texture_type}.png"
        cv2.imwrite(filename, texture)
        print(f"Saved {filename}")
    
    print("Texture generation test completed!\n")

def test_rotation_with_textures():
    """Test rotation with different texture backgrounds."""
    print("Testing rotation with texture backgrounds...")
    
    # Create test image
    test_img = create_test_image()
    cv2.imwrite("test_original.png", test_img)
    print("Created test_original.png")
    
    # Test different rotation angles with textures
    angles = [30, 45, 60, 90]
    
    for angle in angles:
        print(f"Testing rotation by {angle} degrees...")
        
        # Test with texture (default behavior)
        rotated_textured = ImageOps._rotate_image_partial(test_img, angle=angle, use_texture=True)
        filename_textured = f"test_rotated_{angle}_textured.png"
        cv2.imwrite(filename_textured, rotated_textured)
        print(f"Saved {filename_textured}")
        
        # Test with solid color (original behavior)
        rotated_solid = ImageOps._rotate_image_partial(test_img, angle=angle, use_texture=False)
        filename_solid = f"test_rotated_{angle}_solid.png"
        cv2.imwrite(filename_solid, rotated_solid)
        print(f"Saved {filename_solid}")
    
    print("Rotation test completed!\n")

def test_probability_based_rotation():
    """Test the new probability-based texture selection."""
    print("Testing probability-based texture selection...")
    
    # Create test image
    test_img = create_test_image()
    
    # Test different probability settings
    probabilities = [0.25, 0.5, 0.75, 0.9]
    test_count = 5  # Number of rotations per probability setting
    
    for prob in probabilities:
        print(f"\nTesting with {prob*100}% texture probability:")
        
        for i in range(test_count):
            # Use the public method which now has probability-based selection
            # Note: We need to use a temporary file since the public method expects a file path
            temp_filename = "temp_test_image.png"
            cv2.imwrite(temp_filename, test_img)
            
            # Call the public method with probability
            ImageOps.rotate_image_partial(temp_filename, angle=45, texture_probability=prob)
            
            # Rename the output file
            output_filename = f"test_prob_{int(prob*100)}_run_{i+1}.png"
            rotated_filename = ImageOps.new_filepath(temp_filename, append_part="_rot")
            if os.path.exists(rotated_filename):
                os.rename(rotated_filename, output_filename)
                print(f"  Saved {output_filename}")
            
            # Clean up temp file
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
    
    print("\nProbability-based rotation test completed!")
    print("Note: The actual texture/solid color selection is random based on probability.\n")

def cleanup_test_files():
    """Clean up test files."""
    test_files = [
        "test_original.png",
        "test_texture_perlin.png",
        "test_texture_gaussian.png", 
        "test_texture_gradient.png",
        "test_texture_cellular.png"
    ]
    
    # Add rotation test files
    for angle in [30, 45, 60, 90]:
        test_files.extend([
            f"test_rotated_{angle}_textured.png",
            f"test_rotated_{angle}_solid.png"
        ])
    
    print("Test files created:")
    for filename in test_files:
        if os.path.exists(filename):
            print(f"  - {filename}")
    
    print("\nTo clean up test files, run:")
    print("rm test_*.png")

if __name__ == "__main__":
    print("=== Image Rotation Texture Test ===\n")
    
    try:
        # Test texture generation
        test_texture_generation()
        
        # Test rotation with textures
        test_rotation_with_textures()
        
        # Test probability-based rotation
        test_probability_based_rotation()
        
        # Show cleanup info
        cleanup_test_files()
        
        print("All tests completed successfully!")
        print("Check the generated PNG files to see the different texture effects.")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
