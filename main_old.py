# -*- coding: utf-8 -*-
"""
DigiKey to Mentor PADS 元件库转换器
主程序 - 提供 tkinter GUI 界面

功能:
1. 选择 DigiKey 导出的 CSV 文件
2. 预览解析到的元件列表
3. 选择输出格式和路径
4. 执行转换并显示结果
"""

import os
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import threading

from digikey_parser import parse_digikey_csv, group_by_package
from pads_generator import convert_digikey_to_pads
from footprint_lib import get_all_footprint_names


class Application(tk.Tk):
    """主应用程序窗口"""

    def __init__(self):
        super().__init__()

        self.title("DigiKey → Mentor PADS 元件库转换器")
        self.geometry("900x700")
        self.minsize(700, 500)

        # 数据
        self.csv_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.output_name = tk.StringVar(value="digikey_library")
        self.output_format = tk.StringVar(value="combined")
        self.components = []

        self._create_widgets()
        self._center_window()

    def _center_window(self):
        """窗口居中"""
        self.update_idletasks()
        w = self.winfo_width()
        h = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (w // 2)
        y = (self.winfo_screenheight() // 2) - (h // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """创建界面组件"""
        # === 顶部: 文件选择 ===
        frame_input = ttk.LabelFrame(self, text="输入设置", padding=10)
        frame_input.pack(fill=tk.X, padx=10, pady=(10, 5))

        # CSV 文件选择
        ttk.Label(frame_input, text="DigiKey CSV 文件:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(frame_input, textvariable=self.csv_path, width=60).grid(
            row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Button(frame_input, text="浏览...", command=self._browse_csv).grid(
            row=0, column=2, padx=5)
        ttk.Button(frame_input, text="解析预览", command=self._parse_csv).grid(
            row=0, column=3, padx=5)

        frame_input.columnconfigure(1, weight=1)

        # === 中间: 预览表格 ===
        frame_preview = ttk.LabelFrame(self, text="元件预览", padding=5)
        frame_preview.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 树形表格
        columns = ("mfr_pn", "manufacturer", "description", "package_raw",
                    "package", "ref", "pins")
        self.tree = ttk.Treeview(frame_preview, columns=columns, show="headings",
                                 selectmode="extended")

        self.tree.heading("mfr_pn", text="制造商料号")
        self.tree.heading("manufacturer", text="制造商")
        self.tree.heading("description", text="描述")
        self.tree.heading("package_raw", text="原始封装")
        self.tree.heading("package", text="匹配封装")
        self.tree.heading("ref", text="参考前缀")
        self.tree.heading("pins", text="引脚数")

        self.tree.column("mfr_pn", width=130, minwidth=80)
        self.tree.column("manufacturer", width=100, minwidth=60)
        self.tree.column("description", width=200, minwidth=100)
        self.tree.column("package_raw", width=120, minwidth=60)
        self.tree.column("package", width=80, minwidth=60)
        self.tree.column("ref", width=50, minwidth=40)
        self.tree.column("pins", width=50, minwidth=40)

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

        # 统计标签
        self.lbl_stats = ttk.Label(frame_preview, text="等待加载 CSV 文件...")
        self.lbl_stats.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5, 0))

        # === 输出设置 ===
        frame_output = ttk.LabelFrame(self, text="输出设置", padding=10)
        frame_output.pack(fill=tk.X, padx=10, pady=5)

        # 输出目录
        ttk.Label(frame_output, text="输出目录:").grid(
            row=0, column=0, sticky=tk.W, padx=(0, 5))
        ttk.Entry(frame_output, textvariable=self.output_dir, width=60).grid(
            row=0, column=1, sticky=tk.EW, padx=5)
        ttk.Button(frame_output, text="浏览...",
                    command=self._browse_output).grid(row=0, column=2, padx=5)

        # 输出文件名
        ttk.Label(frame_output, text="文件名前缀:").grid(
            row=1, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))
        ttk.Entry(frame_output, textvariable=self.output_name, width=30).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=(5, 0))

        # 输出格式
        ttk.Label(frame_output, text="输出格式:").grid(
            row=2, column=0, sticky=tk.W, padx=(0, 5), pady=(5, 0))

        frame_fmt = ttk.Frame(frame_output)
        frame_fmt.grid(row=2, column=1, sticky=tk.W, padx=5, pady=(5, 0))

        ttk.Radiobutton(frame_fmt, text="合并文件 (.asc)",
                        variable=self.output_format,
                        value="combined").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(frame_fmt, text="分别文件 (.d + .p)",
                        variable=self.output_format,
                        value="separate").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(frame_fmt, text="两者都输出",
                        variable=self.output_format,
                        value="both").pack(side=tk.LEFT)

        frame_output.columnconfigure(1, weight=1)

        # === 底部: 操作按钮和日志 ===
        frame_bottom = ttk.Frame(self, padding=10)
        frame_bottom.pack(fill=tk.X, padx=10, pady=(0, 10))

        ttk.Button(frame_bottom, text="开始转换",
                    command=self._convert, style="Accent.TButton").pack(
            side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame_bottom, text="查看支持的封装",
                    command=self._show_footprints).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(frame_bottom, text="退出",
                    command=self.quit).pack(side=tk.RIGHT)

        # 进度条
        self.progress = ttk.Progressbar(frame_bottom, mode="indeterminate",
                                        length=200)
        self.progress.pack(side=tk.LEFT, padx=10)

    def _browse_csv(self):
        """浏览选择 CSV 文件"""
        path = filedialog.askopenfilename(
            title="选择 DigiKey CSV 文件",
            filetypes=[
                ("CSV 文件", "*.csv"),
                ("所有文件", "*.*"),
            ]
        )
        if path:
            self.csv_path.set(path)
            # 自动设置输出目录为 CSV 所在目录
            if not self.output_dir.get():
                self.output_dir.set(os.path.dirname(path))

    def _browse_output(self):
        """浏览选择输出目录"""
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.output_dir.set(path)

    def _parse_csv(self):
        """解析 CSV 文件并显示预览"""
        csv_path = self.csv_path.get().strip()
        if not csv_path:
            messagebox.showwarning("提示", "请先选择 DigiKey CSV 文件")
            return

        if not os.path.isfile(csv_path):
            messagebox.showerror("错误", f"文件不存在:\n{csv_path}")
            return

        try:
            self.components = parse_digikey_csv(csv_path)
        except Exception as e:
            messagebox.showerror("解析错误", f"无法解析 CSV 文件:\n{e}")
            return

        # 清空表格
        for item in self.tree.get_children():
            self.tree.delete(item)

        # 填充数据
        matched = 0
        for comp in self.components:
            from footprint_lib import get_footprint
            fp = get_footprint(comp.package)
            pkg_status = comp.package if fp else f"{comp.package} (?)"
            if fp:
                matched += 1

            self.tree.insert("", tk.END, values=(
                comp.mfr_pn,
                comp.manufacturer,
                comp.description[:60],
                comp.package_raw,
                pkg_status,
                comp.ref_prefix,
                comp.pin_count,
            ))

        # 更新统计
        total = len(self.components)
        groups = group_by_package(self.components)
        self.lbl_stats.config(
            text=f"共 {total} 个元件, {len(groups)} 种封装, "
                 f"精确匹配: {matched}, 需生成通用封装: {total - matched}"
        )

        if not self.output_dir.get():
            self.output_dir.set(os.path.dirname(csv_path))

    def _convert(self):
        """执行转换"""
        if not self.components:
            # 先尝试解析
            self._parse_csv()
            if not self.components:
                messagebox.showwarning("提示", "没有可转换的元件数据")
                return

        output_dir = self.output_dir.get().strip()
        if not output_dir:
            messagebox.showwarning("提示", "请选择输出目录")
            return

        base_name = self.output_name.get().strip() or "digikey_library"
        fmt = self.output_format.get()

        # 在后台线程执行转换
        self.progress.start(10)

        def do_convert():
            try:
                files, summary = convert_digikey_to_pads(
                    self.components, output_dir, base_name, fmt
                )
                self.after(0, lambda: self._on_convert_done(files, summary))
            except Exception as e:
                self.after(0, lambda: self._on_convert_error(str(e)))

        thread = threading.Thread(target=do_convert, daemon=True)
        thread.start()

    def _on_convert_done(self, files, summary):
        """转换完成回调"""
        self.progress.stop()

        # 显示结果
        result_win = tk.Toplevel(self)
        result_win.title("转换结果")
        result_win.geometry("600x500")

        text = scrolledtext.ScrolledText(result_win, wrap=tk.WORD, font=("Consolas", 10))
        text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        text.insert(tk.END, summary + "\n\n")
        text.insert(tk.END, "输出文件:\n")
        for f in files:
            text.insert(tk.END, f"  {f}\n")
        text.insert(tk.END, "\n提示: 在 PADS Layout 中使用 File → Library → "
                    "Import Library 导入 .asc 文件\n")
        text.insert(tk.END, "或者分别在 PADS Layout 和 PADS Logic 中导入 "
                    ".d 和 .p 文件\n")
        text.config(state=tk.DISABLED)

        ttk.Button(result_win, text="打开输出目录",
                   command=lambda: os.startfile(
                       self.output_dir.get())).pack(pady=5)
        ttk.Button(result_win, text="关闭",
                   command=result_win.destroy).pack(pady=(0, 10))

    def _on_convert_error(self, error_msg):
        """转换出错回调"""
        self.progress.stop()
        messagebox.showerror("转换错误", f"转换过程中出错:\n{error_msg}")

    def _show_footprints(self):
        """显示支持的封装列表"""
        fp_win = tk.Toplevel(self)
        fp_win.title("支持的标准封装")
        fp_win.geometry("400x500")

        ttk.Label(fp_win, text="以下是内置支持的标准封装:",
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
                  text=f"共 {len(names)} 个内置封装。未匹配的封装将自动生成通用封装。").pack(
            padx=10, pady=(0, 10))


def main():
    """主入口"""
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
