import tkinter as tk
from tkinter import ttk

class EnmSelectionDialog(tk.Toplevel):
    def __init__(self, parent, enm_map):
        super().__init__(parent)
        self.title("ENM Selection")
        self.result = None
        self.enm_map = enm_map
        
        # Create main frame
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create canvas and scrollbar
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Add ENM buttons
        for row, (enm_name, enm_info) in enumerate(sorted(self.enm_map.items())):
            ttk.Label(scrollable_frame, text=enm_name).grid(row=row, column=0, padx=5, pady=2)
            ttk.Button(
                scrollable_frame, 
                text=f"S1 ({enm_info.neid_s1})",
                command=lambda name=enm_name, is_s1=True: self.select(name, is_s1)
            ).grid(row=row, column=1, padx=5, pady=2)
            ttk.Button(
                scrollable_frame,
                text=f"S2 ({enm_info.neid_s2})",
                command=lambda name=enm_name, is_s1=False: self.select(name, is_s1)
            ).grid(row=row, column=2, padx=5, pady=2)

        # Pack scrollbar and canvas
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        
        self.geometry("400x600")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
    def select(self, enm_name: str, is_s1: bool):
        self.result = (enm_name, is_s1)
        self.destroy()