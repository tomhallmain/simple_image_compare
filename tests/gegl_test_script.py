import sys
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
        
        # Mark the image as dirty so changes are saved
        print("DEBUG: Marking image as dirty", flush=True)
        image.set_dirty(True)
        
        # Flush displays to ensure changes are visible
        print("DEBUG: Flushing displays", flush=True)
        Gimp.displays_flush()
        
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
