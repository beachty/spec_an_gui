import tkinter as tk
from tkinter import ttk, messagebox

class CredentialsDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("SANE Authentication")
        self.username = tk.StringVar()
        self.password = tk.StringVar()
        self.result = None
        
        # Increase dialog size
        self.geometry("350x250")
        self.resizable(False, False)
        
        # Create main frame with padding
        main_frame = ttk.Frame(self, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create and layout widgets
        ttk.Label(main_frame, text="Username (5+2):").pack(pady=5)
        username_entry = ttk.Entry(main_frame, textvariable=self.username, width=30)
        username_entry.pack(pady=5)
        
        ttk.Label(main_frame, text="Password (SPIN):").pack(pady=5)
        pwd_entry = ttk.Entry(main_frame, textvariable=self.password, show="*", width=30)
        pwd_entry.pack(pady=5)
        
        # Style for taller button
        style = ttk.Style()
        style.configure('Tall.TButton', 
                       padding=(20, 15),  # (horizontal, vertical) padding
                       height=3)          # increased height
        
        login_btn = ttk.Button(
            main_frame, 
            text="Login",
            command=self.validate,
            style='Tall.TButton',
            width=15
        )
        login_btn.pack(pady=15)
        
        # Bind Enter key to validate
        self.bind('<Return>', lambda e: self.validate())
        
        # Make dialog modal
        self.transient(parent)
        self.grab_set()
        
        # Set initial focus
        username_entry.focus_set()
        
    def validate(self):
        if not self.username.get():
            messagebox.showerror("Error", "Username required")
            return
        if not self.password.get().isdigit():
            messagebox.showerror("Error", "Password must be numeric")
            return
        self.result = (self.username.get(), self.password.get())
        self.destroy()