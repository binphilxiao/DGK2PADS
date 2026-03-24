# -*- coding: utf-8 -*-
"""
DigiKey CSV 解析器
支持解析 DigiKey 导出的 CSV/Excel 元件列表
"""

import csv
import os
import re
from config import COLUMN_MAPPINGS, PACKAGE_NORMALIZE, CATEGORY_PREFIXES


class Component:
    """表示一个电子元件"""

    def __init__(self):
        self.digikey_pn = ""
        self.mfr_pn = ""
        self.manufacturer = ""
        self.series = ""
        self.description = ""
        self.package_raw = ""
        self.package = ""           # 标准化后的封装名
        self.mounting_type = ""
        self.quantity = 1
        self.value = ""
        self.tolerance = ""
        self.voltage_rating = ""
        self.power_rating = ""
        self.temp_coeff = ""
        self.operating_temp = ""
        self.category = ""
        self.ref_prefix = "U"       # 参考符号前缀 (R, C, L, U, etc.)
        self.pads_part_name = ""    # PADS 中的元件名
        self.pads_decal_name = ""   # PADS 中的封装名
        self.pin_count = 2          # 引脚数量

    def __repr__(self):
        return f"Component({self.mfr_pn}, {self.package}, {self.ref_prefix})"


def _find_column(headers, field_name):
    """根据 COLUMN_MAPPINGS 查找对应的列索引"""
    candidates = COLUMN_MAPPINGS.get(field_name, [])
    for i, h in enumerate(headers):
        h_stripped = h.strip().strip('\ufeff')  # 去除 BOM 和空白
        for candidate in candidates:
            if h_stripped.lower() == candidate.lower():
                return i
    return -1


def _normalize_package(raw_package):
    """将 DigiKey 封装名标准化为通用封装名"""
    if not raw_package:
        return ""

    raw = raw_package.strip()

    # 直接查找映射表
    if raw in PACKAGE_NORMALIZE:
        return PACKAGE_NORMALIZE[raw]

    # 尝试不区分大小写匹配
    raw_lower = raw.lower()
    for key, value in PACKAGE_NORMALIZE.items():
        if key.lower() == raw_lower:
            return value

    # 尝试正则提取常见模式
    # 匹配 "XX-SOIC", "XX-QFN" 等
    m = re.match(r'(\d+)[-\s]*(SOIC|TSSOP|SSOP|MSOP|QFN|DFN|LQFP|TQFP|QFP|DIP|SOP)',
                 raw, re.IGNORECASE)
    if m:
        count = m.group(1)
        pkg_type = m.group(2).upper()
        return f"{pkg_type}{count}"

    # 匹配 0402/0603 等无源封装（纯数字4位）
    m = re.match(r'^(\d{4})(?:\s|$|\()', raw)
    if m:
        return m.group(1)

    # 返回清理后的原始名称（去除特殊字符）
    cleaned = re.sub(r'[^A-Za-z0-9_-]', '_', raw)
    return cleaned[:20] if cleaned else "UNKNOWN"


def _detect_ref_prefix(component):
    """根据描述和类别检测参考符号前缀"""
    text = f"{component.description} {component.category}".lower()

    for prefix, keywords in CATEGORY_PREFIXES.items():
        for kw in keywords:
            if kw.lower() in text:
                return prefix
    return "U"


def _detect_pin_count(component):
    """根据封装推测引脚数量"""
    pkg = component.package

    # 无源 2端子器件
    two_pin = ["0201", "0402", "0603", "0805", "1206", "1210",
               "1812", "2010", "2512", "SMA", "SMB", "SMC",
               "DO35", "DO41", "RADIAL"]
    if pkg in two_pin:
        return 2

    # SOT 系列
    if pkg == "SOT23":
        return 3
    if pkg in ("SOT23-5", "SC70-5"):
        return 5
    if pkg in ("SOT23-6", "SC70-6", "SOT363"):
        return 6
    if pkg == "SOT223":
        return 4

    # TO 系列
    if pkg in ("TO92", "TO220", "DPAK"):
        return 3
    if pkg == "D2PAK":
        return 3

    # 提取数字后缀
    m = re.search(r'(\d+)$', pkg)
    if m:
        return int(m.group(1))

    return 2


