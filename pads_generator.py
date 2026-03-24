# -*- coding: utf-8 -*-
"""
PADS ASCII 库文件生成器
生成 Mentor PADS 可以导入的 ASCII 格式库文件

支持生成:
- PCB Decal (封装/焊盘图案) 库文件
- Part Type (元件类型) 库文件
- 合并的库文件 (同时包含 Decal 和 Part Type)
"""

import os
from datetime import datetime
from config import PADS_DECAL_HEADER, PADS_PART_HEADER
from footprint_lib import (
    get_footprint, create_generic_footprint, FootprintDef, PadDef, OutlineDef
)
from digikey_parser import Component


def _timestamp():
    """生成 PADS 时间戳"""
    now = datetime.now()
    return now.strftime("%Y.%m.%d.%H.%M.%S")


def _fmt(value, decimals=4):
    """格式化浮点数"""
    return f"{value:.{decimals}f}"


class PADSGenerator:
    """PADS ASCII 库文件生成器"""

    def __init__(self):
        self.decal_lines = []
        self.part_lines = []
        self.generated_decals = set()
        self.generated_parts = set()
        self.warnings = []
        self.stats = {
            "total_components": 0,
            "matched_footprints": 0,
            "generic_footprints": 0,
            "skipped": 0,
        }

    def _add_warning(self, msg):
        self.warnings.append(msg)

    def _generate_decal(self, footprint):
        """生成单个 Decal 的 ASCII 定义"""
        if footprint.name in self.generated_decals:
            return
        self.generated_decals.add(footprint.name)

        lines = []
        ts = _timestamp()

        num_pads = len(footprint.pads)
        num_lines = len(footprint.outlines)
        num_texts = 2  # REF-DES and PART-TYPE

        # Decal 头
        lines.append(f"*{footprint.name} I 0 0 0 {num_texts} 0 {num_pads} {num_lines}")
        lines.append(f"TIMESTAMP {ts}")

        # 时间戳行
        lines.append("0 0 0 0 1.27 0.127 5 0 0 0 0 0")

        # 文本标签: REF-DES
        lines.append("0 0 0 0 1.27 0.127 5 0 0 0 0 0")
        lines.append("REF-DES")

        # 文本标签: PART-TYPE
        lines.append("0 0 0 0 1.27 0.127 5 0 0 0 0 0")
        lines.append("PART-TYPE")

        # 焊盘定义
        # 先定义焊盘 stack
        # PAD <terminal> <stack_count>
        # -2 <width> <shape> <内层参数...>
        # -1 <soldermask 参数>
        # 0 <paste 参数>
        # <terminal_num> <width> <height>

        for pad in footprint.pads:
            if pad.is_smd:
                # SMD 焊盘: 只定义顶层
                lines.append(f"PAD {pad.pin_num} 3")
                lines.append(
                    f"-2 {_fmt(pad.width, 4)} {pad.shape} "
                    f"{_fmt(0, 1)} {_fmt(0, 1)} 0 0 N"
                )
                lines.append(f"-1 0 R")
                lines.append(f"0 0 R")
                lines.append(
                    f"{pad.pin_num} "
                    f"{_fmt(pad.width, 4)} {_fmt(pad.height, 4)}"
                )
            else:
                # Through-hole 焊盘
                drill = pad.width * 0.55  # 钻孔约为焊盘的55%
                lines.append(f"PAD {pad.pin_num} 3")
                lines.append(
                    f"-2 {_fmt(pad.width, 4)} {pad.shape} "
                    f"{_fmt(drill, 4)} 0 0 0 N"
                )
                lines.append(f"-1 0 R")
                lines.append(f"0 0 R")
                lines.append(
                    f"{pad.pin_num} "
                    f"{_fmt(pad.width, 4)} {_fmt(pad.height, 4)}"
                )

        # 焊盘位置
        for pad in footprint.pads:
            lines.append(
                f"{pad.pin_num} {_fmt(pad.x, 4)} {_fmt(pad.y, 4)} "
                f"{pad.pin_num}"
            )

        # 轮廓线
        for outline in footprint.outlines:
            num_pts = len(outline.points)
            is_closed = (num_pts >= 4 and
                         outline.points[0] == outline.points[-1])

            if is_closed:
                lines.append(
                    f"CLOSED {num_pts} {_fmt(outline.line_width, 2)} "
                    f"{outline.layer} -1"
                )
            else:
                lines.append(
                    f"OPEN {num_pts} {_fmt(outline.line_width, 2)} "
                    f"{outline.layer} -1"
                )

            for px, py in outline.points:
                lines.append(f"{_fmt(px, 4)} {_fmt(py, 4)}")

        lines.append("")  # 空行分隔
        self.decal_lines.extend(lines)

    def _generate_part_type(self, component, footprint):
        """生成单个 Part Type 的 ASCII 定义"""
        if component.pads_part_name in self.generated_parts:
            return
        self.generated_parts.add(component.pads_part_name)

        lines = []
        ts = _timestamp()

        decal_name = footprint.name
        num_gates = 1
        num_pins = len(footprint.pads)

        # Part type 头
        # *<part_name> <decal_name> <num_gates> <num_signals> <num_alpins>
        lines.append(
            f"*{component.pads_part_name} "
            f"{decal_name} "
            f"{num_gates} {num_pins} {num_pins}"
        )
        lines.append(f"TIMESTAMP {ts}")

        # 描述属性
        desc = component.description.replace('"', "'")[:80] if component.description else ""
        mfr = component.manufacturer.replace('"', "'")[:40] if component.manufacturer else ""
        mfr_pn = component.mfr_pn.replace('"', "'")[:40] if component.mfr_pn else ""

        # 属性
        attr_count = 0
        attrs = []
        if desc:
            attrs.append(f'"Description" "{desc}"')
            attr_count += 1
        if mfr:
            attrs.append(f'"Manufacturer" "{mfr}"')
            attr_count += 1
        if mfr_pn:
            attrs.append(f'"Mfr_PN" "{mfr_pn}"')
            attr_count += 1
        if component.value:
            attrs.append(f'"Value" "{component.value}"')
            attr_count += 1
        if component.digikey_pn:
            attrs.append(f'"DigiKey_PN" "{component.digikey_pn}"')
            attr_count += 1

        lines.append(f"{attr_count}")
        lines.extend(attrs)

        # Gate 定义
        lines.append(f"G1 {num_pins} 0")

        # Pin 信号对
        for pad in footprint.pads:
            pin_name = f"P{pad.pin_num}"
            lines.append(f"{pin_name} {pad.pin_num} B 0")

        lines.append("")  # 空行分隔
        self.part_lines.extend(lines)

    def process_components(self, components):
        """处理元件列表，生成 PADS 库数据"""
        self.stats["total_components"] = len(components)

        for comp in components:
            # 查找对应的封装
            footprint = get_footprint(comp.package)

            if footprint is None:
                if comp.package and comp.package != "UNKNOWN":
                    # 创建通用封装
                    is_smd = comp.mounting_type.lower() not in (
                        "through hole", "通孔", "through-hole"
                    ) if comp.mounting_type else True

                    footprint = create_generic_footprint(
                        comp.package, comp.pin_count, is_smd
                    )
                    self._add_warning(
                        f"封装 '{comp.package_raw}' -> '{comp.package}' "
                        f"无精确匹配，已创建通用封装 (引脚数: {comp.pin_count})"
                    )
                    self.stats["generic_footprints"] += 1
                else:
                    self._add_warning(
                        f"元件 '{comp.mfr_pn or comp.digikey_pn}' "
                        f"无封装信息，已跳过"
                    )
                    self.stats["skipped"] += 1
                    continue
            else:
                self.stats["matched_footprints"] += 1

            # 确保 decal 名称与元件引用一致
            comp.pads_decal_name = footprint.name

            # 生成 Decal 和 Part Type
            self._generate_decal(footprint)
            self._generate_part_type(comp, footprint)

    def write_decal_file(self, filepath):
        """写入 PCB Decal 库文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{PADS_DECAL_HEADER}\n\n")
            f.write(f"*REMARK* Generated by DigiKey-to-PADS Converter\n")
            f.write(f"*REMARK* Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for line in self.decal_lines:
                f.write(line + "\n")

            f.write("\n*END*\n")

    def write_part_file(self, filepath):
        """写入 Part Type 库文件"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"{PADS_PART_HEADER}\n\n")
            f.write(f"*REMARK* Generated by DigiKey-to-PADS Converter\n")
            f.write(f"*REMARK* Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for line in self.part_lines:
                f.write(line + "\n")

            f.write("\n*END*\n")

    def write_combined_file(self, filepath):
        """写入合并的库文件 (包含 Decal 和 Part Type)"""
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"*REMARK* Generated by DigiKey-to-PADS Converter\n")
            f.write(f"*REMARK* Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # Decal 部分
            f.write(f"{PADS_DECAL_HEADER}\n\n")
            for line in self.decal_lines:
                f.write(line + "\n")
            f.write("\n*END*\n\n")

            # Part Type 部分
            f.write(f"{PADS_PART_HEADER}\n\n")
            for line in self.part_lines:
                f.write(line + "\n")
            f.write("\n*END*\n")

    def get_summary(self):
        """获取转换摘要"""
        s = self.stats
        lines = [
            "=" * 50,
            "转换完成 - 摘要",
            "=" * 50,
            f"总元件数量:     {s['total_components']}",
            f"封装精确匹配:   {s['matched_footprints']}",
            f"通用封装生成:   {s['generic_footprints']}",
            f"跳过(无封装):   {s['skipped']}",
            f"生成 Decal 数:  {len(self.generated_decals)}",
            f"生成 Part 数:   {len(self.generated_parts)}",
            "=" * 50,
        ]

        if self.warnings:
            lines.append(f"\n警告信息 ({len(self.warnings)}):")
            for w in self.warnings[:20]:  # 最多显示20条
                lines.append(f"  ⚠ {w}")
            if len(self.warnings) > 20:
                lines.append(f"  ... 还有 {len(self.warnings) - 20} 条警告")

        return "\n".join(lines)


def convert_digikey_to_pads(components, output_dir, base_name="digikey_library",
                            output_format="combined"):
    """
    主转换函数

    Args:
        components: Component 列表
        output_dir: 输出目录
        base_name: 输出文件基本名
        output_format: 输出格式
            - "combined": 合并的单个文件
            - "separate": 分别输出 Decal 和 Part Type 文件
            - "both": 同时输出合并和分别的文件

    Returns:
        tuple: (输出文件路径列表, 摘要文本)
    """
    os.makedirs(output_dir, exist_ok=True)

    generator = PADSGenerator()
    generator.process_components(components)

    output_files = []

    if output_format in ("combined", "both"):
        combined_path = os.path.join(output_dir, f"{base_name}.asc")
        generator.write_combined_file(combined_path)
        output_files.append(combined_path)

    if output_format in ("separate", "both"):
        decal_path = os.path.join(output_dir, f"{base_name}_decals.d")
        part_path = os.path.join(output_dir, f"{base_name}_parts.p")
        generator.write_decal_file(decal_path)
        generator.write_part_file(part_path)
        output_files.extend([decal_path, part_path])

    summary = generator.get_summary()
    return output_files, summary
