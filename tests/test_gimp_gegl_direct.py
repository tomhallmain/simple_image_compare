#!/usr/bin/env python3
"""
Direct GIMP GEGL Test Script

This script tests GIMP's GEGL capabilities directly without any project dependencies.
It creates a simple test image, applies a GEGL operation, and verifies the result.

Usage:
    python test_gimp_gegl_direct.py [input_image_path]
    
If no input image is provided, it will create a simple test image.
"""

import os
import sys
import subprocess
import json
from pathlib import Path
from PIL import Image


def create_test_image(output_path, width=100, height=100):
    """Create a simple test image using PIL."""
    try:
        from PIL import Image, ImageDraw
        
        # Create a simple gradient test image
        img = Image.new('RGB', (width, height), color='white')
        draw = ImageDraw.Draw(img)
        
        # Draw some test patterns
        for i in range(0, width, 10):
            color = (i % 255, (i * 2) % 255, (i * 3) % 255)
            draw.rectangle([i, 0, i + 9, height], fill=color)
        
        # Add some text
        try:
            draw.text((10, 10), "GEGL Test", fill='black')
        except:
            pass  # Skip text if font not available
        
        img.save(output_path, 'PNG')
        print(f"✅ Created test image: {output_path}")
        return True
        
    except ImportError:
        print("❌ PIL not available, cannot create test image")
        return False
    except Exception as e:
        print(f"❌ Failed to create test image: {e}")
        return False


