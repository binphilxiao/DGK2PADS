# -*- coding: utf-8 -*-
"""
标准封装（Footprint/Decal）库
为 Mentor PADS 定义常用 SMD 和 through-hole 封装的几何参数

所有尺寸单位: mm (METRIC)
坐标原点在封装中心
"""


class PadDef:
    """焊盘定义"""

    def __init__(self, pin_num, x, y, width, height, shape="RF", is_smd=True):
        """
        Args:
            pin_num: 引脚编号 (1-based)
            x, y: 焊盘中心坐标 (mm)
            width: 焊盘宽度 (mm)
            height: 焊盘高度 (mm)
            shape: 焊盘形状 (RF=矩形, OF=椭圆, R=圆形, S=方形)
            is_smd: 是否为贴片焊盘
        """
        self.pin_num = pin_num
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.shape = shape
        self.is_smd = is_smd


class OutlineDef:
    """外形轮廓定义"""

    def __init__(self, points, line_width=0.15, layer=27):
        """
        Args:
            points: 轮廓点列表 [(x1,y1), (x2,y2), ...]
            line_width: 线宽 (mm)
            layer: 层号 (27=丝印层 Silkscreen)
        """
        self.points = points
        self.line_width = line_width
        self.layer = layer


class FootprintDef:
    """完整的封装定义"""

    def __init__(self, name, pads, outlines, is_smd=True):
        self.name = name
        self.pads = pads
        self.outlines = outlines
        self.is_smd = is_smd


def _make_two_pad_chip(name, pad_w, pad_h, pad_gap):
    """生成 2 端子片式器件封装 (电阻/电容/电感)"""
    half_gap = pad_gap / 2.0
    cx = half_gap + pad_w / 2.0

    pads = [
        PadDef(1, -cx, 0, pad_w, pad_h, "RF"),
        PadDef(2, cx, 0, pad_w, pad_h, "RF"),
    ]

    # 丝印外框
    total_w = pad_gap + pad_w * 2
    total_h = pad_h + 0.2
    hw = total_w / 2.0 + 0.1
    hh = total_h / 2.0

    outline = OutlineDef([
        (-hw, hh), (hw, hh), (hw, -hh), (-hw, -hh), (-hw, hh)
    ], 0.15, 27)

    return FootprintDef(name, pads, [outline], is_smd=True)


def _make_sot23(name, pin_count=3):
    """生成 SOT-23 系列封装"""
    pads = []
    outlines = []

    if pin_count == 3:
        # SOT-23-3: 引脚 1,2 在底部，引脚 3 在顶部
        pads = [
            PadDef(1, -0.95, -1.1, 0.60, 0.70, "RF"),
            PadDef(2, 0.95, -1.1, 0.60, 0.70, "RF"),
            PadDef(3, 0.0, 1.1, 0.60, 0.70, "RF"),
        ]
        outline = OutlineDef([
            (-1.5, 0.75), (1.5, 0.75), (1.5, -0.75),
            (-1.5, -0.75), (-1.5, 0.75)
        ], 0.15, 27)
        outlines = [outline]

    elif pin_count == 5:
        # SOT-23-5: 引脚 1,2,3 底部，4,5 顶部
        pads = [
            PadDef(1, -0.95, -1.1, 0.60, 0.70, "RF"),
            PadDef(2, 0.0, -1.1, 0.60, 0.70, "RF"),
            PadDef(3, 0.95, -1.1, 0.60, 0.70, "RF"),
            PadDef(4, 0.95, 1.1, 0.60, 0.70, "RF"),
            PadDef(5, -0.95, 1.1, 0.60, 0.70, "RF"),
        ]
        outline = OutlineDef([
            (-1.5, 0.75), (1.5, 0.75), (1.5, -0.75),
            (-1.5, -0.75), (-1.5, 0.75)
        ], 0.15, 27)
        outlines = [outline]

    elif pin_count == 6:
        # SOT-23-6 (SOT-363): 引脚 1,2,3 底部，4,5,6 顶部
        pads = [
            PadDef(1, -0.95, -1.1, 0.60, 0.70, "RF"),
            PadDef(2, 0.0, -1.1, 0.60, 0.70, "RF"),
            PadDef(3, 0.95, -1.1, 0.60, 0.70, "RF"),
            PadDef(4, 0.95, 1.1, 0.60, 0.70, "RF"),
            PadDef(5, 0.0, 1.1, 0.60, 0.70, "RF"),
            PadDef(6, -0.95, 1.1, 0.60, 0.70, "RF"),
        ]
        outline = OutlineDef([
            (-1.5, 0.75), (1.5, 0.75), (1.5, -0.75),
            (-1.5, -0.75), (-1.5, 0.75)
        ], 0.15, 27)
        outlines = [outline]

    return FootprintDef(name, pads, outlines, is_smd=True)


