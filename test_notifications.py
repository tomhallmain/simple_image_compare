import time
from utils.notification_manager import notification_manager
from utils.constants import ActionType

def mock_title_callback(title):
    """Mock callback to simulate window title updates"""
    print(f"\n[Mock Callback] Title updated: {title}")

def test_1(notification_manager):
    # Test case 1: Single notification
    print("\nTest 1: Adding single notification")
    notification_manager.add_notification(
        "Moved file: test1.jpg to /new/location",
        action_type=ActionType.MOVE_FILE,
        is_manual=True
    )
    print("Waiting for notification to process...")
    time.sleep(10)  # Wait longer than the notification duration

def test_2(notification_manager):
    # Test case 2: Multiple notifications of same type within time window
    print("\nTest 2: Adding multiple notifications of same type")
    for i in range(3):
        notification_manager.add_notification(
            f"Moved file: test{i+2}.jpg to /new/location",
            action_type=ActionType.MOVE_FILE,
            is_manual=True
        )
        time.sleep(0.5)
    print("Waiting for notifications to process...")
    time.sleep(6)

def test_3(notification_manager):
    # Test case 3: Different types of notifications
    print("\nTest 3: Adding different types of notifications")
    notification_manager.add_notification(
        "Copied file: test5.jpg to /backup",
        action_type=ActionType.COPY_FILE,
        is_manual=True
    )
    time.sleep(1)
    notification_manager.add_notification(
        "Removed file: test6.jpg",
        action_type=ActionType.REMOVE_FILE,
        is_manual=False
    )
    print("Waiting for notifications to process...")
    time.sleep(6)

def test_4(notification_manager):
    # Test case 4: Auto and manual notifications of same type
    print("\nTest 4: Mixing auto and manual notifications")
    notification_manager.add_notification(
        "Moved file: test7.jpg to /auto",
        action_type=ActionType.MOVE_FILE,
        is_manual=False
    )
    time.sleep(1)
    notification_manager.add_notification(
        "Moved file: test8.jpg to /manual",
        action_type=ActionType.MOVE_FILE,
        is_manual=True
    )
    print("Waiting for notifications to process...")
    time.sleep(6)

def test_5(notification_manager):
    # Test case 5: Long duration notification
    print("\nTest 5: Adding long duration notification")
    notification_manager.add_notification(
        "This notification will stay for 10 seconds",
        duration=10.0,
        action_type=ActionType.SYSTEM
    )
    print("Waiting for long notification to expire...")
    time.sleep(12)  # Wait for long notification to expire

def main():
    print("\n=== Starting Notification Manager Test ===")
    
    # Set up the mock callback
    # notification_manager.set_title_update_callback(mock_title_callback)
    
    # Set initial title
    notification_manager.set_current_title("Simple Image Compare - C:/test/images")
    print("\nInitial title set")

    test_1(notification_manager)
    test_2(notification_manager)
    test_3(notification_manager)
    test_4(notification_manager)
    test_5(notification_manager)    

    print("\n=== All tests completed ===")

if __name__ == "__main__":
    main() 