#!/usr/bin/env python
from __future__ import absolute_import 


import threading
import webbrowser
import time
from paperstream.marking_server import app
import waitress


def launch_browser():
    """Launches the app"""
    time.sleep(3)
    webbrowser.open("http://localhost:8000/static/index.html", new=0, autoraise=True)

def main(argv=None):
    """Main method for PaperStream"""
    LAUNCH_THREAD = threading.Thread(target=launch_browser)
    LAUNCH_THREAD.start()
    waitress.serve(app, port=8000)
    LAUNCH_THREAD.join()

if __name__ == "__main__":
    main()