def _make_sot223(name):
    """生成 SOT-223 封装"""
    pads = [
        PadDef(1, -2.30, -3.15, 0.70, 1.50, "RF"),
        PadDef(2, 0.0, -3.15, 0.70, 1.50, "RF"),
        PadDef(3, 2.30, -3.15, 0.70, 1.50, "RF"),
        PadDef(4, 0.0, 3.15, 3.30, 1.50, "RF"),  # 散热焊盘
    ]
    outline = OutlineDef([
        (-3.5, 1.8), (3.5, 1.8), (3.5, -1.8),
        (-3.5, -1.8), (-3.5, 1.8)
    ], 0.15, 27)
    return FootprintDef(name, pads, [outline], is_smd=True)


def _make_soic(name, pin_count, pitch=1.27, body_width=3.9, pad_width=0.60,
               pad_height=1.50):
    """生成 SOIC 系列封装"""
    pads = []
    half_pins = pin_count // 2
    total_span = (half_pins - 1) * pitch
    half_span = total_span / 2.0
    pad_center_y = body_width / 2.0 + pad_height / 2.0

    for i in range(half_pins):
        x = -half_span + i * pitch
        # 底部引脚 (1 to half_pins)
        pads.append(PadDef(i + 1, x, -pad_center_y, pad_width, pad_height, "RF"))
        # 顶部引脚 (pin_count to half_pins+1)
        pads.append(PadDef(pin_count - i, x, pad_center_y, pad_width, pad_height, "RF"))

    hw = total_span / 2.0 + pitch / 2.0
    hh = body_width / 2.0
    outline = OutlineDef([
        (-hw, hh), (hw, hh), (hw, -hh), (-hw, -hh), (-hw, hh)
    ], 0.15, 27)
    # Pin 1 标记
    pin1_mark = OutlineDef([
        (-hw + 0.3, -hh + 0.8), (-hw + 0.3, -hh + 0.3),
        (-hw + 0.8, -hh + 0.3)
    ], 0.15, 27)

    return FootprintDef(name, pads, [outline, pin1_mark], is_smd=True)


def _make_tssop(name, pin_count, pitch=0.65, body_width=4.4, pad_width=0.40,
                pad_height=1.20):
    """生成 TSSOP 系列封装"""
    return _make_soic(name, pin_count, pitch, body_width, pad_width, pad_height)


def _make_ssop(name, pin_count, pitch=0.65, body_width=5.3, pad_width=0.40,
               pad_height=1.40):
    """SSOP"""
    return _make_soic(name, pin_count, pitch, body_width, pad_width, pad_height)


def _make_msop(name, pin_count, pitch=0.50, body_width=3.0, pad_width=0.30,
               pad_height=1.00):
    """MSOP"""
    return _make_soic(name, pin_count, pitch, body_width, pad_width, pad_height)


def _make_qfp(name, pin_count, pitch=0.50, body_size=7.0, pad_width=0.30,
              pad_height=1.50):
    """生成 QFP 系列封装（正方形，四面引脚）"""
    pads = []
    pins_per_side = pin_count // 4
    total_span = (pins_per_side - 1) * pitch
    half_span = total_span / 2.0
    pad_center = body_size / 2.0 + pad_height / 2.0

    pin = 1
    # 左侧 (从上到下)
    for i in range(pins_per_side):
        y = half_span - i * pitch
        pads.append(PadDef(pin, -pad_center, y, pad_height, pad_width, "RF"))
        pin += 1

    # 底部 (从左到右)
    for i in range(pins_per_side):
        x = -half_span + i * pitch
        pads.append(PadDef(pin, x, -pad_center, pad_width, pad_height, "RF"))
        pin += 1

    # 右侧 (从下到上)
    for i in range(pins_per_side):
        y = -half_span + i * pitch
        pads.append(PadDef(pin, pad_center, y, pad_height, pad_width, "RF"))
        pin += 1

    # 顶部 (从右到左)
    for i in range(pins_per_side):
        x = half_span - i * pitch
        pads.append(PadDef(pin, x, pad_center, pad_width, pad_height, "RF"))
        pin += 1

    hs = body_size / 2.0
    outline = OutlineDef([
        (-hs, hs), (hs, hs), (hs, -hs), (-hs, -hs), (-hs, hs)
    ], 0.15, 27)
    pin1_mark = OutlineDef([
        (-hs - 0.3, hs - 0.3), (-hs, hs)
    ], 0.20, 27)

    return FootprintDef(name, pads, [outline, pin1_mark], is_smd=True)


