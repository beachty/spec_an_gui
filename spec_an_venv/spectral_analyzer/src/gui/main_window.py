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
        # Initialize frame
        super().__init__(master)
        self.master = master
        self.master.title("VZ Spectral Analyzer GUI")
        
        # Set minimum window size
        self.master.minsize(800, 600)
        
        # Initialize attributes
        self.presets = {}
        
        # Configure main frame
        self.grid(row=0, column=0, sticky="nsew")
        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        
        # Configure frame grid
        self.grid_columnconfigure(0, weight=3)  # Input section
        self.grid_columnconfigure(1, weight=0)  # Separator
        self.grid_columnconfigure(2, weight=1)  # Preset section
        
        # Configure row weights
        self.grid_rowconfigure(1, weight=1)  # Input/Preset area
        self.grid_rowconfigure(4, weight=1)  # Debug area
        
        # Setup components - Reordered
        self._create_preset_panel()  # Create preset panel first
        self._create_debug_frame()
        self._create_status_bar()
        self._create_input_frame()
        self._create_controls()
        
        # Initialize SANE with self as parent
        self.sane = SANE(self)
        self.analyzer = SpectralAnalyzer(self.sane)

        # Schedule preset loading after window is drawn
        self.master.after(100, self._initialize_presets)

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
        # Create container frame for centering
        container = ttk.Frame(self)
        container.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=20)
        container.columnconfigure(0, weight=1)  # Left margin
        container.columnconfigure(2, weight=1)  # Right margin
        
        # Create input frame centered in container
        input_frame = ttk.LabelFrame(container, text="Input Pairs", padding="10")
        input_frame.grid(row=0, column=1, sticky="nsew")
        
        # Headers
        ttk.Label(input_frame, text="Sector Carrier").grid(row=0, column=0, padx=10)
        ttk.Label(input_frame, text="FDD").grid(row=0, column=1, padx=10)
        
        # Entry pairs
        self.pairs = []
        for i in range(5):
            sc_var = tk.StringVar()
            fdd_var = tk.StringVar()
            ttk.Entry(input_frame, textvariable=sc_var, width=15).grid(row=i+1, column=0, padx=10, pady=4)
            ttk.Entry(input_frame, textvariable=fdd_var, width=15).grid(row=i+1, column=1, padx=10, pady=4)
            self.pairs.append((sc_var, fdd_var))
            
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

    def _create_preset_panel(self):
        """Create preset configuration panel"""
        preset_frame = ttk.LabelFrame(self, text="Saved Presets", padding="10")
        preset_frame.grid(row=1, column=2, rowspan=2, sticky="nsew", padx=10, pady=5)
        
        # Create listbox for presets
        self.preset_listbox = tk.Listbox(preset_frame, height=10, width=30)
        self.preset_listbox.pack(fill="both", expand=True, pady=5)
        
        # Create buttons
        btn_frame = ttk.Frame(preset_frame)
        btn_frame.pack(fill="x", pady=5)
        
        ttk.Button(btn_frame, text="Save Current", command=self._save_preset).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Load Selected", command=self._load_preset).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Delete", command=self._delete_preset).pack(side="left", padx=5)

    def _load_presets(self):
        """Load presets from JSON file"""
        # expand user directory
        path = os.path.expanduser('~/.config/vz_spectral_analyzer/presets.json')
        try:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    presets = json.load(f)
                    self._update_preset_list()
                    return presets
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load presets: {str(e)}")
        return {}
    
    def _initialize_presets(self):
        """Load and display presets after window is drawn"""
        self.presets = self._load_presets()
        self._update_preset_list()
            
    def _save_preset(self):
        """Save current pairs as new preset"""
        name = simpledialog.askstring("Save Preset", "Enter preset name:")
        if not name:
            return
            
        pairs = []
        for sc_var, fdd_var in self.pairs:
            sc = sc_var.get().strip()
            fdd = fdd_var.get().strip()
            if sc and fdd:
                pairs.append((sc, fdd))
                
        if not pairs:
            messagebox.showwarning("Warning", "No pairs to save")
            return
            
        self.presets[name] = pairs
        self._save_presets_to_file()
        self._update_preset_list()
        
    def _load_preset(self):
        """Load selected preset into input fields"""
        selection = self.preset_listbox.curselection()
        if not selection:
            return
            
        name = self.preset_listbox.get(selection[0])
        pairs = self.presets.get(name, [])
        
        # Clear current entries
        for sc_var, fdd_var in self.pairs:
            sc_var.set('')
            fdd_var.set('')
            
        # Fill with preset values
        for i, (sc, fdd) in enumerate(pairs):
            if i < len(self.pairs):
                self.pairs[i][0].set(sc)
                self.pairs[i][1].set(fdd)
                
    def _delete_preset(self):
        """Delete selected preset"""
        selection = self.preset_listbox.curselection()
        if not selection:
            return
            
        name = self.preset_listbox.get(selection[0])
        if messagebox.askyesno("Confirm", f"Delete preset '{name}'?"):
            del self.presets[name]
            self._save_presets_to_file()
            self._update_preset_list()
            
    def _update_preset_list(self):
        """Update preset listbox contents"""
        self.preset_listbox.delete(0, tk.END)
        for name in sorted(self.presets.keys()):
            self.preset_listbox.insert(tk.END, name)
            
    def _save_presets_to_file(self):
        """Save presets to JSON file"""
        # expand user
        os.makedirs(os.path.expanduser('~/.config/vz_spectral_analyzer'), exist_ok=True)
        # construct path
        path = os.path.expanduser('~/.config/vz_spectral_analyzer/presets.json')
        try:
            with open(path, 'w') as f:
                json.dump(self.presets, f)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save presets: {str(e)}")

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
            self.status_var.set("\nConnected to SANE")
            self.log_debug("Connected successfully")
            messagebox.showinfo("Success", "Connected to SANE")
        
    def analyze(self):
        """Analyze sector carrier/FDD pairs"""
        if not self.sane.ssh:
            messagebox.showerror("Error", "Not connected to SANE")
            return
            
        self.log_debug("Starting analysis...")

        sector_cell_pairs = []
        
        # Collect and validate all pairs
        for sc_var, fdd_var in self.pairs:
            sc = sc_var.get().strip()
            fdd = fdd_var.get().strip()
            
            if not sc and not fdd:
                continue
                
            if not sc or not fdd:
                messagebox.showerror("Error", "Both Sector Carrier and FDD required")
                return
                
            try:
                enb_id = fdd.split('_')[0]
                if not (enb_id and len(enb_id) == 6 and enb_id.isdigit()):
                    raise ValueError(f"Invalid eNB ID format in FDD: {fdd}")
            except Exception as e:
                messagebox.showerror("Error", str(e))
                return
                
            sector_cell_pairs.append((sc, fdd))
            
        if not sector_cell_pairs:
            messagebox.showerror("Error", "No valid sector carrier/FDD pairs entered")
            return

        try:
            # Get ENM details from first pair (all pairs should be same ENB)
            enm_name, neid = self.sane.get_enm_details(enb_id, True)
            self.log_debug(f"Using ENM: {enm_name}, NEID: {neid}")
            
            # Connect to ENM once with proper name
            channel = self.sane.sane_select(enm_name, neid)
            
            # Pass pairs and enbid to analyzer
            self.analyzer.set_pairs_and_enbid(sector_cell_pairs, enb_id)
            if not self.analyzer.process_all_pairs():
                raise RuntimeError("Failed to process one or more sector-cell pairs")
                
        except Exception as e:
            self.log_debug(f"Error: {str(e)}")
            messagebox.showerror("Error", str(e))
            return

