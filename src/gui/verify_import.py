
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

try:
    from src.gui.kingdee_sync_gui import KingdeeSyncGUI
    from PySide6.QtCore import QPoint
    print("Import successful")
    
    # Check if QPoint is imported in the module (we can't easily inspect local imports of a module from outside without inspecting source, 
    # but if the module loaded without SyntaxError or ImportError, it's a good sign.
    # The NameError happens at runtime, so we can't fully verify without running the method.)
    
    print("Verification script finished.")
except Exception as e:
    print(f"Import failed: {e}")