def _make_qfn(name, pin_count, pitch=0.50, body_size=5.0, pad_width=0.30,
              pad_height=0.80, exposed_pad=None):
    """生成 QFN 系列封装"""
    pads = []
    pins_per_side = pin_count // 4
    total_span = (pins_per_side - 1) * pitch
    half_span = total_span / 2.0
    pad_center = body_size / 2.0

    pin = 1
    # 底部 (从左到右)
    for i in range(pins_per_side):
        x = -half_span + i * pitch
        pads.append(PadDef(pin, x, -pad_center, pad_width, pad_height, "RF"))
        pin += 1

    # 右侧 (从下到上)
    for i in range(pins_per_side):
        y = -half_span + i * pitch
        pads.append(PadDef(pin, pad_center, y, pad_height, pad_width, "RF"))
        pin += 1

    # 顶部 (从右到左)
    for i in range(pins_per_side):
        x = half_span - i * pitch
        pads.append(PadDef(pin, x, pad_center, pad_width, pad_height, "RF"))
        pin += 1

    # 左侧 (从上到下)
    for i in range(pins_per_side):
        y = half_span - i * pitch
        pads.append(PadDef(pin, -pad_center, y, pad_height, pad_width, "RF"))
        pin += 1

    # 中心散热焊盘(可选)
    if exposed_pad:
        ep_w, ep_h = exposed_pad
        pads.append(PadDef(pin_count + 1, 0, 0, ep_w, ep_h, "RF"))

    hs = body_size / 2.0
    outline = OutlineDef([
        (-hs, hs), (hs, hs), (hs, -hs), (-hs, -hs), (-hs, hs)
    ], 0.15, 27)
    pin1_mark = OutlineDef([
        (-hs + 0.3, -hs + 0.8), (-hs + 0.3, -hs + 0.3),
        (-hs + 0.8, -hs + 0.3)
    ], 0.15, 27)

    return FootprintDef(name, pads, [outline, pin1_mark], is_smd=True)


def _make_dip(name, pin_count, pitch=2.54, row_spacing=7.62, drill=0.80,
              pad_dia=1.60):
    """生成 DIP 系列封装"""
    pads = []
    half_pins = pin_count // 2
    total_span = (half_pins - 1) * pitch
    half_span = total_span / 2.0
    half_row = row_spacing / 2.0

    pin = 1
    # 左列 (从上到下)
    for i in range(half_pins):
        y = half_span - i * pitch
        pads.append(PadDef(pin, -half_row, y, pad_dia, pad_dia, "R", is_smd=False))
        pin += 1

    # 右列 (从下到上)
    for i in range(half_pins):
        y = -half_span + i * pitch
        pads.append(PadDef(pin, half_row, y, pad_dia, pad_dia, "R", is_smd=False))
        pin += 1

    hw = row_spacing / 2.0 + 1.5
    hh = total_span / 2.0 + 1.5
    outline = OutlineDef([
        (-hw, hh), (hw, hh), (hw, -hh), (-hw, -hh), (-hw, hh)
    ], 0.15, 27)
    # Pin 1 缺口
    notch = OutlineDef([
        (-1.0, hh), (0, hh - 1.0), (1.0, hh)
    ], 0.15, 27)

    return FootprintDef(name, pads, [outline, notch], is_smd=False)


def _make_to220(name):
    """TO-220-3 封装"""
    pads = [
        PadDef(1, -2.54, 0, 1.60, 1.60, "R", is_smd=False),
        PadDef(2, 0, 0, 1.60, 1.60, "R", is_smd=False),
        PadDef(3, 2.54, 0, 1.60, 1.60, "R", is_smd=False),
    ]
    outline = OutlineDef([
        (-5.0, 5.0), (5.0, 5.0), (5.0, -5.0), (-5.0, -5.0), (-5.0, 5.0)
    ], 0.20, 27)
    return FootprintDef(name, pads, [outline], is_smd=False)


def _make_to92(name):
    """TO-92 封装"""
    pads = [
        PadDef(1, -1.27, 0, 1.20, 1.20, "R", is_smd=False),
        PadDef(2, 0, 0, 1.20, 1.20, "R", is_smd=False),
        PadDef(3, 1.27, 0, 1.20, 1.20, "R", is_smd=False),
    ]
    outline = OutlineDef([
        (-2.5, 2.0), (2.5, 2.0), (2.5, -2.0), (-2.5, -2.0), (-2.5, 2.0)
    ], 0.15, 27)
    return FootprintDef(name, pads, [outline], is_smd=False)