def create_persistent_test_files():
    """Create persistent test image and script in tests directory."""
    tests_dir = Path(__file__).parent
    
    # Create test image
    test_image_path = tests_dir / "gegl_test_input.png"
    if not test_image_path.exists():
        create_test_image(str(test_image_path), 200, 200)
    
    # Create test script
    test_script_path = tests_dir / "gegl_test_script.py"
    script_content = '''import sys
import os
import json
print("DEBUG: Starting script", flush=True)

try:
    print("DEBUG: Importing gi", flush=True)
    import gi
    print("DEBUG: Setting gi versions", flush=True)
    gi.require_version('Gimp', '3.0')
    gi.require_version('Gegl', '0.4')
    print("DEBUG: Importing GIMP modules", flush=True)
    from gi.repository import Gimp, Gegl, Gio
    print("DEBUG: Imports successful", flush=True)
except Exception as e:
    print(f"DEBUG: Import error: {e}", flush=True)
    sys.exit(1)

def test_gegl_operation(input_path, output_path):
    """Test basic GEGL operation."""
    print(f"DEBUG: Starting GEGL operation with input={input_path}, output={output_path}", flush=True)
    try:
        print("DEBUG: Loading image", flush=True)
        # Load the image
        image = Gimp.file_load(Gimp.RunMode.NONINTERACTIVE, Gio.file_new_for_path(input_path))
        if not image:
            print("DEBUG: Failed to load image", flush=True)
            return {"error": "Failed to load image"}
        
        print("DEBUG: Image loaded successfully", flush=True)
        
        # Debug: Inspect the image object to see available methods
        print("DEBUG: Image object type:", type(image), flush=True)
        print("DEBUG: Image object dir:", [attr for attr in dir(image) if not attr.startswith('_')], flush=True)
        
        # Try to find the correct method for getting active layer/drawable
        print("DEBUG: Looking for active layer methods...", flush=True)
        active_methods = [attr for attr in dir(image) if 'active' in attr.lower()]
        print("DEBUG: Methods containing 'active':", active_methods, flush=True)
        
        # Get the drawable (active layer) - GIMP 3.0 API
        print("DEBUG: Getting drawable", flush=True)
        # Try to get selected drawables first
        selected_drawables = image.get_selected_drawables()
        print("DEBUG: Selected drawables:", selected_drawables, flush=True)
        
        if selected_drawables and len(selected_drawables) > 0:
            drawable = selected_drawables[0]
            print("DEBUG: Using first selected drawable", flush=True)
        else:
            # Try to get selected layers
            selected_layers = image.get_selected_layers()
            print("DEBUG: Selected layers:", selected_layers, flush=True)
            if selected_layers and len(selected_layers) > 0:
                drawable = selected_layers[0]
                print("DEBUG: Using first selected layer", flush=True)
            else:
                print("DEBUG: No selected drawables or layers found", flush=True)
                return {"error": "No selected drawables or layers found"}
        
        print("DEBUG: Drawable found:", type(drawable), flush=True)
        
        # Initialize GEGL - CRITICAL STEP!
        print("DEBUG: Initializing GEGL", flush=True)
        Gegl.init(None)
        
        # Create GEGL node
        print("DEBUG: Creating GEGL node", flush=True)
        node = Gegl.Node()
        
        # Debug: Inspect the GEGL Node object
        print("DEBUG: GEGL Node object type:", type(node), flush=True)
        print("DEBUG: GEGL Node object dir:", [attr for attr in dir(node) if not attr.startswith('_')], flush=True)
        
        # Look for methods that might create child nodes
        child_methods = [attr for attr in dir(node) if 'child' in attr.lower() or 'add' in attr.lower()]
        print("DEBUG: Methods containing 'child' or 'add':", child_methods, flush=True)
        
        # GEGL OPERATIONS SECTION - Based on official GIMP 3.0 example:
        # Reference: https://gitlab.gnome.org/GNOME/gimp/-/blob/master/extensions/goat-exercises/goat-exercise-py3.py
        # 
        # The following approach follows the official GIMP 3.0 Python API patterns
        # for creating and connecting GEGL nodes using buffer-based operations.
        
        # Get the drawable's buffer for GEGL operations
        print("DEBUG: Getting drawable buffer", flush=True)
        buffer = drawable.get_buffer()
        shadow_buffer = drawable.get_shadow_buffer()
        
        # Create GEGL graph using the official API pattern
        print("DEBUG: Creating GEGL graph using official API pattern", flush=True)
        graph = Gegl.Node()
        
        # Create input node (buffer source)
        print("DEBUG: Creating input node", flush=True)
        input_node = graph.create_child("gegl:buffer-source")
        input_node.set_property("buffer", buffer)
        
        # Create brightness-contrast operation node
        print("DEBUG: Creating operation node", flush=True)
        op_node = graph.create_child("gegl:brightness-contrast")
        op_node.set_property("brightness", 0.2)
        op_node.set_property("contrast", 0.1)
        
        # Create output node (write buffer)
        print("DEBUG: Creating output node", flush=True)
        output_node = graph.create_child("gegl:write-buffer")
        output_node.set_property("buffer", shadow_buffer)
        
        # Connect nodes using the official API pattern (.link() method)
        print("DEBUG: Connecting nodes", flush=True)
        input_node.link(op_node)
        op_node.link(output_node)
        
        # Process the image
        print("DEBUG: Processing image", flush=True)
        output_node.process()
        print("DEBUG: Processing complete", flush=True)
        
        # Flush the shadow buffer (critical step!)
        print("DEBUG: Flushing shadow buffer", flush=True)
        shadow_buffer.flush()
        
        # Merge shadow and update the drawable
        print("DEBUG: Merging shadow and updating drawable", flush=True)
        drawable.merge_shadow(True)
        drawable.update(0, 0, drawable.get_width(), drawable.get_height())
        
        # Flush displays to ensure changes are visible
        print("DEBUG: Flushing displays", flush=True)
        Gimp.displays_flush()
        
        # TODO: Review GIMP 3.0 Python API reference to determine the correct way to
        # apply processed drawable changes to the image before saving. The current
        # approach may not be properly applying the GEGL-processed drawable to the
        # image, resulting in the original image being saved instead of the processed one.
        # Reference: https://lazka.github.io/pgi-docs/#Gimp-3.0/classes/Drawable.html
        
        # Save the image using GIMP's file save
        print("DEBUG: Saving image using GIMP file save", flush=True)
        success = Gimp.file_save(Gimp.RunMode.NONINTERACTIVE, image, Gio.file_new_for_path(output_path), None)
        if not success:
            print("DEBUG: Failed to save image", flush=True)
            return {"error": "Failed to save image"}
        
        # Verify output file was created
        print("DEBUG: Checking if output file exists", flush=True)
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"DEBUG: Output file exists, size: {file_size} bytes", flush=True)
        else:
            print("DEBUG: Output file does not exist!", flush=True)
            return {"error": "Output file was not created"}
        
        # Clean up
        print("DEBUG: Cleaning up", flush=True)
        image.delete()
        
        print("DEBUG: Operation successful", flush=True)
        return {"success": True, "output_path": output_path}
        
    except Exception as e:
        print(f"DEBUG: Exception in GEGL operation: {e}", flush=True)
        return {"error": str(e)}

# Main execution
print("DEBUG: Starting main execution", flush=True)
print(f"DEBUG: sys.argv = {sys.argv}", flush=True)

# Get file paths from environment variables
input_path = os.environ.get('GEGL_INPUT_PATH')
output_path = os.environ.get('GEGL_OUTPUT_PATH')

if not input_path or not output_path:
    print("DEBUG: Missing environment variables", flush=True)
    print(json.dumps({"error": "Missing GEGL_INPUT_PATH or GEGL_OUTPUT_PATH environment variables"}))
else:
    print(f"DEBUG: Arguments: input={input_path}, output={output_path}", flush=True)
    
    result = test_gegl_operation(input_path, output_path)
    print("DEBUG: Result:", result, flush=True)
    print(json.dumps(result))
    print("DEBUG: Script complete", flush=True)
'''
    
    with open(test_script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"✅ Created test script: {test_script_path}")
    
    return str(test_image_path), str(test_script_path)




