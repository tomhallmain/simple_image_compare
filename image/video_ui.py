import platform

import vlc


class VideoUI:
    video_frame_handle_callback = None

    # VLC player controls
    Instance = vlc.Instance()
    player = Instance.media_player_new()
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
        VideoUI.media = VideoUI.Instance.media_new(self.filepath)
        VideoUI.player.set_media(VideoUI.media)
        if VideoUI.player.play() == -1:
            raise Exception("Failed to play video")

    def close(self):
        self.stop()

    def stop(self):
        VideoUI.player.stop()
        self.active = False

    def pause(self):
        VideoUI.player.pause()

    def ensure_video_frame(self):
        if VideoUI.video_frame_handle_callback is None:
            raise Exception("Video frame handle callback not set")

        # set the window id where to render VLC's video output
        if platform.system() == 'Windows':
            self.player.set_hwnd(VideoUI.video_frame_handle_callback())
        else:
            self.player.set_xwindow(VideoUI.video_frame_handle_callback()) # this line messes up windows