def _make_dpak(name):
    """DPAK (TO-252) 封装"""
    pads = [
        PadDef(1, -2.30, -3.40, 1.00, 1.50, "RF"),
        PadDef(3, 2.30, -3.40, 1.00, 1.50, "RF"),
        PadDef(2, 0, 2.00, 6.00, 5.80, "RF"),  # 散热焊盘
    ]
    outline = OutlineDef([
        (-3.5, 4.5), (3.5, 4.5), (3.5, -2.5), (-3.5, -2.5), (-3.5, 4.5)
    ], 0.15, 27)
    return FootprintDef(name, pads, [outline], is_smd=True)


def _make_d2pak(name):
    """D2PAK (TO-263) 封装"""
    pads = [
        PadDef(1, -2.54, -5.20, 1.20, 2.00, "RF"),
        PadDef(3, 2.54, -5.20, 1.20, 2.00, "RF"),
        PadDef(2, 0, 2.50, 8.00, 7.60, "RF"),  # 散热焊盘
    ]
    outline = OutlineDef([
        (-5.0, 6.0), (5.0, 6.0), (5.0, -4.0), (-5.0, -4.0), (-5.0, 6.0)
    ], 0.15, 27)
    return FootprintDef(name, pads, [outline], is_smd=True)


def _make_diode_smd(name, pad_w, pad_h, pad_gap):
    """SMD 二极管封装 (SMA/SMB/SMC)"""
    half_gap = pad_gap / 2.0
    cx = half_gap + pad_w / 2.0

    pads = [
        PadDef(1, -cx, 0, pad_w, pad_h, "RF"),  # Cathode
        PadDef(2, cx, 0, pad_w, pad_h, "RF"),    # Anode
    ]

    total_w = pad_gap + pad_w * 2
    hw = total_w / 2.0 + 0.1
    hh = pad_h / 2.0 + 0.2

    outline = OutlineDef([
        (-hw, hh), (hw, hh), (hw, -hh), (-hw, -hh), (-hw, hh)
    ], 0.15, 27)
    # 阴极标记
    cathode_mark = OutlineDef([
        (-hw + 0.5, hh), (-hw + 0.5, -hh)
    ], 0.20, 27)

    return FootprintDef(name, pads, [outline, cathode_mark], is_smd=True)


# ============================================================
# 封装库: 标准化封装名 -> FootprintDef
# ============================================================

FOOTPRINT_LIBRARY = {}


