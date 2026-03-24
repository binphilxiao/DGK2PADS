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
        self.geometry("1050x800")
        self.minsize(850, 650)

        # Data
        self.components = []
        self.all_api_components = []  # unfiltered API results
        self.api_client = None
        self.api_products_raw = []

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
        self.api_max_results = tk.IntVar(value=50)
        self.api_manufacturer_var = tk.StringVar()
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

        columns = ("mfr_pn", "manufacturer", "description", "package_raw",
                    "package", "ref", "pins", "value")
        self.tree = ttk.Treeview(frame_preview, columns=columns, show="headings",
                                 selectmode="extended", height=10)

        self.tree.heading("mfr_pn", text="MFR P/N")
        self.tree.heading("manufacturer", text="Manufacturer")
        self.tree.heading("description", text="Description")
        self.tree.heading("package_raw", text="Raw Package")
        self.tree.heading("package", text="Matched Pkg")
        self.tree.heading("ref", text="Ref")
        self.tree.heading("pins", text="Pins")
        self.tree.heading("value", text="Value")

        self.tree.column("mfr_pn", width=140, minwidth=80)
        self.tree.column("manufacturer", width=100, minwidth=60)
        self.tree.column("description", width=200, minwidth=100)
        self.tree.column("package_raw", width=130, minwidth=60)
        self.tree.column("package", width=80, minwidth=60)
        self.tree.column("ref", width=40, minwidth=35)
        self.tree.column("pins", width=40, minwidth=35)
        self.tree.column("value", width=80, minwidth=50)

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

        ttk.Label(frame_search, text="Max Results:").grid(
            row=row, column=2, sticky=tk.W, padx=(20, 5))
        ttk.Spinbox(frame_search, from_=10, to=500, increment=10,
                     textvariable=self.api_max_results, width=8).grid(
            row=row, column=3, sticky=tk.W, padx=5)

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

        preset_name = self.combo_preset.get()
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

    def _api_search(self):
        """Execute API search"""
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

        # Append manufacturer name to keyword so API returns
        # manufacturer-biased results (API has no name-based mfr filter)
        mfr_name = self.api_manufacturer_var.get().strip()
        if mfr_name:
            search_keyword = f"{keyword} {mfr_name}"
        else:
            search_keyword = keyword

        max_results = self.api_max_results.get()

        self.progress.start(10)
        self.lbl_progress.config(text="Searching...")
        self.lbl_api_status.config(text="Searching...", foreground="orange")

        def do_search():
            try:
                client._ensure_auth()

                def on_progress(current, total):
                    self.after(0, lambda c=current, t=total:
                               self.lbl_progress.config(
                                   text=f"Fetched {c}/{t} results..."))

                products = client.search_all(
                    search_keyword,
                    max_results=max_results,
                    category_id=category_id,
                    progress_callback=on_progress,
                )

                components = convert_api_results(products)
                self.after(0, lambda: self._on_api_search_done(
                    products, components))

            except DigiKeyAPIError as e:
                self.after(0, lambda err=str(e): self._on_api_search_fail(err))

        threading.Thread(target=do_search, daemon=True).start()

    def _on_api_search_done(self, products, components):
        """API search completed - auto-apply filters and show results"""
        self.progress.stop()
        self.lbl_progress.config(text="")

        self.api_products_raw = products
        self.all_api_components = components  # save unfiltered

        # Auto-apply client-side filters (manufacturer, parameters, etc.)
        filtered = self._filter_components(components)
        self.components = filtered

        # Detect sandbox dummy data
        if (self.api_use_sandbox.get() and len(components) <= 1):
            self.lbl_api_status.config(
                text=f"Done: {len(components)} result(s). "
                     f"Sandbox has very limited data. "
                     f"Uncheck 'Sandbox' for real results.",
                foreground="orange")
        elif len(filtered) < len(components):
            # Show filter step diagnostics
            filter_detail = ""
            if hasattr(self, '_filter_log') and self._filter_log:
                filter_detail = "  |  " + ", ".join(self._filter_log)

            self.lbl_api_status.config(
                text=f"Done: {len(components)} found, "
                     f"{len(filtered)} after filters."
                     f"{filter_detail}",
                foreground="green" if filtered else "orange")
        else:
            self.lbl_api_status.config(
                text=f"Done: {len(components)} components found. "
                     f"Use 'Apply Filters' to narrow down.",
                foreground="green")

        self._refresh_preview()

    def _filter_components(self, components):
        """Apply client-side filters (manufacturer + parameter dropdowns)"""
        filtered = list(components)
        self._filter_log = []  # diagnostic log

        # Manufacturer filter
        mfr_filter = self.api_manufacturer_var.get().strip().lower()
        if mfr_filter:
            before = len(filtered)
            filtered = [c for c in filtered
                        if mfr_filter in c.manufacturer.lower()]
            self._filter_log.append(
                f"Manufacturer '{mfr_filter}': {before} -> {len(filtered)}")

        # Helper: check if value appears in component description
        def _in_desc(comp, val):
            return val in comp.description.lower().replace(" ", "")

        # Parameter filters
        for key, entry_info in self.api_param_entries.items():
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
    def _refresh_preview(self):
        """Refresh preview table"""
        for item in self.tree.get_children():
            self.tree.delete(item)

        matched = 0
        for comp in self.components:
            fp = get_footprint(comp.package)
            pkg_status = comp.package if fp else f"{comp.package} (?)"
            if fp:
                matched += 1

            self.tree.insert("", tk.END, values=(
                comp.mfr_pn,
                comp.manufacturer,
                (comp.description[:55] + "...") if len(comp.description) > 55
                else comp.description,
                comp.package_raw,
                pkg_status,
                comp.ref_prefix,
                comp.pin_count,
                comp.value,
            ))

        total = len(self.components)
        groups = group_by_package(self.components)
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
