# DigiKey → Mentor PADS 元件库转换器

将 DigiKey 导出的 CSV 元件列表转换为 Mentor PADS 可识别的 ASCII 库文件格式。

## 功能特点

- **自动解析** DigiKey 导出的 CSV 文件（支持中英文列名）
- **智能封装匹配**: 内置 80+ 种常见封装（0201~2512、SOT、SOIC、TSSOP、QFP、QFN、DIP 等）
- **自动生成通用封装**: 对于未匹配的封装类型，自动创建占位封装
- **多种输出格式**:
  - `.asc` 合并文件（可直接导入 PADS）
  - `.d` Decal 封装库 + `.p` Part Type 元件库（分别导入）
- **图形界面**: tkinter GUI，支持预览、选择、转换
- **元件属性保留**: 制造商、料号、描述、DigiKey 编号等属性写入库文件

## 快速开始

### 环境要求

- Python 3.7+
- 无须额外安装第三方库（仅使用标准库）

### 运行

```bash
python main.py
```

### 使用步骤

1. **导出 DigiKey 数据**: 在 DigiKey 网站上选择元件后，导出 CSV 文件
2. **打开转换器**: 运行 `python main.py`
3. **选择 CSV 文件**: 点击"浏览"选择 DigiKey 导出的 CSV
4. **点击"解析预览"**: 查看识别到的元件和封装匹配情况
5. **设置输出**: 选择输出目录、文件名和格式
6. **点击"开始转换"**: 生成 PADS 库文件

### 在 PADS 中导入

**方法一: 导入合并文件 (.asc)**
1. 打开 PADS Layout
2. `File` → `Library` → `Import Library...`
3. 选择生成的 `.asc` 文件

**方法二: 分别导入**
1. PADS Layout: `File` → `Library` → `Import Library...` → 选择 `.d` 文件 (Decal)
2. PADS Logic: `File` → `Library` → `Import Library...` → 选择 `.p` 文件 (Part Type)

## 文件结构

```
├── main.py              # 主程序 (GUI 界面)
├── config.py            # 配置文件 (列名映射、封装映射)
├── digikey_parser.py    # DigiKey CSV 解析器
├── footprint_lib.py     # 标准封装库定义
├── pads_generator.py    # PADS ASCII 库文件生成器
└── README.md            # 本文档
```

## 支持的封装列表

### 片式无源器件 (电阻/电容/电感)
0201, 0402, 0603, 0805, 1206, 1210, 1812, 2010, 2512

### SOT 系列
SOT23, SOT23-5, SOT23-6, SOT223, SOT363, SC70, SC70-5, SC70-6

### SOIC 系列
SOIC8, SOIC14, SOIC16

### TSSOP 系列
TSSOP8, TSSOP14, TSSOP16, TSSOP20, TSSOP24, TSSOP28

### SSOP / MSOP
SSOP8, SSOP16, SSOP20, MSOP8, MSOP10

### QFP 系列
LQFP32, LQFP44, LQFP48, LQFP64, LQFP100, LQFP144
TQFP32, TQFP44, TQFP48, TQFP64, TQFP100

### QFN / DFN
QFN8, QFN16, QFN20, QFN24, QFN32, QFN40, QFN48, QFN56, QFN64
DFN8, DFN10

### DIP 系列
DIP8, DIP14, DIP16, DIP18, DIP20, DIP24, DIP28, DIP40

### 功率封装
TO92, TO220, DPAK, D2PAK

### 二极管封装
SMA, SMB, SMC, DO35, DO41

## DigiKey CSV 格式说明

转换器支持以下 DigiKey 导出 CSV 的列标题（中英文均可）：

| 字段 | 英文列标题 | 中文列标题 |
|------|-----------|-----------|
| 料号 | Digi-Key Part Number | Digi-Key 零件编号 |
| 制造商料号 | Manufacturer Part Number | 制造商零件编号 |
| 制造商 | Manufacturer | 制造商 |
| 描述 | Description | 描述 |
| 封装 | Package / Case | 封装/外壳 |
| 安装类型 | Mounting Type | 安装类型 |

## 自定义和扩展

### 添加新封装映射

编辑 `config.py` 中的 `PACKAGE_NORMALIZE` 字典：

```python
PACKAGE_NORMALIZE = {
    "你的DigiKey封装名": "标准封装名",
    ...
}
```

### 添加新封装定义

编辑 `footprint_lib.py`，在 `_build_library()` 函数中添加新的封装定义。

## 注意事项

- 通用封装（标记为 `?`）的焊盘尺寸可能不准确，建议在 PADS 中手动调整
- 建议在导入 PADS 后检查封装焊盘尺寸是否符合实际的元件 datasheet
- 对于关键元件，推荐使用制造商提供的精确 footprint 数据
