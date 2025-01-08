import tkinter as tk
from src.gui.main_window import SpectralAnalyzerGUI

def main():
    root = tk.Tk()
    app = SpectralAnalyzerGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()