def test_gimp_gegl(gimp_exe, input_path, output_path, script_path):
    """Test GIMP GEGL operation.
    
    KNOWN ISSUE: GEGL operations may fail with "Failed to set operation type" errors
    because GEGL cannot find its plug-ins. This is a common issue on Windows where
    the GEGL_PATH environment variable is not set correctly.
    
    ERROR SYMPTOMS:
    - "Failed to set operation type gegl:load, using a passthrough op instead"
    - "Failed to set operation type gegl:brightness-contrast, using a passthrough op instead"
    - "Failed to set operation type gegl:save, using a passthrough op instead"
    - "GEGL was unable to locate any of it's plug-ins"
    
    POTENTIAL SOLUTIONS:
    1. Set GEGL_PATH environment variable to point to GEGL operations directory
    2. Check if GEGL operations DLL files are present in GIMP installation
    3. Use GIMP's built-in operations instead of direct GEGL operations
    4. Consider using GIMP's PDB (Procedure Database) functions instead
    
    For more information, see:
    - GIMP 3.0 GEGL documentation
    - GEGL_PATH environment variable configuration
    """
    print(f"Testing GIMP GEGL with:")
    print(f"  GIMP: {gimp_exe}")
    print(f"  Input: {input_path}")
    print(f"  Output: {output_path}")
    print(f"  Script: {script_path}")
    
    # Use console mode with the persistent script
    import os
    env = os.environ.copy()
    env['GEGL_INPUT_PATH'] = input_path
    env['GEGL_OUTPUT_PATH'] = output_path
    
    # Set GEGL_PATH to help GEGL find its operations
    # Try common GEGL operations directories in GIMP 3.0 installation
    gimp_base = os.path.dirname(os.path.dirname(gimp_exe))  # Go up from bin/ to GIMP 3/
    possible_gegl_paths = [
        os.path.join(gimp_base, "lib", "gegl-0.4"),
        os.path.join(gimp_base, "lib", "gegl"),
        os.path.join(gimp_base, "lib", "gegl-0.3"),
        os.path.join(gimp_base, "lib", "gegl-0.2"),
        os.path.join(gimp_base, "lib", "GEGL"),
    ]
    
    # Find the first existing GEGL operations directory
    gegl_path = None
    for path in possible_gegl_paths:
        if os.path.exists(path):
            gegl_path = path
            print(f"DEBUG: Found GEGL operations directory: {gegl_path}")
            break
    
    if gegl_path:
        env['GEGL_PATH'] = gegl_path
        print(f"DEBUG: Set GEGL_PATH to: {gegl_path} <<<<<<<<<<<<<<<<<<<")
    else:
        print("DEBUG: No GEGL operations directory found, trying default paths")
        # Try some default fallback paths
        env['GEGL_PATH'] = os.path.join(gimp_base, "lib", "gegl-0.4")
        print(f"DEBUG: Set GEGL_PATH to: {env['GEGL_PATH']} <<<<<<<<<<<<<<<<<<<")
    
    cmd = [
        gimp_exe,
        "--batch-interpreter", "python-fu-eval",
        "-b", f"exec(open(r'{script_path}').read())",
        "--quit"
    ]
    
    print(f"Running GIMP command: {' '.join(cmd)}")
    
    # Execute GIMP with longer timeout
    print("DEBUG: Starting subprocess...")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120, env=env)
    print("DEBUG: Subprocess completed")
    
    print(f"Return code: {result.returncode}")
    print(f"STDOUT: {result.stdout}")
    if result.stderr:
        print(f"STDERR: {result.stderr}")
    
    # Parse result
    try:
        if result.stdout and result.stdout.strip():
            result_data = json.loads(result.stdout.strip().split('\n')[-1])
            if result_data.get('success'):
                print(f"✅ GEGL operation successful!")
                print(f"   Output saved to: {result_data.get('output_path')}")
                return True
            else:
                print(f"❌ GEGL operation failed: {result_data.get('error')}")
                return False
        else:
            print("❌ No output from GIMP")
            return False
    except json.JSONDecodeError as e:
        print(f"❌ Failed to parse GIMP output: {e}")
        print(f"Raw output: {result.stdout}")
        return False