def _build_library():
    """构建标准封装库"""
    lib = {}

    # === 片式无源器件 ===
    # (name, pad_width, pad_height, pad_gap)
    chip_sizes = [
        ("0201", 0.30, 0.30, 0.30),
        ("0402", 0.50, 0.55, 0.50),
        ("0603", 0.80, 0.80, 0.80),
        ("0805", 1.00, 1.25, 1.00),
        ("1206", 1.00, 1.75, 1.80),
        ("1210", 1.00, 2.70, 1.80),
        ("1812", 1.00, 3.40, 2.80),
        ("2010", 1.00, 2.70, 3.20),
        ("2512", 1.00, 3.40, 4.20),
    ]
    for name, pw, ph, pg in chip_sizes:
        lib[name] = _make_two_pad_chip(name, pw, ph, pg)

    # === SOT 系列 ===
    lib["SOT23"] = _make_sot23("SOT23", 3)
    lib["SOT23-5"] = _make_sot23("SOT23-5", 5)
    lib["SOT23-6"] = _make_sot23("SOT23-6", 6)
    lib["SOT363"] = _make_sot23("SOT363", 6)
    lib["SC70"] = _make_sot23("SC70", 3)
    lib["SC70-5"] = _make_sot23("SC70-5", 5)
    lib["SC70-6"] = _make_sot23("SC70-6", 6)
    lib["SOT223"] = _make_sot223("SOT223")

    # === SOIC 系列 ===
    for n in [8, 14, 16]:
        lib[f"SOIC{n}"] = _make_soic(f"SOIC{n}", n)

    # === TSSOP 系列 ===
    for n in [8, 14, 16, 20, 24, 28]:
        lib[f"TSSOP{n}"] = _make_tssop(f"TSSOP{n}", n)

    # === SSOP 系列 ===
    for n in [8, 16, 20]:
        lib[f"SSOP{n}"] = _make_ssop(f"SSOP{n}", n)

    # === MSOP 系列 ===
    for n in [8, 10]:
        lib[f"MSOP{n}"] = _make_msop(f"MSOP{n}", n)

    # === QFP 系列 ===
    qfp_configs = {
        32: (0.80, 7.0), 44: (0.80, 10.0), 48: (0.50, 7.0),
        64: (0.50, 10.0), 100: (0.50, 14.0), 144: (0.50, 20.0),
    }
    for n, (pitch, body) in qfp_configs.items():
        lib[f"LQFP{n}"] = _make_qfp(f"LQFP{n}", n, pitch, body)
        lib[f"TQFP{n}"] = _make_qfp(f"TQFP{n}", n, pitch, body)

    # === QFN 系列 ===
    qfn_configs = {
        8: (0.65, 3.0, None), 16: (0.50, 3.0, (1.7, 1.7)),
        20: (0.50, 4.0, (2.5, 2.5)), 24: (0.50, 4.0, (2.5, 2.5)),
        32: (0.50, 5.0, (3.5, 3.5)), 40: (0.50, 6.0, (4.0, 4.0)),
        48: (0.50, 7.0, (5.0, 5.0)), 56: (0.40, 7.0, (5.0, 5.0)),
        64: (0.50, 9.0, (7.0, 7.0)),
    }
    for n, (pitch, body, ep) in qfn_configs.items():
        lib[f"QFN{n}"] = _make_qfn(f"QFN{n}", n, pitch, body, exposed_pad=ep)

    # === DFN 系列 ===
    lib["DFN8"] = _make_qfn("DFN8", 8, 0.50, 3.0)
    lib["DFN10"] = _make_qfn("DFN10", 8, 0.50, 3.0)  # simplified

    # === DIP 系列 ===
    for n in [8, 14, 16, 18, 20, 24, 28, 40]:
        lib[f"DIP{n}"] = _make_dip(f"DIP{n}", n)

    # === 功率封装 ===
    lib["TO220"] = _make_to220("TO220")
    lib["TO92"] = _make_to92("TO92")
    lib["DPAK"] = _make_dpak("DPAK")
    lib["D2PAK"] = _make_d2pak("D2PAK")

    # === 二极管 SMD 封装 ===
    lib["SMA"] = _make_diode_smd("SMA", 1.50, 2.10, 2.00)
    lib["SMB"] = _make_diode_smd("SMB", 1.80, 2.60, 2.40)
    lib["SMC"] = _make_diode_smd("SMC", 2.00, 3.50, 4.20)

    # === 通孔二极管 ===
    lib["DO35"] = _make_dip("DO35", 2, pitch=7.62, row_spacing=7.62,
                            drill=0.70, pad_dia=1.40)
    lib["DO41"] = _make_dip("DO41", 2, pitch=10.16, row_spacing=10.16,
                            drill=0.80, pad_dia=1.60)

    return lib


FOOTPRINT_LIBRARY = _build_library()


def get_footprint(package_name):
    """获取封装定义，如果不存在则返回 None"""
    return FOOTPRINT_LIBRARY.get(package_name)


def get_all_footprint_names():
    """获取所有可用的封装名列表"""
    return sorted(FOOTPRINT_LIBRARY.keys())


def create_generic_footprint(name, pin_count=2, is_smd=True, pitch=0.50):
    """为未知封装创建通用占位封装"""
    pads = []

    if pin_count <= 2:
        # 简单两端器件
        pads = [
            PadDef(1, -1.0, 0, 0.60, 1.00, "RF" if is_smd else "R", is_smd),
            PadDef(2, 1.0, 0, 0.60, 1.00, "RF" if is_smd else "R", is_smd),
        ]
        outline = OutlineDef([
            (-1.5, 0.8), (1.5, 0.8), (1.5, -0.8), (-1.5, -0.8), (-1.5, 0.8)
        ], 0.15, 27)
    else:
        # 双列排列
        half_pins = pin_count // 2
        total_height = (half_pins - 1) * pitch
        half_h = total_height / 2.0

        for i in range(half_pins):
            y = half_h - i * pitch
            pads.append(PadDef(i + 1, -2.0, y, 0.30, 0.80, "RF" if is_smd else "R", is_smd))
            pads.append(PadDef(pin_count - i, 2.0, y, 0.30, 0.80, "RF" if is_smd else "R", is_smd))

        hw = 2.5
        hh = half_h + 1.0
        outline = OutlineDef([
            (-hw, hh), (hw, hh), (hw, -hh), (-hw, -hh), (-hw, hh)
        ], 0.15, 27)

    return FootprintDef(name, pads, [outline], is_smd=is_smd)
