import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import time
import json
import os
from ..core.sane import SANE
from ..core.spectral_analyzer import SpectralAnalyzer

class SpectralAnalyzerGUI(ttk.Frame):
    DEBUG_USERNAME = '***REMOVED***'
    DEBUG_PASSWORD = '***REMOVED***'
    DEBUG_SC = '12C1'
    DEBUG_FDD = '***REMOVED***'

    def __init__(self, master):
        # show sector carrier
        self.show_sc = tk.BooleanVar(value=False)
        self.show_fdd = tk.BooleanVar(value=False)

        # mode selection
        self.selected_mode = tk.StringVar(value="pget")

        # Initialize frame
        super().__init__(master)
        self.master = master
        self.master.title("VZ Spectral Analyzer GUI")
        
        # menu bar
        self._create_menu_bar()

        # Set minimum and initial window size
        self.master.minsize(800, 900)
        self.master.geometry("800x900")  # Set initial size
        
        # Store initial size for restoration
        self.master.bind("<Configure>", self._on_window_configure)
        self._window_size = (800, 900)
        
        # Initialize attributes
        self.pair_presets = {}
        self.enb_presets = {}
        
        # Configure main frame
        self.grid(row=0, column=0, sticky="nsew")
        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        
        # Configure frame grid
        self.grid_columnconfigure(0, weight=1)  # Input section
        self.grid_columnconfigure(1, weight=0)  # Separator
        self.grid_columnconfigure(2, weight=1)  # Preset section
        
        # Configure row weights
        self.grid_rowconfigure(1, weight=1)  # Input/Preset area
        self.grid_rowconfigure(4, weight=1)  # Debug area
        
        # Setup components - Reordered
        self._create_status_bar()
        self._create_mode_panel()  # Add this before preset panel
        self._create_preset_panels()
        self._create_input_frame()
        self._create_controls()
        self._create_debug_frame()
        
        # Initialize SANE with self as parent
        self.sane = SANE(self)
        self.analyzer = SpectralAnalyzer(self.sane)

        # Schedule preset loading after window is drawn
        self.master.after(100, self._initialize_presets)

    def _on_window_configure(self, event):
        """Store window size when user manually resizes"""
        if event.widget == self.master:
            self._window_size = (event.width, event.height)
    
    def _restore_window_size(self):
        """Restore main window size"""
        width, height = self._window_size
        self.master.geometry(f"{width}x{height}")

    def _create_mode_panel(self):
        """Create mode selection panel with radio buttons"""
        mode_frame = ttk.LabelFrame(self, text="Analysis Mode", padding="10")
        mode_frame.grid(row=0, column=2, sticky="ew", padx=10, pady=5)
        
        # Mode radio buttons
        modes = [
            ("On Demand | PGET", "pget"),
            ("Last 4 ROP (Coming Soon)", "four_rop")
        ]
        
        for i, (text, value) in enumerate(modes):
            rb = ttk.Radiobutton(
                mode_frame,
                text=text,
                value=value,
                variable=self.selected_mode
            )
            rb.grid(row=0, column=i, sticky="w", padx=5, pady=2)

    def _create_menu_bar(self):
        """Create top menu bar with File and Help menus"""
        menubar = tk.Menu(self.master)
        self.master.config(menu=menubar)
        
        # File Menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.master.quit)
        
        # Help Menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_help)

    def _show_help(self):
        """Display help dialog with program information"""
        help_window = tk.Toplevel(self.master)
        help_window.title("About VZ Spectral Analyzer")
        help_window.geometry("500x400")
        help_window.resizable(False, False)
        
        # Create text widget
        text = tk.Text(help_window, wrap=tk.WORD, padx=10, pady=10)
        text.pack(expand=True, fill="both")
        
        # Configure tags for formatting
        text.tag_configure("title", font=("Arial", 16, "bold"), justify="center")
        text.tag_configure("version", font=("Arial", 10, "italic"), foreground="gray50")
        text.tag_configure("heading", font=("Arial", 12, "bold"), foreground="navy")
        text.tag_configure("bullet", font=("Arial", 10), lmargin1=20, lmargin2=20)
        text.tag_configure("link", font=("Arial", 10), foreground="blue", underline=1)
        
        # Insert formatted text
        text.insert("end", "VZ Spectral Analyzer GUI\n\n", "title")
        text.insert("end", "Version: 0.1.2\n\n", "version")
        
        text.insert("end", "Description:\n", "heading")
        text.insert("end", "This tool utilizes the SANE SSH interface to connect directly to eNBs and analyze UL Spectral Data.\n\n")
        
        text.insert("end", "Data Source Details:\n", "heading")
        text.insert("end", "• Currently the tool only supports using instantaneos pget(s) as a data source for analysis\n\n", "bullet")
        
        text.insert("end", "Features:\n", "heading")
        text.insert("end", "• SANE Authentication and Connection\n", "bullet")
        text.insert("end", "• FDD UL Spectral Analysis driven by eNB or Sector Carrier Options\n", "bullet")
        text.insert("end", "• Preset Management for rapid data entry\n", "bullet")
        text.insert("end", "• Debug Logging for the super user\n\n", "bullet")
        
        text.insert("end", "For support, contact: ", "heading")
        text.insert("end", "***REMOVED***", "link")
        
        # Make text read-only
        text.config(state="disabled")
        
        # Add close button
        ttk.Button(help_window, text="Close", command=help_window.destroy).pack(pady=10)
        
        # Make window modal
        help_window.transient(self.master)
        help_window.grab_set()
        self.master.wait_window(help_window)

    def _create_status_bar(self):
        """Create connection status bar"""
        # Create container frame for centering
        status_container = ttk.Frame(self)
        status_container.grid(row=0, column=0, columnspan=2, sticky="ew", pady=5)
        status_container.columnconfigure(0, weight=1)  # Left margin
        status_container.columnconfigure(3, weight=1)  # Right margin
        
        # Create status labels centered in container
        ttk.Label(status_container, text="\nSANE Connection Status:").grid(row=0, column=1, padx=5)
        self.status_var = tk.StringVar(value="\nNot Connected")
        ttk.Label(status_container, textvariable=self.status_var).grid(row=0, column=2, padx=5)
        
    def _create_input_frame(self):
        """Create input pairs frame"""
        container = ttk.Frame(self)
        container.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=20)
        container.columnconfigure(0, weight=1)
        container.columnconfigure(2, weight=1)
        
        # Create input frame centered in container
        input_frame = ttk.LabelFrame(container, text="Input Data", padding="10")
        input_frame.grid(row=0, column=1, sticky="nsew")
        
        # eNB Entry field
        self.enb_label = ttk.Label(input_frame, text="eNB ID\nEx: ***REMOVED***", justify="center")
        self.enb_label.grid(row=0, column=0, padx=10)
        self.enb_entry = ttk.Entry(input_frame, width=15)
        self.enb_entry.grid(row=1, column=0, padx=10, pady=4)
        
        # Headers for FDD/SC (initially hidden)
        self.sc_label = ttk.Label(input_frame, text="Sector Carrier\nEx: 12", justify="center")
        self.sc_label.grid(row=2, column=0, padx=10)
        self.fdd_label = ttk.Label(input_frame, text="FDD\nEx: ***REMOVED***_1_2", justify="center")
        self.fdd_label.grid(row=2, column=1, padx=10)
        
        # Entry pairs
        self.pairs = []
        self.sc_entries = []
        self.fdd_entries = []
        for i in range(5):
            sc_var = tk.StringVar()
            fdd_var = tk.StringVar()
            
            sc_entry = ttk.Entry(input_frame, textvariable=sc_var, width=15)
            sc_entry.grid(row=i+3, column=0, padx=10, pady=4)
            self.sc_entries.append(sc_entry)
            
            fdd_entry = ttk.Entry(input_frame, textvariable=fdd_var, width=15)
            fdd_entry.grid(row=i+3, column=1, padx=10, pady=4)
            self.fdd_entries.append(fdd_entry)
            self.pairs.append((sc_var, fdd_var))
        
        # Add checkboxes below entry fields
        self.sc_checkbox = ttk.Checkbutton(
            input_frame, 
            text="Specify Sector Carrier",
            variable=self.show_sc,
            command=self._toggle_sc_visibility
        )
        self.sc_checkbox.grid(row=8, column=0, columnspan=2, pady=(10,0))
    
        self.fdd_checkbox = ttk.Checkbutton(
            input_frame,
            text="Specify FDD",
            variable=self.show_fdd,
            command=self._toggle_fdd_visibility
        )
        self.fdd_checkbox.grid(row=9, column=0, columnspan=2, pady=(10,0))
        
        # Initialize field visibility
        self._toggle_sc_visibility()
        self._toggle_fdd_visibility()

    def _toggle_sc_visibility(self):
        """Toggle visibility of sector carrier fields"""
        state = 'normal' if self.show_sc.get() else 'hidden'
        self.sc_label.grid_remove() if state == 'hidden' else self.sc_label.grid()
        
        for entry in self.sc_entries:
            if state == 'hidden':
                entry.grid_remove()
                entry.delete(0, tk.END)  # Clear SC when hiding
            else:
                entry.grid()
    
    def _toggle_fdd_visibility(self):
        """Toggle visibility of FDD fields and hide/show eNB field"""
        state = 'normal' if self.show_fdd.get() else 'hidden'
        
        # Toggle eNB visibility (inverse of FDD visibility)
        if state == 'hidden':
            self.enb_label.grid()
            self.enb_entry.grid()
            self.sc_checkbox.grid_remove()  # Hide SC checkbox
            self.show_sc.set(False)  # Uncheck SC
            self._toggle_sc_visibility()  # Update SC fields
        else:
            self.enb_label.grid_remove()
            self.enb_entry.grid_remove()
            self.enb_entry.delete(0, tk.END)
            self.sc_checkbox.grid()  # Show SC checkbox
        
        # Toggle FDD visibility
        self.fdd_label.grid_remove() if state == 'hidden' else self.fdd_label.grid()
        for entry in self.fdd_entries:
            if state == 'hidden':
                entry.grid_remove()
                entry.delete(0, tk.END)
            else:
                entry.grid()
            
    def _create_controls(self):
        """Create control buttons and toggles"""
        control_frame = ttk.Frame(self)
        control_frame.grid(row=2, column=0, columnspan=2, pady=5)
        
        ttk.Button(control_frame, text="Connect", command=self.connect).pack(side="left", padx=5)
        ttk.Button(control_frame, text="Analyze", command=self.analyze).pack(side="left", padx=5)
        # ttk.Button(control_frame, text="DEBUG PRESET", command=self.fill_debug_preset).pack(side="left", padx=5)

    def _create_debug_frame(self):
        """Create debug logging frame"""
        debug_frame = ttk.LabelFrame(self, text="Debug Log", padding="5")
        debug_frame.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=5)
        
        # Configure debug frame grid
        debug_frame.grid_columnconfigure(0, weight=1)
        debug_frame.grid_rowconfigure(0, weight=1)
        
        # Create text widget and scrollbar using grid
        self.debug_text = tk.Text(debug_frame)
        self.debug_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(debug_frame, command=self.debug_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.debug_text.configure(yscrollcommand=scrollbar.set)

    def _create_preset_panels(self):
        """Create both preset configuration panels"""
        # Container for both preset panels
        preset_container = ttk.Frame(self)
        preset_container.grid(row=1, column=2, rowspan=2, sticky="nsew", padx=10, pady=5)
        
        # Pairs Preset Panel
        self.pair_preset_frame = self._create_preset_panel(
            preset_container, 
            "SC/FDD Pair Presets",
            self._save_pair_preset,
            self._load_pair_preset,
            self._delete_pair_preset
        )
        self.pair_preset_frame.pack(fill="both", expand=True, pady=5)
        
        # ENB Preset Panel
        self.enb_preset_frame = self._create_preset_panel(
            preset_container,
            "eNB Presets", 
            self._save_enb_preset,
            self._load_enb_preset,
            self._delete_enb_preset
        )
        self.enb_preset_frame.pack(fill="both", expand=True, pady=5)

    def _create_preset_panel(self, parent, title, save_cmd, load_cmd, delete_cmd):
        """Create individual preset panel with controls"""
        frame = ttk.LabelFrame(parent, text=title, padding="10")
        
        # Create listbox
        listbox = tk.Listbox(frame, height=5, width=30)
        listbox.pack(fill="both", expand=True, pady=5)
        
        # Button frame
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill="x", pady=5)
        
        # Add buttons
        ttk.Button(btn_frame, text="Save", command=save_cmd).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Load", command=load_cmd).pack(side="left", padx=2)
        ttk.Button(btn_frame, text="Delete", command=delete_cmd).pack(side="left", padx=2)
        
        frame.listbox = listbox  # Store reference to listbox
        return frame

    def _initialize_presets(self):
        """Load both preset types"""
        self.pair_presets = self._load_presets("pair_presets.json")
        self.enb_presets = self._load_presets("enb_presets.json")
        self._update_preset_lists()

    def _load_pair_preset(self):
        """Load selected SC/FDD pair preset"""
        selection = self.pair_preset_frame.listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a preset to load")
            return
            
        preset_name = self.pair_preset_frame.listbox.get(selection[0])
        pairs = self.pair_presets.get(preset_name)
        if not pairs:
            return
            
        # Enable FDD mode
        self.show_fdd.set(True)
        self._toggle_fdd_visibility()
        
        # Clear existing entries
        for sc_var, fdd_var in self.pairs:
            sc_var.set("")
            fdd_var.set("")
        
        # Load preset pairs
        for i, (sc, fdd) in enumerate(pairs):
            if i < len(self.pairs):
                self.pairs[i][0].set(sc)
                self.pairs[i][1].set(fdd)
                
        self.log_debug(f"Loaded pair preset: {preset_name}")
    
    def _load_enb_preset(self):
        """Load selected eNB preset"""
        selection = self.enb_preset_frame.listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a preset to load")
            return
            
        preset_name = self.enb_preset_frame.listbox.get(selection[0])
        enb = self.enb_presets.get(preset_name)
        if not enb:
            return
            
        # Disable FDD mode
        self.show_fdd.set(False)
        self._toggle_fdd_visibility()
        
        # Set eNB value
        self.enb_entry.delete(0, tk.END)
        self.enb_entry.insert(0, enb)
        self.log_debug(f"Loaded eNB preset: {preset_name}")
    
    def _delete_pair_preset(self):
        """Delete selected SC/FDD pair preset"""
        selection = self.pair_preset_frame.listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a preset to delete")
            return
            
        preset_name = self.pair_preset_frame.listbox.get(selection[0])
        if messagebox.askyesno("Confirm Delete", f"Delete preset '{preset_name}'?"):
            del self.pair_presets[preset_name]
            self._save_presets_to_file("pair_presets.json", self.pair_presets)
            self._update_preset_lists()
            self.log_debug(f"Deleted pair preset: {preset_name}")
    
    def _delete_enb_preset(self):
        """Delete selected eNB preset"""
        selection = self.enb_preset_frame.listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a preset to delete")
            return
            
        preset_name = self.enb_preset_frame.listbox.get(selection[0])
        if messagebox.askyesno("Confirm Delete", f"Delete preset '{preset_name}'?"):
            del self.enb_presets[preset_name]
            self._save_presets_to_file("enb_presets.json", self.enb_presets)
            self._update_preset_lists()
            self.log_debug(f"Deleted eNB preset: {preset_name}")

    def _update_preset_list(self, listbox: tk.Listbox, presets: dict):
        """Update a preset listbox with sorted preset names"""
        # Clear existing items
        listbox.delete(0, tk.END)
        
        # Sort and insert preset names
        sorted_names = sorted(presets.keys())
        for name in sorted_names:
            listbox.insert(tk.END, name)
    
    def _update_preset_lists(self):
        """Update both preset listboxes"""
        self._update_preset_list(self.pair_preset_frame.listbox, self.pair_presets)
        self._update_preset_list(self.enb_preset_frame.listbox, self.enb_presets)

    def _save_presets_to_file(self, filename: str, data: dict):
        """Save presets to specified file"""
        path = os.path.expanduser(f'~/.config/vz_spectral_analyzer/{filename}')
        try:
            with open(path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save presets: {str(e)}")

    # Implement separate handlers for each preset type
    def _save_pair_preset(self):
        """Save current SC/FDD pairs"""
        name = simpledialog.askstring("Save Pair Preset", "Enter preset name:")
        if not name:
            return
            
        pairs = []
        for sc_var, fdd_var in self.pairs:
            sc = sc_var.get().strip()
            fdd = fdd_var.get().strip()
            if fdd:
                pairs.append((sc, fdd))
                
        if not pairs:
            messagebox.showwarning("Warning", "No pairs to save")
            return
            
        self.pair_presets[name] = pairs
        self._save_presets_to_file("pair_presets.json", self.pair_presets)
        self._update_preset_lists()

    def _save_enb_preset(self):
        """Save current eNB"""
        name = simpledialog.askstring("Save ENB Preset", "Enter preset name:")
        if not name:
            return
            
        enb = self.enb_entry.get().strip()
        if not enb:
            messagebox.showwarning("Warning", "No eNB to save")
            return
            
        self.enb_presets[name] = enb
        self._save_presets_to_file("enb_presets.json", self.enb_presets)
        self._update_preset_lists()

    # Add similar implementations for _load_pair_preset, _load_enb_preset, 
    # _delete_pair_preset, and _delete_enb_preset

    def fill_debug_preset(self):
        """Fill debug credentials and auto-connect to SANE"""
        # Set debug credentials in SANE
        self.sane.username = self.DEBUG_USERNAME
        self.sane.password = self.DEBUG_PASSWORD
        self.log_debug("Debug credentials loaded")
        
        # Fill first sector/FDD pair
        self.pairs[0][0].set(self.DEBUG_SC)
        self.pairs[0][1].set(self.DEBUG_FDD)
        self.log_debug("Debug sector/FDD pair loaded")
        
        # Initiate SANE connection
        self.log_debug("Initiating debug SANE connection...")
        connected, ssh = self.sane.sane_authentication(True)
        
        if connected:
            self.status_var.set("\nConnected to SANE")
            self.log_debug("Debug connection successful")
            messagebox.showinfo("Success", "Connected to SANE")
        else:
            self.log_debug("Debug connection failed")
            messagebox.showerror("Error", "Failed to connect to SANE")

    def log_debug(self, message: str):
        """Log debug message"""
        timestamp = time.strftime("%H:%M:%S")
        self.debug_text.insert("end", f"[{timestamp}] {message}\n")
        self.debug_text.see("end")
        self.master.update()

    def connect(self):
        """Connect to SANE"""
        self.log_debug("Connecting to SANE...")
        connected, ssh = self.sane.sane_authentication()
        if connected:
            self.status_var.set("\nCONNECTED")
            self.log_debug("Connected successfully")
            messagebox.showinfo("Success", "Connected to SANE")

    def validate_all_700mhz_fdds(self, pairs) -> bool:
        """Pre-validate any 700MHz carriers before main processing"""
        for _, fdd_var in pairs:
            fdd = fdd_var.get().strip()
            if fdd and not self.validate_700mhz_fdd(fdd):
                return False
        return True
    
    def validate_700mhz_fdd(self, fdd: str) -> bool:
        """
        Validate if FDD matches 700MHz pattern and get user confirmation
        Returns True if:
        - FDD doesn't match 700MHz pattern
        - FDD matches pattern and user confirms
        Returns False if:
        - FDD matches pattern and user declines
        """
        import re
        pattern = r'^\d{6}_\d_1$'
        if re.match(pattern, fdd):
            return messagebox.askyesno(
                "Confirm 700MHz Carrier",
                f"FDD {fdd} appears to be a 700MHz carrier with nonstandard numbering.\nDo you want to proceed?"
            )
        return True
    
    def _extract_enb_from_fdd(self, fdd: str) -> str:
        """Extract eNB ID from FDD string"""
        if not fdd or '_' not in fdd:
            return None
        enb_id = fdd.split('_')[0]
        return enb_id if len(enb_id) == 6 and enb_id.isdigit() else None
            
    def analyze(self):
        """Analyze sector carrier/FDD pairs with eNB"""
        if not self.sane.ssh:
            messagebox.showerror("Error", "Not connected to SANE")
            return
                
        self.log_debug("Attempting analysis...")

        # Get eNB ID - from input or FDD
        enb_id = self.enb_entry.get().strip()
        if not enb_id and self.show_fdd.get():
            # Try to derive from first valid FDD
            for _, fdd_var in self.pairs:
                fdd = fdd_var.get().strip()
                if fdd:
                    enb_id = self._extract_enb_from_fdd(fdd)
                    if enb_id:
                        break

        if not enb_id or len(enb_id) != 6 or not enb_id.isdigit():
            messagebox.showerror("Error", "Invalid or missing eNB ID format")
            return

        try:
            # Get ENM details and connect
            enm_name, neid = self.sane.get_enm_details(enb_id, True)
            self.log_debug(f"Using ENM: {enm_name}, NEID: {neid}")
            channel = self.sane.sane_select(enm_name, neid)
            
            if not self.show_fdd.get():
                # eNB only mode - no pairs needed
                self.analyzer.enb_id = enb_id
                if not self.analyzer.process_enb():
                    raise RuntimeError("Failed to process eNB")
            else:
                # Process with specific pairs
                if not self.validate_all_700mhz_fdds(self.pairs):
                    return
                    
                analysis_pairs = []
                for sc_var, fdd_var in self.pairs:
                    sc = sc_var.get().strip() if self.show_sc.get() else "*"
                    fdd = fdd_var.get().strip()
                    if fdd:
                        analysis_pairs.append((sc, fdd))
                        
                if not analysis_pairs:
                    messagebox.showerror("Error", "No valid analysis pairs")
                    return
                    
                self.analyzer.set_pairs_and_enbid(analysis_pairs, enb_id)
                if not self.analyzer.process_all_pairs():
                    raise RuntimeError("Failed to process pairs")
                
                self.master.after(100, self._restore_window_size)
                
        except Exception as e:
            self.log_debug(f"Error: {str(e)}")
            messagebox.showerror("Error", str(e))