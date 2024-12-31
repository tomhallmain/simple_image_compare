import platform

import vlc


class VideoUI:
    video_frame_handle_callback = None

    # VLC player controls
    vlc_instance = vlc.Instance()
    player = vlc_instance.media_player_new()
    media = None

    @staticmethod
    def set_video_frame_handle_callback(callback):
        VideoUI.video_frame_handle_callback = callback

    def __init__(self, filepath):
        self.filepath = filepath
        self.active = False

    def display(self, canvas):
        self.ensure_video_frame()
        self.active = True
        VideoUI.media = VideoUI.vlc_instance.media_new(self.filepath)
        VideoUI.player.set_media(VideoUI.media)
        if VideoUI.player.play() == -1:
            raise Exception("Failed to play video")

    def close(self):
        self.stop()

    def stop(self):
        VideoUI.player.stop()
        self.active = False

    @staticmethod
    def pause():
        VideoUI.player.pause()

    @staticmethod
    def take_screenshot():
        VideoUI.player.take_snapshot()

    @staticmethod
    def seek(pos):
        VideoUI.player.set_position(pos)

    def ensure_video_frame(self):
        if VideoUI.video_frame_handle_callback is None:
            raise Exception("Video frame handle callback not set")
        window_id = VideoUI.video_frame_handle_callback()
        VideoUI.set_player_window(window_id)

    @staticmethod
    def set_player_window(window_id):
        # set the window id where to render VLC's video output
        if platform.system() == 'Windows':
            VideoUI.player.set_hwnd(window_id)
        else:
            VideoUI.player.set_xwindow(window_id) # this line messes up windows
