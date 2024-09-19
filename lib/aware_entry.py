
from tkinter.ttk import Entry

class AwareEntry(Entry):
    an_entry_has_focus = False

    def __init__(self, *args, **kwargs):
        Entry.__init__(self, *args, **kwargs)
        self.bind('<FocusIn>', lambda e: AwareEntry.set_focus(True))
        self.bind('<FocusOut>', lambda e: AwareEntry.set_focus(False))

    @staticmethod
    def set_focus(in_focus):
        AwareEntry.an_entry_has_focus = in_focus
