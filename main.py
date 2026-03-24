# -*- coding: utf-8 -*-
"""
DigiKey to Mentor PADS Component Library Converter
Main application - tkinter GUI

Features:
1. Method 1: Select DigiKey CSV export file -> Parse -> Convert
2. Method 2: Search DigiKey API directly -> Filter -> Convert
"""

import os
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading

from digikey_parser import parse_digikey_csv, group_by_package
from pads_generator import convert_digikey_to_pads
from footprint_lib import get_all_footprint_names, get_footprint
from digikey_api import (
    DigiKeyClient, DigiKeyAPIError,
    SEARCH_PRESETS, DIGIKEY_CATEGORIES, COMMON_MANUFACTURERS,
    convert_api_results, api_product_to_component,
    save_api_config, load_api_config,
)


class Application(tk.Tk):
    """Main application window"""

    def __init__(self):
        super().__init__()

        self.title("DigiKey -> Mentor PADS Library Converter")
        self.geometry("1280x900")
        self.minsize(1000, 700)

        # Data
        self.components = []
        self.all_api_components = []  # unfiltered API results
        self.api_client = None
        self.api_products_raw = []

        self._stop_event = threading.Event()

        # Common variables
        self.output_dir = tk.StringVar()
        self.output_name = tk.StringVar(value="digikey_library")
        self.output_format = tk.StringVar(value="combined")

        # CSV variables
        self.csv_path = tk.StringVar()

        # API variables
        self.api_client_id = tk.StringVar()
        self.api_client_secret = tk.StringVar()
        self.api_use_sandbox = tk.BooleanVar(value=False)
        self.api_keyword = tk.StringVar()
        self.api_category_var = tk.StringVar()
        self.api_manufacturer_var = tk.StringVar()
        self.api_series_var = tk.StringVar()
        self.api_param_entries = {}  # parameter filter widgets

        self._load_saved_config()
        self._create_widgets()
        self._center_window()

    def _load_saved_config(self):
        """Load saved API credentials"""
        config = load_api_config()
        if config:
            self.api_client_id.set(config.get("client_id", ""))
            self.api_client_secret.set(config.get("client_secret", ""))
            self.api_use_sandbox.set(config.get("use_sandbox", False))

    def _center_window(self):
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create UI widgets"""
        # === Tabs ===
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        # Tab 1: API Search
        self.tab_api = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_api, text="  DigiKey API Search  ")
        self._create_api_tab()

        # Tab 2: CSV Import
        self.tab_csv = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_csv, text="  CSV File Import  ")
        self._create_csv_tab()

        # === Component Preview Table ===
        frame_preview = ttk.LabelFrame(self, text="Component Preview", padding=5)
        frame_preview.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("mfr_pn", "manufacturer", "series", "description", "value",
                    "tolerance", "temp_coeff", "power", "operating_temp",
                    "package")
        self.tree = ttk.Treeview(frame_preview, columns=columns, show="headings",
                                 selectmode="extended", height=10)

        self.tree.heading("mfr_pn", text="MFR P/N",
                          command=lambda: self._sort_tree("mfr_pn"))
        self.tree.heading("manufacturer", text="Manufacturer",
                          command=lambda: self._sort_tree("manufacturer"))
        self.tree.heading("series", text="Series",
                          command=lambda: self._sort_tree("series"))
        self.tree.heading("description", text="Description",
                          command=lambda: self._sort_tree("description"))
        self.tree.heading("value", text="Resistance",
                          command=lambda: self._sort_tree("value"))
        self.tree.heading("tolerance", text="Tolerance",
                          command=lambda: self._sort_tree("tolerance"))
        self.tree.heading("temp_coeff", text="Temp Coeff",
                          command=lambda: self._sort_tree("temp_coeff"))
        self.tree.heading("power", text="Power (Watts)",
                          command=lambda: self._sort_tree("power"))
        self.tree.heading("operating_temp", text="Operating Temp",
                          command=lambda: self._sort_tree("operating_temp"))
        self.tree.heading("package", text="Package / Case",
                          command=lambda: self._sort_tree("package"))

        self._sort_col = None    # current sort column
        self._sort_asc = True    # current sort direction

        self.tree.column("mfr_pn", width=150, minwidth=80)
        self.tree.column("manufacturer", width=90, minwidth=60)
        self.tree.column("series", width=80, minwidth=50)
        self.tree.column("description", width=180, minwidth=100)
        self.tree.column("value", width=90, minwidth=50)
        self.tree.column("tolerance", width=70, minwidth=40)
        self.tree.column("temp_coeff", width=90, minwidth=50)
        self.tree.column("power", width=100, minwidth=50)
        self.tree.column("operating_temp", width=120, minwidth=60)
        self.tree.column("package", width=140, minwidth=60)

        scrollbar_y = ttk.Scrollbar(frame_preview, orient=tk.VERTICAL,
                                    command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(frame_preview, orient=tk.HORIZONTAL,
                                    command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set,
                            xscrollcommand=scrollbar_x.set)

        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        scrollbar_y.grid(row=0, column=1, sticky=tk.NS)
        scrollbar_x.grid(row=1, column=0, sticky=tk.EW)

        frame_preview.rowconfigure(0, weight=1)
        frame_preview.columnconfigure(0, weight=1)

        self.lbl_stats = ttk.Label(frame_preview,
                                   text="Waiting for component data...")
        self.lbl_stats.grid(row=2, column=0, columnspan=2, sticky=tk.W,
                            pady=(3, 0))

        # === Output Settings ===
        frame_output = ttk.LabelFrame(self, text="Output Settings", padding=8)
        frame_output.pack(fill=tk.X, padx=10, pady=3)

        ttk.Label(frame_output, text="Output Dir:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(frame_output, textvariable=self.output_dir, width=55).grid(
            row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Button(frame_output, text="Browse...",
                    command=self._browse_output).grid(row=0, column=2, padx=5)

        ttk.Label(frame_output, text="Filename:").grid(
            row=0, column=3, sticky=tk.W, padx=(15, 5))
        ttk.Entry(frame_output, textvariable=self.output_name, width=20).grid(
            row=0, column=4, sticky=tk.W, padx=5)

        frame_fmt = ttk.Frame(frame_output)
        frame_fmt.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(5, 0))

        ttk.Label(frame_fmt, text="Format:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Radiobutton(frame_fmt, text="Combined (.asc)",
                        variable=self.output_format,
                        value="combined").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(frame_fmt, text="Separate (.d + .p)",
                        variable=self.output_format,
                        value="separate").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(frame_fmt, text="Both",
                        variable=self.output_format,
                        value="both").pack(side=tk.LEFT)

        frame_output.columnconfigure(1, weight=1)

        # === Bottom Buttons ===
        frame_bottom = ttk.Frame(self, padding=8)
        frame_bottom.pack(fill=tk.X, padx=10, pady=(0, 8))

        ttk.Button(frame_bottom, text="Generate PADS Library",
                    command=self._convert).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame_bottom, text="View Supported Footprints",
                    command=self._show_footprints).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame_bottom, text="Quit",
                    command=self.quit).pack(side=tk.RIGHT)

        self.progress = ttk.Progressbar(frame_bottom, mode="indeterminate",
                                        length=200)
        self.progress.pack(side=tk.LEFT, padx=10)

        self.lbl_progress = ttk.Label(frame_bottom, text="")
        self.lbl_progress.pack(side=tk.LEFT)

    # ============================================================
    # API Search Tab
    # ============================================================
    def _create_api_tab(self):
        """Create API search tab"""
        container = ttk.Frame(self.tab_api, padding=5)
        container.pack(fill=tk.BOTH, expand=True)

        # --- API Credentials ---
        frame_auth = ttk.LabelFrame(
            container, text="API Authentication (developer.digikey.com)",
            padding=8)
        frame_auth.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(frame_auth, text="Client ID:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(frame_auth, textvariable=self.api_client_id, width=45).grid(
            row=0, column=1, sticky=tk.EW, padx=5)

        ttk.Label(frame_auth, text="Client Secret:").grid(
            row=0, column=2, sticky=tk.W, padx=(15, 5))
        ttk.Entry(frame_auth, textvariable=self.api_client_secret, width=45,
                  show="*").grid(row=0, column=3, sticky=tk.EW, padx=5)

        ttk.Checkbutton(frame_auth, text="Sandbox",
                        variable=self.api_use_sandbox).grid(
            row=0, column=4, padx=(10, 0))

        ttk.Button(frame_auth, text="Save",
                    command=self._save_credentials).grid(
            row=0, column=5, padx=(10, 0))

        # Login button row
        ttk.Button(frame_auth, text="Login to DigiKey (Browser Auth)",
                    command=self._api_login).grid(
            row=1, column=0, sticky=tk.W, pady=(8, 0))

        self.lbl_login_status = ttk.Label(
            frame_auth, text="Not logged in", foreground="gray")
        self.lbl_login_status.grid(
            row=1, column=1, columnspan=4, sticky=tk.W, padx=(10, 0),
            pady=(8, 0))

        ttk.Label(frame_auth,
                  text="Note: Set your DigiKey App Callback URL to "
                       "http://localhost:8139/callback",
                  foreground="gray").grid(
            row=2, column=0, columnspan=6, sticky=tk.W, pady=(5, 0))

        frame_auth.columnconfigure(1, weight=1)
        frame_auth.columnconfigure(3, weight=1)

        # --- Search Settings ---
        frame_search = ttk.LabelFrame(container, text="Search Options",
                                      padding=8)
        frame_search.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Component type preset
        row = 0
        ttk.Label(frame_search, text="Component Preset:").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5))

        preset_names = ["(Custom Search)"] + list(SEARCH_PRESETS.keys())
        self.combo_preset = ttk.Combobox(frame_search, values=preset_names,
                                         state="readonly", width=30)
        self.combo_preset.set("Chip Resistor")
        self.combo_preset.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.combo_preset.bind("<<ComboboxSelected>>", self._on_preset_changed)

        # Keyword
        row += 1
        ttk.Label(frame_search, text="Search Keywords:").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        ttk.Entry(frame_search, textvariable=self.api_keyword, width=50).grid(
            row=row, column=1, columnspan=3, sticky=tk.EW, padx=5, pady=(5, 0))

        # Category dropdown
        row += 1
        ttk.Label(frame_search, text="DigiKey Category:").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        cat_names = ["(Any / By Keyword)"] + list(DIGIKEY_CATEGORIES.keys())
        self.combo_category = ttk.Combobox(frame_search, values=cat_names,
                                           state="readonly", width=40)
        self.combo_category.set("(Any / By Keyword)")
        self.combo_category.grid(row=row, column=1, columnspan=3, sticky=tk.W,
                                  padx=5, pady=(5, 0))

        # Manufacturer dropdown
        row += 1
        ttk.Label(frame_search, text="Manufacturer:").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.combo_manufacturer = ttk.Combobox(
            frame_search, textvariable=self.api_manufacturer_var,
            values=COMMON_MANUFACTURERS, width=40)
        self.combo_manufacturer.set("")
        self.combo_manufacturer.grid(row=row, column=1, columnspan=3,
                                      sticky=tk.W, padx=5, pady=(5, 0))

        # Series dropdown (shown for resistors)
        row += 1
        self.lbl_series = ttk.Label(frame_search, text="Series:")
        self.lbl_series.grid(row=row, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        self.combo_series = ttk.Combobox(
            frame_search, textvariable=self.api_series_var,
            values=[], width=40)
        self.combo_series.set("")
        self.combo_series.grid(row=row, column=1, columnspan=3,
                               sticky=tk.W, padx=5, pady=(5, 0))
        # Initially hidden
        self.lbl_series.grid_remove()
        self.combo_series.grid_remove()

        # Parameter filter area
        row += 1
        ttk.Separator(frame_search, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=4, sticky=tk.EW, pady=8)

        row += 1
        ttk.Label(frame_search, text="Parameter Filters (blank = any):",
                  font=("", 9, "bold")).grid(
            row=row, column=0, columnspan=4, sticky=tk.W)

        # Parameter widgets container (dynamically generated)
        row += 1
        self.frame_params = ttk.Frame(frame_search)
        self.frame_params.grid(row=row, column=0, columnspan=4, sticky=tk.NSEW,
                                pady=(5, 0))

        frame_search.columnconfigure(1, weight=1)
        frame_search.rowconfigure(row, weight=1)

        # Initialize preset parameters
        self._on_preset_changed(None)

        # Search buttons
        frame_btn = ttk.Frame(container)
        frame_btn.pack(fill=tk.X)

        ttk.Button(frame_btn, text="Search DigiKey",
                    command=self._api_search).pack(side=tk.LEFT, padx=(0, 10))
        self.btn_stop = ttk.Button(frame_btn, text="Stop Fetch",
                                    command=self._stop_search, state=tk.DISABLED)
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame_btn, text="Test Connection",
                    command=self._api_test).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame_btn, text="Apply Filters",
                    command=self._apply_client_filters).pack(
            side=tk.LEFT, padx=(0, 10))

        self.lbl_api_status = ttk.Label(frame_btn, text="", foreground="gray")
        self.lbl_api_status.pack(side=tk.LEFT, padx=10)

    def _on_preset_changed(self, event):
        """Update parameter panel when preset changes"""
        # Clear existing parameter widgets
        for widget in self.frame_params.winfo_children():
            widget.destroy()
        self.api_param_entries.clear()

        # Show/hide Series dropdown based on preset
        preset_name = self.combo_preset.get()
        if preset_name == "Chip Resistor":
            from digikey_api import COMMON_RESISTOR_SERIES
            self.combo_series.config(values=COMMON_RESISTOR_SERIES)
            self.lbl_series.grid()
            self.combo_series.grid()
        else:
            self.api_series_var.set("")
            self.lbl_series.grid_remove()
            self.combo_series.grid_remove()
        if preset_name in SEARCH_PRESETS:
            config = SEARCH_PRESETS[preset_name]
            self.api_keyword.set(config["keyword"])

            # Set category
            cat_name = config["category_name"]
            if cat_name in DIGIKEY_CATEGORIES:
                self.combo_category.set(cat_name)

            # Create parameter dropdown widgets
            for i, param in enumerate(config["parameters"]):
                ttk.Label(self.frame_params, text=param["name"] + ":").grid(
                    row=i, column=0, sticky=tk.W, padx=(0, 5), pady=2)

                var = tk.StringVar()
                combo = ttk.Combobox(self.frame_params, textvariable=var,
                                     values=param.get("values", []),
                                     width=25)
                combo.set("")
                combo.grid(row=i, column=1, sticky=tk.W, padx=5, pady=2)

                self.api_param_entries[param["key"]] = {
                    "var": var,
                    "param_id": param["param_id"],
                    "name": param["name"],
                }

            self.frame_params.columnconfigure(1, weight=1)
        else:
            self.api_keyword.set("")
            self.combo_category.set("(Any / By Keyword)")

    def _get_api_client(self):
        """Get or create API client"""
        client_id = self.api_client_id.get().strip()
        client_secret = self.api_client_secret.get().strip()

        if not client_id or not client_secret:
            raise DigiKeyAPIError(
                "Please enter DigiKey API credentials "
                "(Client ID and Client Secret).\n\n"
                "How to get them:\n"
                "1. Go to https://developer.digikey.com\n"
                "2. Register / Log in to developer account\n"
                "3. Create an app to get Client ID and Secret\n"
                "4. Subscribe to Product Information V4 API"
            )

        if (self.api_client is None or
                self.api_client.client_id != client_id or
                self.api_client.client_secret != client_secret):
            self.api_client = DigiKeyClient(
                client_id, client_secret,
                use_sandbox=self.api_use_sandbox.get()
            )

        return self.api_client

    def _save_credentials(self):
        """Save API credentials"""
        cid = self.api_client_id.get().strip()
        csecret = self.api_client_secret.get().strip()
        if cid and csecret:
            save_api_config(cid, csecret, self.api_use_sandbox.get())
            messagebox.showinfo("Info", "API credentials saved.")
        else:
            messagebox.showwarning("Warning",
                                   "Please enter Client ID and Client Secret.")

    def _api_login(self):
        """Perform DigiKey OAuth login via browser"""
        try:
            client = self._get_api_client()
        except DigiKeyAPIError as e:
            messagebox.showerror("Error", str(e))
            return

        # Check if already logged in with valid token
        if client.access_token and time.time() < client.token_expires_at:
            self.lbl_login_status.config(
                text="Logged in (token valid)", foreground="green")
            return

        self.lbl_login_status.config(text="Opening browser...",
                                     foreground="orange")
        self.update_idletasks()

        def do_login():
            try:
                client.authenticate()
                self.after(0, lambda: self.lbl_login_status.config(
                    text="Login successful", foreground="green"))
            except DigiKeyAPIError as e:
                self.after(0, lambda err=str(e): self._on_login_fail(err))

        threading.Thread(target=do_login, daemon=True).start()

    def _on_login_fail(self, err):
        self.lbl_login_status.config(text="Login failed", foreground="red")
        messagebox.showerror(
            "DigiKey Login Failed",
            f"OAuth authorization failed:\n\n{err}\n\n"
            f"Please verify:\n"
            f"1. DigiKey App Callback URL is set to:\n"
            f"   http://localhost:8139/callback\n"
            f"2. Client ID and Secret are correct\n"
            f"3. Product Information V4 API is subscribed")

    def _api_test(self):
        """Test API connection (must be logged in first)"""
        try:
            client = self._get_api_client()
        except DigiKeyAPIError as e:
            messagebox.showerror("Error", str(e))
            return

        if not client.access_token:
            messagebox.showinfo("Info",
                                "Please click 'Login to DigiKey' first.")
            return

        self.lbl_api_status.config(text="Testing...", foreground="orange")
        self.update_idletasks()

        def do_test():
            try:
                client._ensure_auth()
                self.after(0, lambda: self._on_api_test_ok())
            except DigiKeyAPIError as e:
                self.after(0, lambda err=str(e): self._on_api_test_fail(err))

        threading.Thread(target=do_test, daemon=True).start()

    def _on_api_test_ok(self):
        self.lbl_api_status.config(text="Connection OK", foreground="green")

    def _on_api_test_fail(self, err):
        self.lbl_api_status.config(text="Connection failed", foreground="red")
        messagebox.showerror("API Connection Failed",
                             f"Cannot connect to DigiKey API:\n\n{err}")

    def _build_search_keyword(self):
        """Build base search keyword (without filter terms, those go to API filters)."""
        return self.api_keyword.get().strip()

    def _match_filter_value(self, user_val, available_values):
        """Match a user-selected filter value to an API ValueId.
        available_values: {value_text_lower: value_id}
        Returns matched value_id or None.
        """
        val_lower = user_val.lower().strip()
        # Exact match
        if val_lower in available_values:
            return available_values[val_lower]
        # Try with ± prefix for tolerance values (user "1%" -> "±1%")
        if val_lower and not val_lower.startswith('±'):
            prefixed = '±' + val_lower
            if prefixed in available_values:
                return available_values[prefixed]
        # Substring match on comma-separated alternatives
        # e.g., user "1/10W" matches "0.1w, 1/10w"
        best_match = None
        best_len = float('inf')
        for vname, vid in available_values.items():
            # Check each comma-separated part
            parts = [p.strip() for p in vname.split(',')]
            for part in parts:
                if val_lower == part:
                    return vid  # exact match on a part
            # Prefix match: "0603" matches "0603 (1608 metric)"
            if vname.startswith(val_lower + ' ') or vname.startswith(val_lower + '('):
                if len(vname) < best_len:
                    best_match = vid
                    best_len = len(vname)
            # Check if user value appears as standalone in the name
            if val_lower in vname and len(vname) < best_len:
                # Avoid false positives: "1%" matching "0.1%"
                # Only match if val appears at word boundary
                import re
                if re.search(r'(?:^|[\s,±])' + re.escape(val_lower) + r'(?:$|[\s,)])', vname):
                    best_match = vid
                    best_len = len(vname)
        return best_match

    def _api_search(self):
        """Execute API search with server-side filtering (two-phase)"""
        try:
            client = self._get_api_client()
        except DigiKeyAPIError as e:
            messagebox.showerror("Error", str(e))
            return

        keyword = self.api_keyword.get().strip()
        if not keyword:
            messagebox.showwarning("Warning", "Please enter search keywords.")
            return

        # Get category ID
        cat_name = self.combo_category.get()
        category_id = DIGIKEY_CATEGORIES.get(cat_name)

        # Collect user filter selections
        mfr_name = self.api_manufacturer_var.get().strip()
        user_param_selections = {}
        for key, entry_info in self.api_param_entries.items():
            val = entry_info["var"].get().strip()
            if val:
                user_param_selections[key] = {
                    "value": val,
                    "param_id": entry_info["param_id"],
                }

        self._stop_event.clear()
        self.btn_stop.config(state=tk.NORMAL)
        self.progress.start(10)
        self.lbl_progress.config(text="Phase 1: Discovering filters...")
        self.lbl_api_status.config(text="Searching...", foreground="orange")

        def do_search():
            try:
                client._ensure_auth()

                # Phase 1: Discover available filter IDs
                self.after(0, lambda: self.lbl_progress.config(
                    text="Phase 1: Discovering available filters..."))

                mfr_map, param_map, total_unfiltered = \
                    client.discover_filter_ids(keyword, category_id)

                # Match manufacturer
                mfr_ids = None
                mfr_matched = False
                if mfr_name:
                    mfr_lower = mfr_name.lower()
                    if mfr_lower in mfr_map:
                        mfr_ids = [mfr_map[mfr_lower]]
                        mfr_matched = True

                # Match parameter filters to API ValueIds
                api_param_filters = []
                unmatched_params = {}  # for client-side fallback
                server_matched_keys = set()  # keys handled server-side
                for key, sel in user_param_selections.items():
                    param_id = sel["param_id"]
                    val = sel["value"]
                    if param_id in param_map:
                        vid = self._match_filter_value(val, param_map[param_id])
                        if vid:
                            api_param_filters.append({
                                "ParameterId": param_id,
                                "FilterValues": [{"Id": vid}],
                            })
                            server_matched_keys.add(key)
                            continue
                    # Not matched - will do client-side
                    unmatched_params[key] = sel

                # Build search keyword: add unmatched terms to keyword
                kw_parts = [keyword]
                if mfr_name and not mfr_matched:
                    kw_parts.append(mfr_name)
                # Add series to keyword for server-side narrowing
                series_name = self.api_series_var.get().strip()
                if series_name:
                    kw_parts.append(series_name)
                for key, sel in unmatched_params.items():
                    kw_parts.append(sel["value"])
                search_keyword = " ".join(kw_parts)

                # Build info string
                filter_info_parts = []
                if mfr_matched:
                    filter_info_parts.append(f"Mfr={mfr_name}")
                if series_name:
                    filter_info_parts.append(f"Series={series_name}")
                if api_param_filters:
                    filter_info_parts.append(
                        f"{len(api_param_filters)} param filter(s)")
                if unmatched_params:
                    filter_info_parts.append(
                        f"{len(unmatched_params)} client-side")

                filter_info = ", ".join(filter_info_parts) if \
                    filter_info_parts else "keyword only"

                # Phase 2: Real search with server-side filters
                self.after(0, lambda: self.lbl_progress.config(
                    text=f"Phase 2: Fetching results ({filter_info})..."))

                # Clear table and prepare for incremental display
                skip_keys = server_matched_keys.copy()
                skip_mfr = mfr_matched
                self.after(0, lambda sk=skip_keys, sm=skip_mfr:
                           self._prepare_incremental(sk, sm))

                def on_progress(fetched, total, msg):
                    self.after(0, lambda f=fetched, t=total, m=msg:
                               self.lbl_progress.config(
                                   text=f"Fetched {f}/~{t}  {m}"))

                def on_segment(new_products):
                    """Called for each completed segment with new products"""
                    self.after(0, lambda p=new_products:
                               self._append_segment(p))

                # Determine split parameter for segmented fetching
                preset_name = self.combo_preset.get()
                preset_cfg = SEARCH_PRESETS.get(preset_name, {})
                split_param_id = preset_cfg.get("split_param_id")

                # Get all value IDs for the split parameter
                # (only if it's not already user-filtered)
                split_value_ids = None
                if split_param_id and split_param_id in param_map:
                    # Check if user already filtered on this param
                    already_filtered = any(
                        f["ParameterId"] == split_param_id
                        for f in api_param_filters
                    )
                    if not already_filtered:
                        split_value_ids = list(
                            param_map[split_param_id].values())

                products, total_filtered = client.search_all_segmented(
                    search_keyword,
                    category_id=category_id,
                    manufacturer_ids=mfr_ids,
                    parameter_filters=api_param_filters if api_param_filters
                    else None,
                    split_param_id=split_param_id,
                    split_value_ids=split_value_ids,
                    progress_callback=on_progress,
                    segment_callback=on_segment,
                    stop_flag=self._stop_event,
                )

                # Final: update status
                stopped = self._stop_event.is_set()
                self.after(0, lambda fi=filter_info, tf=total_filtered, s=stopped:
                           self._on_search_finished(fi, tf, stopped=s))

            except DigiKeyAPIError as e:
                self.after(0, lambda err=str(e): self._on_api_search_fail(err))

        threading.Thread(target=do_search, daemon=True).start()

    def _prepare_incremental(self, skip_keys, skip_mfr):
        """Clear table and prepare for incremental segment display"""
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.components = []
        self.all_api_components = []
        self.api_products_raw = []
        self._incremental_skip_keys = skip_keys
        self._incremental_skip_mfr = skip_mfr

    def _append_segment(self, new_products):
        """Append a batch of new products to the table incrementally"""
        from digikey_api import convert_api_results
        new_comps = convert_api_results(new_products)

        # Apply client-side filters on new batch
        filtered = self._filter_components(
            new_comps,
            skip_keys=getattr(self, '_incremental_skip_keys', set()),
            skip_mfr=getattr(self, '_incremental_skip_mfr', False))

        self.all_api_components.extend(new_comps)
        self.api_products_raw.extend(new_products)
        self.components.extend(filtered)

        # Append rows to table (no full refresh - just add new)
        for comp in filtered:
            self.tree.insert("", tk.END, values=(
                comp.mfr_pn,
                comp.manufacturer,
                comp.series,
                (comp.description[:55] + "...") if len(comp.description) > 55
                else comp.description,
                comp.value,
                comp.tolerance,
                comp.temp_coeff,
                comp.power_rating,
                comp.operating_temp,
                comp.package_raw,
            ))

        # Update stats
        total = len(self.components)
        groups = group_by_package(self.components)
        matched = sum(1 for c in self.components if get_footprint(c.package))
        self.lbl_stats.config(
            text=f"Total: {total} components, {len(groups)} packages, "
                 f"Matched: {matched}, Generic: {total - matched}")
        self.lbl_api_status.config(
            text=f"Fetching... {total} components so far",
            foreground="orange")

    def _stop_search(self):
        """Signal the background search thread to stop"""
        self._stop_event.set()
        self.btn_stop.config(state=tk.DISABLED)
        self.lbl_progress.config(text="Stopping...")

    def _on_search_finished(self, filter_info, total_filtered, stopped=False):
        """Called when segmented search is fully complete"""
        self.progress.stop()
        self.lbl_progress.config(text="")
        self.btn_stop.config(state=tk.DISABLED)
        total = len(self.components)
        total_all = len(self.all_api_components)

        status_prefix = "Stopped" if stopped else "Done"
        if total < total_all:
            self.lbl_api_status.config(
                text=f"{status_prefix}: {total_all} fetched (of ~{total_filtered} matching), "
                     f"{total} after client filters. [{filter_info}]",
                foreground="green" if total else "orange")
        else:
            self.lbl_api_status.config(
                text=f"{status_prefix}: {total} components "
                     f"(of ~{total_filtered} matching). [{filter_info}]",
                foreground="green")

    def _on_api_search_done(self, products, components,
                            filter_info="", total_filtered=0,
                            server_matched_keys=None,
                            server_matched_mfr=False):
        """API search completed - apply remaining client-side filters"""
        self.progress.stop()
        self.lbl_progress.config(text="")

        self.api_products_raw = products
        self.all_api_components = components  # save unfiltered

        # Auto-apply client-side filters only for params NOT already server-side
        filtered = self._filter_components(
            components,
            skip_keys=server_matched_keys or set(),
            skip_mfr=server_matched_mfr)
        self.components = filtered

        # Detect sandbox dummy data
        if (self.api_use_sandbox.get() and len(components) <= 1):
            self.lbl_api_status.config(
                text=f"Done: {len(components)} result(s). "
                     f"Sandbox has very limited data. "
                     f"Uncheck 'Sandbox' for real results.",
                foreground="orange")
        elif len(filtered) < len(components):
            self.lbl_api_status.config(
                text=f"Fetched {len(components)} (of ~{total_filtered} matching), "
                     f"{len(filtered)} after client filters. "
                     f"[{filter_info}]",
                foreground="green" if filtered else "orange")
        else:
            self.lbl_api_status.config(
                text=f"Done: {len(components)} components "
                     f"(of ~{total_filtered} matching). [{filter_info}]",
                foreground="green")

        self._refresh_preview()

    def _filter_components(self, components, skip_keys=None, skip_mfr=False):
        """Apply client-side filters (manufacturer + parameter dropdowns)
        skip_keys: set of param keys already filtered server-side
        skip_mfr: True if manufacturer was filtered server-side
        """
        if skip_keys is None:
            skip_keys = set()
        filtered = list(components)
        self._filter_log = []  # diagnostic log

        # Manufacturer filter (skip if already done server-side)
        mfr_filter = self.api_manufacturer_var.get().strip().lower()
        if mfr_filter and not skip_mfr:
            before = len(filtered)
            filtered = [c for c in filtered
                        if mfr_filter in c.manufacturer.lower()]
            self._filter_log.append(
                f"Manufacturer '{mfr_filter}': {before} -> {len(filtered)}")

        # Series filter (always client-side)
        series_filter = self.api_series_var.get().strip()
        if series_filter:
            series_lower = series_filter.lower()
            before = len(filtered)
            filtered = [c for c in filtered
                        if series_lower in c.series.lower()]
            self._filter_log.append(
                f"Series '{series_filter}': {before} -> {len(filtered)}")

        # Helper: check if value appears in component description
        def _in_desc(comp, val):
            return val in comp.description.lower().replace(" ", "")

        # Parameter filters (skip those already applied server-side)
        for key, entry_info in self.api_param_entries.items():
            if key in skip_keys:
                continue
            val = entry_info["var"].get().strip()
            if not val:
                continue

            val_lower = val.lower().replace(" ", "")
            before = len(filtered)

            if key == "package":
                filtered = [c for c in filtered
                            if val_lower in c.package_raw.lower().replace(" ", "")
                            or val_lower in c.package.lower().replace(" ", "")
                            or _in_desc(c, val_lower)]
            elif key in ("resistance", "capacitance", "inductance"):
                filtered = [c for c in filtered
                            if val_lower in c.value.lower().replace(" ", "")
                            or _in_desc(c, val_lower)]
            elif key == "tolerance":
                filtered = [c for c in filtered
                            if val_lower in c.tolerance.lower().replace(" ", "")
                            or _in_desc(c, val_lower)]
            elif key == "voltage":
                filtered = [c for c in filtered
                            if val_lower in c.voltage_rating.lower().replace(" ", "")
                            or _in_desc(c, val_lower)]
            elif key == "power_rating":
                filtered = [c for c in filtered
                            if _in_desc(c, val_lower)]
            else:
                # Generic: search in description
                filtered = [c for c in filtered
                            if _in_desc(c, val_lower)]

            self._filter_log.append(
                f"{entry_info['name']} '{val}': {before} -> {len(filtered)}")

        return filtered

    def _apply_client_filters(self):
        """Re-apply client-side filters on existing API results"""
        if not self.all_api_components:
            messagebox.showinfo("Info",
                                "No search results to filter. "
                                "Please search first.")
            return

        filtered = self._filter_components(self.all_api_components)
        self.components = filtered

        # Show filter step diagnostics if result is 0
        filter_detail = ""
        if hasattr(self, '_filter_log') and self._filter_log:
            filter_detail = "  |  " + ", ".join(self._filter_log)

        self.lbl_api_status.config(
            text=f"Filtered: {len(filtered)} components "
                 f"(of {len(self.all_api_components)} total)"
                 f"{filter_detail}",
            foreground="green" if filtered else "orange")
        self._refresh_preview()

    def _on_api_search_fail(self, error):
        """API search failed"""
        self.progress.stop()
        self.lbl_progress.config(text="")
        self.btn_stop.config(state=tk.DISABLED)
        self.lbl_api_status.config(text="Search failed", foreground="red")
        messagebox.showerror("Search Failed",
                             f"DigiKey API search error:\n\n{error}")

    # ============================================================
    # CSV Import Tab
    # ============================================================
    def _create_csv_tab(self):
        """Create CSV import tab"""
        container = ttk.Frame(self.tab_csv, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="Select DigiKey CSV export file:").pack(
            anchor=tk.W, pady=(0, 5))

        frame_file = ttk.Frame(container)
        frame_file.pack(fill=tk.X, pady=(0, 10))

        ttk.Entry(frame_file, textvariable=self.csv_path, width=70).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(frame_file, text="Browse...",
                    command=self._browse_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_file, text="Parse & Preview",
                    command=self._parse_csv).pack(side=tk.LEFT, padx=5)

        ttk.Label(container,
                  text="Note: CSV files exported from DigiKey website.\n"
                       "Export: DigiKey website -> Select components -> "
                       "Export/Download CSV",
                  foreground="gray").pack(anchor=tk.W, pady=5)

    # ============================================================
    # Common Methods
    # ============================================================
    def _sort_tree(self, col):
        """Sort treeview by column header click"""
        # Toggle direction if same column clicked again
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True

        # Get all rows with values
        items = [(self.tree.set(iid, col), iid)
                 for iid in self.tree.get_children()]

        # Sort items
        items.sort(key=lambda x: x[0].lower(), reverse=not self._sort_asc)

        # Rearrange items in treeview
        for idx, (_, iid) in enumerate(items):
            self.tree.move(iid, "", idx)

        # Update heading to show sort indicator
        col_names = {
            "mfr_pn": "MFR P/N", "manufacturer": "Manufacturer",
            "series": "Series",
            "description": "Description", "value": "Resistance",
            "tolerance": "Tolerance", "temp_coeff": "Temp Coefficient",
            "power": "Power (Watts)", "operating_temp": "Operating Temp",
            "package": "Package / Case",
        }
        for c, name in col_names.items():
            if c == col:
                arrow = " \u25b2" if self._sort_asc else " \u25bc"
                self.tree.heading(c, text=name + arrow)
            else:
                self.tree.heading(c, text=name)

    def _refresh_preview(self):
        """Refresh preview table"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        for comp in self.components:
            self.tree.insert("", tk.END, values=(
                comp.mfr_pn,
                comp.manufacturer,
                comp.series,
                (comp.description[:55] + "...") if len(comp.description) > 55
                else comp.description,
                comp.value,
                comp.tolerance,
                comp.temp_coeff,
                comp.power_rating,
                comp.operating_temp,
                comp.package_raw,
            ))

        total = len(self.components)
        groups = group_by_package(self.components)
        matched = sum(1 for c in self.components if get_footprint(c.package))
        self.lbl_stats.config(
            text=f"Total: {total} components, {len(groups)} packages, "
                 f"Matched: {matched}, Generic: {total - matched}")

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            title="Select DigiKey CSV File",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")])
        if path:
            self.csv_path.set(path)
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(path))

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select Output Directory")
        if path:
            self.output_dir.set(path)

    def _parse_csv(self):
        csv_path = self.csv_path.get().strip()
        if not csv_path:
            messagebox.showwarning("Warning", "Please select a CSV file first.")
            return
        if not os.path.isfile(csv_path):
            messagebox.showerror("Error", f"File not found:\n{csv_path}")
            return
        try:
            self.components = parse_digikey_csv(csv_path)
        except Exception as e:
            messagebox.showerror("Parse Error", f"Cannot parse CSV:\n{e}")
            return

        self._refresh_preview()

        if not self.output_dir.get():
            self.output_dir.set(os.path.dirname(csv_path))

    def _convert(self):
        """Generate PADS library files"""
        if not self.components:
            messagebox.showwarning(
                "Warning",
                "No component data to convert.\n"
                "Please search via API or import a CSV first.")
            return

        output_dir = self.output_dir.get().strip()
        if not output_dir:
            messagebox.showwarning("Warning", "Please select an output directory.")
            return

        base_name = self.output_name.get().strip() or "digikey_library"
        fmt = self.output_format.get()

        self.progress.start(10)
        self.lbl_progress.config(text="Generating...")

        def do_convert():
            try:
                files, summary = convert_digikey_to_pads(
                    self.components, output_dir, base_name, fmt)
                self.after(0, lambda: self._on_convert_done(files, summary))
            except Exception as e:
                self.after(0, lambda err=str(e): self._on_convert_error(err))

        threading.Thread(target=do_convert, daemon=True).start()

    def _on_convert_done(self, files, summary):
        self.progress.stop()
        self.lbl_progress.config(text="Done!")

        result_win = tk.Toplevel(self)
        result_win.title("Conversion Result")
        result_win.geometry("650x520")

        text = scrolledtext.ScrolledText(result_win, wrap=tk.WORD,
                                         font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text.insert(tk.END, summary + "\n\n")
        text.insert(tk.END, "Output Files:\n")
        for f in files:
            text.insert(tk.END, f"  {f}\n")
        text.insert(tk.END, "\nHow to Import:\n")
        text.insert(tk.END,
                    "  PADS Layout -> File -> Library -> Import Library\n")
        text.insert(tk.END,
                    "  Select the generated .asc / .d / .p file(s)\n")
        text.config(state=tk.DISABLED)

        btn_frame = ttk.Frame(result_win)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="Open Output Folder",
                   command=lambda: os.startfile(
                       self.output_dir.get())).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Close",
                   command=result_win.destroy).pack(side=tk.LEFT, padx=5)

    def _on_convert_error(self, error_msg):
        self.progress.stop()
        self.lbl_progress.config(text="")
        messagebox.showerror("Conversion Error",
                             f"Error during conversion:\n{error_msg}")

    def _show_footprints(self):
        fp_win = tk.Toplevel(self)
        fp_win.title("Supported Footprints")
        fp_win.geometry("400x500")

        ttk.Label(fp_win, text="Built-in Supported Footprints:",
                  font=("", 10, "bold")).pack(padx=10, pady=10)

        frame = ttk.Frame(fp_win)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        listbox = tk.Listbox(frame, font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                                  command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        names = get_all_footprint_names()
        for name in names:
            listbox.insert(tk.END, name)

        ttk.Label(
            fp_win,
            text=f"{len(names)} total. Unmatched packages get generic "
                 f"placeholder footprints.").pack(padx=10, pady=(0, 10))


def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