def parse_digikey_csv(filepath, encoding=None):
    """
    解析 DigiKey 导出的 CSV 文件

    Args:
        filepath: CSV 文件路径
        encoding: 文件编码，默认自动检测

    Returns:
        list[Component]: 元件列表
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")

    # 自动检测编码
    if encoding is None:
        for enc in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'latin-1']:
            try:
                with open(filepath, 'r', encoding=enc) as f:
                    f.read(1024)
                encoding = enc
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        if encoding is None:
            encoding = 'utf-8'

    components = []

    with open(filepath, 'r', encoding=encoding, newline='') as f:
        # 跳过可能的空行或非数据行
        reader = csv.reader(f)
        headers = None

        for row in reader:
            if not row or all(cell.strip() == '' for cell in row):
                continue
            # 第一个非空行作为列标题
            headers = row
            break

        if headers is None:
            raise ValueError("CSV 文件为空或没有列标题")

        # 查找各列的索引
        col_map = {}
        for field in COLUMN_MAPPINGS:
            idx = _find_column(headers, field)
            if idx >= 0:
                col_map[field] = idx

        if not col_map:
            raise ValueError(
                "无法识别 DigiKey CSV 列标题。\n"
                f"找到的列标题: {headers}\n"
                "请确认是 DigiKey 导出的 CSV 文件。"
            )

        # 解析数据行
        for row in reader:
            if not row or all(cell.strip() == '' for cell in row):
                continue

            comp = Component()

            def get_val(field):
                idx = col_map.get(field, -1)
                if 0 <= idx < len(row):
                    return row[idx].strip()
                return ""

            comp.digikey_pn = get_val("part_number")
            comp.mfr_pn = get_val("mfr_part_number")
            comp.manufacturer = get_val("manufacturer")
            comp.description = get_val("description")
            comp.package_raw = get_val("package")
            comp.mounting_type = get_val("mounting_type")
            comp.value = get_val("value")
            comp.tolerance = get_val("tolerance")
            comp.voltage_rating = get_val("voltage_rating")
            comp.category = get_val("category")

            qty_str = get_val("quantity")
            try:
                comp.quantity = int(qty_str) if qty_str else 1
            except ValueError:
                comp.quantity = 1

            # 标准化封装名
            comp.package = _normalize_package(comp.package_raw)

            # 检测参考前缀
            comp.ref_prefix = _detect_ref_prefix(comp)

            # 检测引脚数量
            comp.pin_count = _detect_pin_count(comp)

            # 生成 PADS 名称
            if comp.mfr_pn:
                # 清理特殊字符，PADS 名称不支持空格和特殊符号
                safe_name = re.sub(r'[^A-Za-z0-9_.-]', '_', comp.mfr_pn)
                comp.pads_part_name = safe_name[:40]
            else:
                safe_name = re.sub(r'[^A-Za-z0-9_.-]', '_',
                                   comp.digikey_pn or "UNKNOWN")
                comp.pads_part_name = safe_name[:40]

            comp.pads_decal_name = comp.package if comp.package else "UNKNOWN"

            if comp.mfr_pn or comp.digikey_pn:
                components.append(comp)

    return components


def group_by_package(components):
    """按封装分组"""
    groups = {}
    for comp in components:
        pkg = comp.package or "UNKNOWN"
        if pkg not in groups:
            groups[pkg] = []
        groups[pkg].append(comp)
    return groups


def group_by_category(components):
    """按类别前缀分组"""
    groups = {}
    for comp in components:
        prefix = comp.ref_prefix
        if prefix not in groups:
            groups[prefix] = []
        groups[prefix].append(comp)
    return groups
