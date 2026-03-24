# -*- coding: utf-8 -*-
"""
DigiKey to Mentor PADS 转换器 - 配置文件
包含 DigiKey CSV 列名映射、封装映射等配置
"""

# DigiKey CSV 列名映射（支持中英文）
COLUMN_MAPPINGS = {
    "part_number": [
        "Digi-Key Part Number", "Digi-Key 零件编号", "DigiKey Part Number",
        "Digi-Key Part #", "零件编号"
    ],
    "mfr_part_number": [
        "Manufacturer Part Number", "制造商零件编号", "Mfr Part Number",
        "Manufacturer Part #", "MPN"
    ],
    "manufacturer": [
        "Manufacturer", "制造商", "Mfr"
    ],
    "description": [
        "Description", "描述", "Part Description", "Desc"
    ],
    "package": [
        "Package / Case", "封装/外壳", "Package", "封装",
        "Package/Case", "Case/Package"
    ],
    "mounting_type": [
        "Mounting Type", "安装类型", "Mount Type"
    ],
    "quantity": [
        "Quantity", "数量", "Qty"
    ],
    "value": [
        "Value", "值", "Resistance", "Capacitance", "Inductance",
        "电阻", "电容", "电感"
    ],
    "tolerance": [
        "Tolerance", "容差", "容许偏差"
    ],
    "voltage_rating": [
        "Voltage - Rated", "额定电压", "Voltage Rating", "Voltage"
    ],
    "category": [
        "Category", "类别", "Part Category"
    ],
}

# DigiKey 封装名到标准封装名的映射
PACKAGE_NORMALIZE = {
    # 无源器件 - 公制/英制
    "0201 (0603 Metric)": "0201",
    "0402 (1005 Metric)": "0402",
    "0603 (1608 Metric)": "0603",
    "0805 (2012 Metric)": "0805",
    "1206 (3216 Metric)": "1206",
    "1210 (3225 Metric)": "1210",
    "1812 (4532 Metric)": "1812",
    "2010 (5025 Metric)": "2010",
    "2512 (6332 Metric)": "2512",
    "0201": "0201",
    "0402": "0402",
    "0603": "0603",
    "0805": "0805",
    "1206": "1206",
    "1210": "1210",
    "1812": "1812",
    "2010": "2010",
    "2512": "2512",

    # SOT 系列
    "SOT-23": "SOT23",
    "SOT-23-3": "SOT23",
    "SOT-23-5": "SOT23-5",
    "SOT-23-6": "SOT23-6",
    "SOT-223": "SOT223",
    "SOT-223-4": "SOT223",
    "SOT-363": "SOT363",
    "SC-70": "SC70",
    "SC-70-5": "SC70-5",
    "SC-70-6": "SC70-6",

    # SOIC 系列
    "8-SOIC": "SOIC8",
    "SOIC-8": "SOIC8",
    "8-SOIC (0.154\", 3.90mm Width)": "SOIC8",
    "14-SOIC": "SOIC14",
    "SOIC-14": "SOIC14",
    "16-SOIC": "SOIC16",
    "SOIC-16": "SOIC16",

    # SOP/SSOP/TSSOP/MSOP
    "8-TSSOP": "TSSOP8",
    "14-TSSOP": "TSSOP14",
    "16-TSSOP": "TSSOP16",
    "20-TSSOP": "TSSOP20",
    "24-TSSOP": "TSSOP24",
    "28-TSSOP": "TSSOP28",
    "8-SSOP": "SSOP8",
    "16-SSOP": "SSOP16",
    "20-SSOP": "SSOP20",
    "8-MSOP": "MSOP8",
    "10-MSOP": "MSOP10",

    # QFP 系列
    "32-LQFP": "LQFP32",
    "44-LQFP": "LQFP44",
    "48-LQFP": "LQFP48",
    "64-LQFP": "LQFP64",
    "100-LQFP": "LQFP100",
    "144-LQFP": "LQFP144",
    "32-TQFP": "TQFP32",
    "44-TQFP": "TQFP44",
    "48-TQFP": "TQFP48",
    "64-TQFP": "TQFP64",
    "100-TQFP": "TQFP100",

    # QFN/DFN 系列
    "8-QFN": "QFN8",
    "16-QFN": "QFN16",
    "20-QFN": "QFN20",
    "24-QFN": "QFN24",
    "32-QFN": "QFN32",
    "40-QFN": "QFN40",
    "48-QFN": "QFN48",
    "56-QFN": "QFN56",
    "64-QFN": "QFN64",
    "8-DFN": "DFN8",
    "10-DFN": "DFN10",

    # DIP 系列
    "8-DIP": "DIP8",
    "14-DIP": "DIP14",
    "16-DIP": "DIP16",
    "18-DIP": "DIP18",
    "20-DIP": "DIP20",
    "24-DIP": "DIP24",
    "28-DIP": "DIP28",
    "40-DIP": "DIP40",

    # 二极管/晶体管封装
    "DO-214AC (SMA)": "SMA",
    "DO-214AA (SMB)": "SMB",
    "DO-214AB (SMC)": "SMC",
    "DO-35": "DO35",
    "DO-41": "DO41",
    "TO-220": "TO220",
    "TO-220-3": "TO220",
    "TO-252 (DPAK)": "DPAK",
    "TO-263 (D2PAK)": "D2PAK",
    "TO-92": "TO92",
    "TO-92-3": "TO92",

    # 电解电容
    "Radial": "RADIAL",
    "Radial, Can": "RADIAL",

    # BGA
    "BGA-256": "BGA256",
    "BGA-484": "BGA484",
}

# 元件类别前缀识别
CATEGORY_PREFIXES = {
    "R": ["Resistor", "电阻", "Res"],
    "C": ["Capacitor", "电容", "Cap"],
    "L": ["Inductor", "电感", "Ind", "Ferrite"],
    "D": ["Diode", "二极管", "LED"],
    "Q": ["Transistor", "晶体管", "MOSFET", "BJT"],
    "U": ["IC", "集成电路", "Microcontroller", "MCU", "Amplifier",
          "Regulator", "Converter", "Interface", "Memory", "FPGA",
          "Processor", "Driver", "Sensor"],
    "Y": ["Crystal", "Oscillator", "晶振", "振荡器"],
    "J": ["Connector", "连接器", "Header", "Jack", "Plug", "Socket"],
    "F": ["Fuse", "保险丝"],
    "SW": ["Switch", "开关"],
}

# PADS 库版本标识
PADS_DECAL_HEADER = "*PADS-LIBRARY-PCB-DECALS-V9*"
PADS_PART_HEADER = "*PADS-LIBRARY-PART-TYPES-V9*"
PADS_LINE_HEADER = "*PADS-LIBRARY-LINE-ITEMS-V9*"

# 默认单位: METRIC (mm)
DEFAULT_UNITS = "METRIC"
