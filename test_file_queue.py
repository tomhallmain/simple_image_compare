#!/usr/bin/env python3
"""
Test script for the file operation queue system in marked_file_mover.py
"""

import os
import tempfile
import time
from files.marked_file_mover import FileOperation, FileOperationQueue, MarkedFiles
from utils.utils import Utils

def test_file_operation_queue():
    """Test the file operation queue system."""
    print("Testing file operation queue system...")
    
    # Create temporary directories for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        source_dir = os.path.join(temp_dir, "source")
        target_dir = os.path.join(temp_dir, "target")
        os.makedirs(source_dir)
        os.makedirs(target_dir)
        
        # Create test files
        test_files = []
        for i in range(3):
            test_file = os.path.join(source_dir, f"test_file_{i}.txt")
            with open(test_file, 'w') as f:
                f.write(f"Test content {i}")
            test_files.append(test_file)
        
        print(f"Created {len(test_files)} test files in {source_dir}")
        
        # Test the queue system
        queue = FileOperationQueue()
        
        # Add operations to the queue
        for test_file in test_files:
            operation = FileOperation(
                marked_file=test_file,
                target_dir=target_dir,
                move_func=Utils.copy_file
            )
            queue.add_operation(operation)
        
        print(f"Added {len(test_files)} operations to queue")
        print(f"Queue size: {queue.get_queue_size()}")
        
        # Wait for operations to complete
        queue.wait_for_completion()
        
        print("All operations completed")
        print(f"Queue size after completion: {queue.get_queue_size()}")
        
        # Verify files were copied
        copied_files = []
        for test_file in test_files:
            filename = os.path.basename(test_file)
            copied_file = os.path.join(target_dir, filename)
            if os.path.exists(copied_file):
                copied_files.append(copied_file)
        
        print(f"Successfully copied {len(copied_files)} files")
        
        # Clean up
        queue.stop_worker()
        
        # Verify results
        assert len(copied_files) == len(test_files), f"Expected {len(test_files)} files, got {len(copied_files)}"
        print("✓ All test files were successfully copied")
        
        return True

def test_marked_files_integration():
    """Test integration with MarkedFiles class."""
    print("\nTesting MarkedFiles integration...")
    
    # Create temporary directories for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        source_dir = os.path.join(temp_dir, "source")
        target_dir = os.path.join(temp_dir, "target")
        os.makedirs(source_dir)
        os.makedirs(target_dir)
        
        # Create test files
        test_files = []
        for i in range(2):
            test_file = os.path.join(source_dir, f"test_file_{i}.txt")
            with open(test_file, 'w') as f:
                f.write(f"Test content {i}")
            test_files.append(test_file)
        
        # Set up mock app_actions
        class MockAppActions:
            def toast(self, message):
                print(f"Toast: {message}")
            
            def title_notify(self, message, base_message=None, action_type=None):
                print(f"Title notify: {message}")
            
            def get_base_dir(self):
                return source_dir
        
        app_actions = MockAppActions()
        
        # Set marked files
        MarkedFiles.file_marks = test_files[:]
        
        # Test the move operation with queue
        try:
            some_files_already_present, exceptions_present = MarkedFiles.move_marks_to_dir_static(
                app_actions=app_actions,
                target_dir=target_dir,
                move_func=Utils.copy_file,
                use_queue=True
            )
            
            print(f"Move operation completed: some_files_already_present={some_files_already_present}, exceptions_present={exceptions_present}")
            
            # Verify files were copied
            copied_files = []
            for test_file in test_files:
                filename = os.path.basename(test_file)
                copied_file = os.path.join(target_dir, filename)
                if os.path.exists(copied_file):
                    copied_files.append(copied_file)
            
            print(f"Successfully copied {len(copied_files)} files")
            assert len(copied_files) == len(test_files), f"Expected {len(test_files)} files, got {len(copied_files)}"
            print("✓ MarkedFiles integration test passed")
            
        return True

def test_queue_status():
    """Test queue status reporting."""
    print("\nTesting queue status reporting...")
    
    queue = FileOperationQueue()
    
    # Check initial status
    status = MarkedFiles.get_queue_status()
    print(f"Initial queue status: {status}")
    
    # Start worker
    queue.start_worker()
    time.sleep(0.1)  # Give worker time to start
    
    # Check status after starting
    status = MarkedFiles.get_queue_status()
    print(f"Queue status after starting worker: {status}")
    
    # Stop worker
    queue.stop_worker()
    
    # Check final status
    status = MarkedFiles.get_queue_status()
    print(f"Final queue status: {status}")
    
    print("✓ Queue status reporting test passed")
    return True

if __name__ == "__main__":
    try:
        test_file_operation_queue()
        test_marked_files_integration()
        test_queue_status()
        print("\n🎉 All tests passed!")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc() 