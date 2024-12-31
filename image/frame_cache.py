import os
import tempfile

import cv2

from utils.config import config


class FrameCache:
    temporary_directory = tempfile.TemporaryDirectory(prefix="tmp_comp_frames")
    cache = {}

    @staticmethod
    def get_image_path(media_path):
        # The media path is probably a video or GIF. Need to grab the first frame.
        media_path_lower = media_path.lower()
        for ext in config.video_types:
            if media_path_lower.endswith(ext):
                return FrameCache.get_first_frame(media_path)
        return media_path

    @staticmethod
    def get_first_frame(media_path):
        if media_path not in FrameCache.cache:
            FrameCache.set_first_frame(media_path)
        return FrameCache.cache[media_path]

    @staticmethod
    def set_first_frame(media_path):
        cap = cv2.VideoCapture(media_path)

        # Read the first frame
        ret, frame = cap.read()

        basename = os.path.splitext(os.path.basename(media_path))[0] + ".jpg"
        frame_path = os.path.join(FrameCache.temporary_directory.name, basename)

        # Check if the frame was successfully read
        if ret:
            # Save the first frame as an image
            cv2.imwrite(frame_path, frame)
        else:
            print("Error: Could not read the first frame.")

        # Release the video capture object
        cap.release()
        FrameCache.cache[media_path] = frame_path

    @staticmethod
    def clear():
        FrameCache.cache = {}