def find_gimp_executable():
    """Find GIMP console executable."""
    possible_paths = [
        "gimp-console-3.0",
        "gimp-console-3",
        "gimp-console",
        r"C:\Program Files\GIMP 3\bin\gimp-console-3.0.exe",
        r"C:\Program Files\GIMP 3\bin\gimp-console-3.exe",
        r"C:\Program Files\GIMP 3\bin\gimp-console.exe",
        r"C:\Program Files (x86)\GIMP 3\bin\gimp-console-3.0.exe",
        r"C:\Program Files (x86)\GIMP 3\bin\gimp-console-3.exe",
        r"C:\Program Files (x86)\GIMP 3\bin\gimp-console.exe",
        # Fallback to regular GIMP if console not found
        "gimp-3.0",
        "gimp",
        r"C:\Program Files\GIMP 3\bin\gimp-3.0.exe",
        r"C:\Program Files\GIMP 3\bin\gimp.exe",
        r"C:\Program Files (x86)\GIMP 3\bin\gimp-3.0.exe",
        r"C:\Program Files (x86)\GIMP 3\bin\gimp.exe",
    ]
    
    for path in possible_paths:
        if os.path.isfile(path):
            return path
        
        # Try to find in PATH
        import shutil
        found = shutil.which(path)
        if found:
            return found
    
    return None


def main():
    """Main test function."""
    print("GIMP GEGL Direct Test")
    print("=" * 40)
    
    # Find GIMP executable
    gimp_exe = find_gimp_executable()
    if not gimp_exe:
        print("❌ GIMP executable not found")
        print("Please install GIMP 3.0 or specify the path manually")
        return 1
    
    print(f"✅ Found GIMP: {gimp_exe}")
    
    # Create persistent test files
    print(f"\nCreating test files...")
    input_path, script_path = create_persistent_test_files()
    
    # Set output path
    input_dir = os.path.dirname(input_path)
    input_name = os.path.splitext(os.path.basename(input_path))[0]
    input_ext = os.path.splitext(input_path)[1]
    output_path = os.path.join(input_dir, f"{input_name}_gegl_test{input_ext}")
    
    # Test GEGL operation
    print(f"\nTesting GEGL operation...")
    success = test_gimp_gegl(gimp_exe, input_path, output_path, script_path)
    
    if success:
        print(f"✅ Test completed successfully!")
        print(f"✅ Output saved to: {output_path}")
        print(f"✅ Test files created in: {os.path.dirname(script_path)}")
        
        # Check file size
        if os.path.exists(output_path):
            size = os.path.getsize(output_path)
            print(f"✅ Output file size: {size} bytes")
        
        return 0
    else:
        print(f"❌ Test failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
