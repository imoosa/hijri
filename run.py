"""
Run with:  python run.py
(from the project root - the folder that contains this file and app/)

This is the fix for the earlier "attempted relative import with no known
parent package" error: that happens when you execute a file *inside* the
app/ package directly (e.g. `python app/main.py`). Running this file
instead, from the root, imports `app` as a proper package.
"""

from app.main import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=8000)
