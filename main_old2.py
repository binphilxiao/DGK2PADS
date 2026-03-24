# -*- coding: utf-8 -*-
"""
DigiKey to Mentor PADS 元件库转换器
主程序 - 提供 tkinter GUI 界面

功能:
1. 方式一: 选择 DigiKey 导出的 CSV 文件 → 解析 → 转换
2. 方式二: 通过 DigiKey API 直接搜索元件 → 筛选 → 转换
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
    SEARCH_PRESETS, DIGIKEY_CATEGORIES,
    convert_api_results, api_product_to_component,
    save_api_config, load_api_config,
)


class Application(tk.Tk):
    """主应用程序窗口"""

    def __init__(self):
        super().__init__()

        self.title("DigiKey → Mentor PADS 元件库转换器")
        self.geometry("1000x780")
        self.minsize(800, 600)

        # 数据
        self.components = []
        self.api_client = None
        self.api_products_raw = []  # API 原始返回

        # 公共变量
        self.output_dir = tk.StringVar()
        self.output_name = tk.StringVar(value="digikey_library")
        self.output_format = tk.StringVar(value="combined")

        # CSV 变量
        self.csv_path = tk.StringVar()

        # API 变量
        self.api_client_id = tk.StringVar()
        self.api_client_secret = tk.StringVar()
        self.api_use_sandbox = tk.BooleanVar(value=False)
        self.api_keyword = tk.StringVar()
        self.api_category_var = tk.StringVar()
        self.api_max_results = tk.IntVar(value=50)
        self.api_param_entries = {}  # 参数过滤器输入框

        self._load_saved_config()
        self._create_widgets()
        self._center_window()

    def _load_saved_config(self):
        """加载已保存的 API 配置"""
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
        """创建界面"""
        # === 顶部标签页 ===
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        # Tab 1: API 搜索
        self.tab_api = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_api, text="  DigiKey API 搜索  ")
        self._create_api_tab()

        # Tab 2: CSV 导入
        self.tab_csv = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_csv, text="  CSV 文件导入  ")
        self._create_csv_tab()

        # === 公共区域: 元件预览表格 ===
        frame_preview = ttk.LabelFrame(self, text="元件预览", padding=5)
        frame_preview.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        columns = ("mfr_pn", "manufacturer", "description", "package_raw",
                    "package", "ref", "pins", "value")
        self.tree = ttk.Treeview(frame_preview, columns=columns, show="headings",
                                 selectmode="extended", height=10)

        self.tree.heading("mfr_pn", text="制造商料号")
        self.tree.heading("manufacturer", text="制造商")
        self.tree.heading("description", text="描述")
        self.tree.heading("package_raw", text="原始封装")
        self.tree.heading("package", text="匹配封装")
        self.tree.heading("ref", text="前缀")
        self.tree.heading("pins", text="引脚")
        self.tree.heading("value", text="值")

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

        self.lbl_stats = ttk.Label(frame_preview, text="等待加载元件数据...")
        self.lbl_stats.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(3, 0))

        # === 输出设置 ===
        frame_output = ttk.LabelFrame(self, text="输出设置", padding=8)
        frame_output.pack(fill=tk.X, padx=10, pady=3)

        ttk.Label(frame_output, text="输出目录:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(frame_output, textvariable=self.output_dir, width=55).grid(
            row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Button(frame_output, text="浏览...",
                    command=self._browse_output).grid(row=0, column=2, padx=5)

        ttk.Label(frame_output, text="文件名:").grid(
            row=0, column=3, sticky=tk.W, padx=(15, 5))
        ttk.Entry(frame_output, textvariable=self.output_name, width=20).grid(
            row=0, column=4, sticky=tk.W, padx=5)

        frame_fmt = ttk.Frame(frame_output)
        frame_fmt.grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(5, 0))

        ttk.Label(frame_fmt, text="格式:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Radiobutton(frame_fmt, text="合并 (.asc)",
                        variable=self.output_format,
                        value="combined").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(frame_fmt, text="分别 (.d + .p)",
                        variable=self.output_format,
                        value="separate").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Radiobutton(frame_fmt, text="两者都输出",
                        variable=self.output_format,
                        value="both").pack(side=tk.LEFT)

        frame_output.columnconfigure(1, weight=1)

        # === 底部按钮 ===
        frame_bottom = ttk.Frame(self, padding=8)
        frame_bottom.pack(fill=tk.X, padx=10, pady=(0, 8))

        ttk.Button(frame_bottom, text="生成 PADS 库文件",
                    command=self._convert).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame_bottom, text="查看支持的封装",
                    command=self._show_footprints).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame_bottom, text="退出",
                    command=self.quit).pack(side=tk.RIGHT)

        self.progress = ttk.Progressbar(frame_bottom, mode="indeterminate",
                                        length=200)
        self.progress.pack(side=tk.LEFT, padx=10)

        self.lbl_progress = ttk.Label(frame_bottom, text="")
        self.lbl_progress.pack(side=tk.LEFT)

    # ============================================================
    # API 搜索标签页
    # ============================================================
    def _create_api_tab(self):
        """创建 API 搜索标签页"""
        container = ttk.Frame(self.tab_api, padding=5)
        container.pack(fill=tk.BOTH, expand=True)

        # --- API 凭据 ---
        frame_auth = ttk.LabelFrame(container, text="API 认证 (developer.digikey.com)", padding=8)
        frame_auth.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(frame_auth, text="Client ID:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(frame_auth, textvariable=self.api_client_id, width=45).grid(
            row=0, column=1, sticky=tk.EW, padx=5)

        ttk.Label(frame_auth, text="Client Secret:").grid(
            row=0, column=2, sticky=tk.W, padx=(15, 5))
        ttk.Entry(frame_auth, textvariable=self.api_client_secret, width=45,
                  show="*").grid(row=0, column=3, sticky=tk.EW, padx=5)

        ttk.Checkbutton(frame_auth, text="Sandbox 模式",
                        variable=self.api_use_sandbox).grid(
            row=0, column=4, padx=(10, 0))

        ttk.Button(frame_auth, text="保存凭据",
                    command=self._save_credentials).grid(
            row=0, column=5, padx=(10, 0))

        # 登录按钮行
        ttk.Button(frame_auth, text="登录 DigiKey (浏览器授权)",
                    command=self._api_login).grid(
            row=1, column=0, columnspan=2, sticky=tk.W, pady=(8, 0))

        self.lbl_login_status = ttk.Label(
            frame_auth, text="未登录", foreground="gray")
        self.lbl_login_status.grid(
            row=1, column=1, columnspan=2, sticky=tk.W, padx=(10, 0), pady=(8, 0))

        ttk.Label(frame_auth,
                  text="提示: DigiKey App 的 Callback URL 需设为 http://localhost:8139/callback",
                  foreground="gray").grid(
            row=2, column=0, columnspan=6, sticky=tk.W, pady=(5, 0))

        frame_auth.columnconfigure(1, weight=1)
        frame_auth.columnconfigure(3, weight=1)

        # --- 搜索设置 ---
        frame_search = ttk.LabelFrame(container, text="搜索条件", padding=8)
        frame_search.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # 元件类型预设
        row = 0
        ttk.Label(frame_search, text="元件类型预设:").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5))

        preset_names = ["(自定义搜索)"] + list(SEARCH_PRESETS.keys())
        self.combo_preset = ttk.Combobox(frame_search, values=preset_names,
                                         state="readonly", width=30)
        self.combo_preset.set("电阻 (Chip Resistor)")
        self.combo_preset.grid(row=row, column=1, sticky=tk.W, padx=5)
        self.combo_preset.bind("<<ComboboxSelected>>", self._on_preset_changed)

        ttk.Label(frame_search, text="最大结果数:").grid(
            row=row, column=2, sticky=tk.W, padx=(20, 5))
        ttk.Spinbox(frame_search, from_=10, to=500, increment=10,
                     textvariable=self.api_max_results, width=8).grid(
            row=row, column=3, sticky=tk.W, padx=5)

        # 关键字
        row += 1
        ttk.Label(frame_search, text="搜索关键字:").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        ttk.Entry(frame_search, textvariable=self.api_keyword, width=50).grid(
            row=row, column=1, columnspan=3, sticky=tk.EW, padx=5, pady=(5, 0))

        # 类别下拉
        row += 1
        ttk.Label(frame_search, text="DigiKey 类别:").grid(
            row=row, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        cat_names = ["(不限/由关键字决定)"] + list(DIGIKEY_CATEGORIES.keys())
        self.combo_category = ttk.Combobox(frame_search, values=cat_names,
                                           state="readonly", width=40)
        self.combo_category.set("(不限/由关键字决定)")
        self.combo_category.grid(row=row, column=1, columnspan=3, sticky=tk.W,
                                  padx=5, pady=(5, 0))

        # 参数过滤器区域
        row += 1
        ttk.Separator(frame_search, orient=tk.HORIZONTAL).grid(
            row=row, column=0, columnspan=4, sticky=tk.EW, pady=8)

        row += 1
        ttk.Label(frame_search, text="参数过滤 (留空表示不限):",
                  font=("", 9, "bold")).grid(
            row=row, column=0, columnspan=4, sticky=tk.W)

        # 参数输入框容器 (动态生成)
        row += 1
        self.frame_params = ttk.Frame(frame_search)
        self.frame_params.grid(row=row, column=0, columnspan=4, sticky=tk.NSEW,
                                pady=(5, 0))

        frame_search.columnconfigure(1, weight=1)
        frame_search.rowconfigure(row, weight=1)

        # 初始化预设参数
        self._on_preset_changed(None)

        # 搜索按钮
        frame_btn = ttk.Frame(container)
        frame_btn.pack(fill=tk.X)

        ttk.Button(frame_btn, text="搜索 DigiKey",
                    command=self._api_search).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame_btn, text="测试连接",
                    command=self._api_test).pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_api_status = ttk.Label(frame_btn, text="", foreground="gray")
        self.lbl_api_status.pack(side=tk.LEFT, padx=10)

    def _on_preset_changed(self, event):
        """预设更改时更新参数面板"""
        # 清空现有参数输入框
        for widget in self.frame_params.winfo_children():
            widget.destroy()
        self.api_param_entries.clear()

        preset_name = self.combo_preset.get()
        if preset_name in SEARCH_PRESETS:
            config = SEARCH_PRESETS[preset_name]
            self.api_keyword.set(config["keyword"])

            # 设置类别
            cat_name = config["category_name"]
            if cat_name in DIGIKEY_CATEGORIES:
                self.combo_category.set(cat_name)

            # 创建参数输入框
            for i, param in enumerate(config["parameters"]):
                ttk.Label(self.frame_params, text=param["name"] + ":").grid(
                    row=i, column=0, sticky=tk.W, padx=(0, 5), pady=2)

                var = tk.StringVar()
                entry = ttk.Entry(self.frame_params, textvariable=var, width=40)
                entry.grid(row=i, column=1, sticky=tk.EW, padx=5, pady=2)

                ttk.Label(self.frame_params, text=param["hint"],
                          foreground="gray").grid(
                    row=i, column=2, sticky=tk.W, padx=5, pady=2)

                self.api_param_entries[param["key"]] = {
                    "var": var,
                    "param_id": param["param_id"],
                    "name": param["name"],
                }

            self.frame_params.columnconfigure(1, weight=1)
        else:
            self.api_keyword.set("")
            self.combo_category.set("(不限/由关键字决定)")

    def _get_api_client(self):
        """获取或创建 API 客户端"""
        client_id = self.api_client_id.get().strip()
        client_secret = self.api_client_secret.get().strip()

        if not client_id or not client_secret:
            raise DigiKeyAPIError(
                "请先输入 DigiKey API 凭据 (Client ID 和 Client Secret)\n\n"
                "获取方式:\n"
                "1. 访问 https://developer.digikey.com\n"
                "2. 注册/登录开发者账号\n"
                "3. 创建应用获取 Client ID 和 Secret\n"
                "4. 订阅 Product Information V4 API"
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
        """保存 API 凭据"""
        cid = self.api_client_id.get().strip()
        csecret = self.api_client_secret.get().strip()
        if cid and csecret:
            save_api_config(cid, csecret, self.api_use_sandbox.get())
            messagebox.showinfo("提示", "API 凭据已保存")
        else:
            messagebox.showwarning("提示", "请输入 Client ID 和 Client Secret")

    def _api_login(self):
        """通过浏览器进行 DigiKey OAuth 登录"""
        try:
            client = self._get_api_client()
        except DigiKeyAPIError as e:
            messagebox.showerror("错误", str(e))
            return

        # 检查是否已有有效 token
        if client.access_token and time.time() < client.token_expires_at:
            self.lbl_login_status.config(
                text="已登录 ✓ (token 有效)", foreground="green")
            return

        self.lbl_login_status.config(text="正在打开浏览器...", foreground="orange")
        self.update_idletasks()

        def do_login():
            try:
                client.authenticate()
                self.after(0, lambda: self.lbl_login_status.config(
                    text="登录成功 ✓", foreground="green"))
            except DigiKeyAPIError as e:
                self.after(0, lambda err=str(e): self._on_login_fail(err))

        threading.Thread(target=do_login, daemon=True).start()

    def _on_login_fail(self, err):
        self.lbl_login_status.config(text="登录失败 ✗", foreground="red")
        messagebox.showerror("DigiKey 登录失败",
                             f"OAuth 授权失败:\n\n{err}\n\n"
                             f"请确认:\n"
                             f"1. DigiKey App 的 Callback URL 已设为:\n"
                             f"   http://localhost:8139/callback\n"
                             f"2. Client ID 和 Secret 正确\n"
                             f"3. 已订阅 Product Information V4 API")

    def _api_test(self):
        """测试 API 连接 (先确保已登录)"""
        try:
            client = self._get_api_client()
        except DigiKeyAPIError as e:
            messagebox.showerror("错误", str(e))
            return

        if not client.access_token:
            messagebox.showinfo("提示",
                                "请先点击'登录 DigiKey'进行浏览器授权")
            return

        self.lbl_api_status.config(text="正在测试...", foreground="orange")
        self.update_idletasks()

        def do_test():
            try:
                client._ensure_auth()
                self.after(0, lambda: self._on_api_test_ok())
            except DigiKeyAPIError as e:
                self.after(0, lambda err=str(e): self._on_api_test_fail(err))

        threading.Thread(target=do_test, daemon=True).start()

    def _on_api_test_ok(self):
        self.lbl_api_status.config(text="连接成功 ✓", foreground="green")

    def _on_api_test_fail(self, err):
        self.lbl_api_status.config(text="连接失败 ✗", foreground="red")
        messagebox.showerror("API 连接失败", f"无法连接到 DigiKey API:\n\n{err}")

    def _api_search(self):
        """执行 API 搜索"""
        try:
            client = self._get_api_client()
        except DigiKeyAPIError as e:
            messagebox.showerror("错误", str(e))
            return

        keyword = self.api_keyword.get().strip()
        if not keyword:
            messagebox.showwarning("提示", "请输入搜索关键字")
            return

        # 获取类别 ID
        cat_name = self.combo_category.get()
        category_id = DIGIKEY_CATEGORIES.get(cat_name)

        # 构建参数过滤器 (将用户输入的值作为关键字补充)
        # DigiKey API 的参数过滤需要 ValueId，这些需要先查询获取
        # 简化策略: 将参数值附加到关键字中
        extra_keywords = []
        for key, entry_info in self.api_param_entries.items():
            val = entry_info["var"].get().strip()
            if val:
                extra_keywords.append(val)

        # 将参数值追加到关键字
        if extra_keywords:
            keyword = keyword + " " + " ".join(extra_keywords)

        max_results = self.api_max_results.get()

        self.progress.start(10)
        self.lbl_progress.config(text="正在搜索...")
        self.lbl_api_status.config(text="搜索中...", foreground="orange")

        def do_search():
            try:
                client._ensure_auth()

                def on_progress(current, total):
                    self.after(0, lambda c=current, t=total:
                               self.lbl_progress.config(
                                   text=f"已获取 {c}/{t} 个结果..."))

                products = client.search_all(
                    keyword,
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
        """API 搜索完成"""
        self.progress.stop()
        self.lbl_progress.config(text="")
        self.lbl_api_status.config(
            text=f"搜索完成: {len(components)} 个元件", foreground="green")

        self.api_products_raw = products
        self.components = components
        self._refresh_preview()

    def _on_api_search_fail(self, error):
        """API 搜索失败"""
        self.progress.stop()
        self.lbl_progress.config(text="")
        self.lbl_api_status.config(text="搜索失败", foreground="red")
        messagebox.showerror("搜索失败", f"DigiKey API 搜索出错:\n\n{error}")

    # ============================================================
    # CSV 导入标签页
    # ============================================================
    def _create_csv_tab(self):
        """创建 CSV 导入标签页"""
        container = ttk.Frame(self.tab_csv, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        ttk.Label(container, text="选择 DigiKey 导出的 CSV 文件:").pack(
            anchor=tk.W, pady=(0, 5))

        frame_file = ttk.Frame(container)
        frame_file.pack(fill=tk.X, pady=(0, 10))

        ttk.Entry(frame_file, textvariable=self.csv_path, width=70).pack(
            side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        ttk.Button(frame_file, text="浏览...",
                    command=self._browse_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_file, text="解析并预览",
                    command=self._parse_csv).pack(side=tk.LEFT, padx=5)

        ttk.Label(container,
                  text="说明: 从 DigiKey 网站导出的 CSV 文件，支持中英文列名。\n"
                       "导出方式: DigiKey 网站 → 选择元件 → 导出/下载 CSV",
                  foreground="gray").pack(anchor=tk.W, pady=5)

    # ============================================================
    # 公共方法
    # ============================================================
    def _refresh_preview(self):
        """刷新预览表格"""
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
            text=f"共 {total} 个元件, {len(groups)} 种封装, "
                 f"精确匹配: {matched}, 通用封装: {total - matched}")

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            title="选择 DigiKey CSV 文件",
            filetypes=[("CSV 文件", "*.csv"), ("所有文件", "*.*")])
        if path:
            self.csv_path.set(path)
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(path))

    def _browse_output(self):
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_dir.set(path)

    def _parse_csv(self):
        csv_path = self.csv_path.get().strip()
        if not csv_path:
            messagebox.showwarning("提示", "请先选择 CSV 文件")
            return
        if not os.path.isfile(csv_path):
            messagebox.showerror("错误", f"文件不存在:\n{csv_path}")
            return
        try:
            self.components = parse_digikey_csv(csv_path)
        except Exception as e:
            messagebox.showerror("解析错误", f"无法解析 CSV:\n{e}")
            return

        self._refresh_preview()

        if not self.output_dir.get():
            self.output_dir.set(os.path.dirname(csv_path))

    def _convert(self):
        """执行转换，生成 PADS 库文件"""
        if not self.components:
            messagebox.showwarning("提示", "没有可转换的元件数据。\n请先通过 API 搜索或 CSV 导入元件。")
            return

        output_dir = self.output_dir.get().strip()
        if not output_dir:
            messagebox.showwarning("提示", "请选择输出目录")
            return

        base_name = self.output_name.get().strip() or "digikey_library"
        fmt = self.output_format.get()

        self.progress.start(10)
        self.lbl_progress.config(text="正在生成...")

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
        self.lbl_progress.config(text="完成!")

        result_win = tk.Toplevel(self)
        result_win.title("转换结果")
        result_win.geometry("650x520")

        text = scrolledtext.ScrolledText(result_win, wrap=tk.WORD,
                                         font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text.insert(tk.END, summary + "\n\n")
        text.insert(tk.END, "输出文件:\n")
        for f in files:
            text.insert(tk.END, f"  {f}\n")
        text.insert(tk.END, "\n导入方式:\n")
        text.insert(tk.END, "  PADS Layout → File → Library → Import Library\n")
        text.insert(tk.END, "  选择生成的 .asc / .d / .p 文件\n")
        text.config(state=tk.DISABLED)

        btn_frame = ttk.Frame(result_win)
        btn_frame.pack(pady=8)
        ttk.Button(btn_frame, text="打开输出目录",
                   command=lambda: os.startfile(
                       self.output_dir.get())).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="关闭",
                   command=result_win.destroy).pack(side=tk.LEFT, padx=5)

    def _on_convert_error(self, error_msg):
        self.progress.stop()
        self.lbl_progress.config(text="")
        messagebox.showerror("转换错误", f"转换出错:\n{error_msg}")

    def _show_footprints(self):
        fp_win = tk.Toplevel(self)
        fp_win.title("支持的标准封装")
        fp_win.geometry("400x500")

        ttk.Label(fp_win, text="内置支持的标准封装:",
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

        ttk.Label(fp_win,
                  text=f"共 {len(names)} 个。未匹配的封装将自动生成通用占位封装。").pack(
            padx=10, pady=(0, 10))


def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
