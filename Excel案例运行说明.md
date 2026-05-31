# RailwayStation_V2_py Excel案例运行说明

这份文档只讲一件事：怎么用 `PointToArea/RailwayStation_V2_py` 跑一个 Excel 案例。

下面的说明是按当前 Python 源码真实行为写的，不是按理想化 CLI 写的。

## 1. 先说结论

当前 Python 版没有现成的命令行入口。

要跑一个 Excel 案例，实际分两步：

1. 先给案例文件补出 `Start_with_end` 和 `End_generated`
2. 再读取 `Start` 和 `End_generated` 运行求解器

## 2. 运行前提

需要：

- Python 3.10+
- `openpyxl`

安装依赖：

```bash
pip install openpyxl
```

## 3. 输入文件要求

假设你要跑这个案例：

- 案例文件：`/Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2.Console/Data/2025-09-04-noon.xlsx`
- 地图文件：`/Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2.Console/Data/map.xlsx`

当前代码有两个重要前提：

1. 求解阶段会读取案例文件里的 `Start` 和 `End_generated`
2. `TerminalContext.build_terminal_context(...)` 会默认去案例文件同目录找 `map.xlsx`

所以最稳妥的做法是：

- 把案例文件和 `map.xlsx` 放在同一个目录
- 不要直接改原始案例，先复制一个副本再跑

## 4. 最推荐的运行方式

先进入工程目录：

```bash
cd /Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2_py
```

先复制一个案例副本，避免原文件被原地改写：

```bash
cp /Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2.Console/Data/2025-09-04-noon.xlsx ./2025-09-04-noon.run.xlsx
cp /Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2.Console/Data/map.xlsx ./map.xlsx
```

然后执行：

```bash
python run_excel_case.py \
  --file /Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2_py/2025-09-04-noon.run.xlsx \
  --map /Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2_py/map.xlsx \
  --output /Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2_py/result_2025-09-04-noon_python.json \
  --prepare-terminal \
  --apply-csharp-export-postprocess
```

## 5. 这段代码实际做了什么

### 5.1 `Terminal.add_end_position_to_start_sheet(...)`

它会修改案例 Excel，本地新增一个 sheet：

- `Start_with_end`

这个 sheet 是在 `Start` 基础上补三列：

- `末尾位置`
- `终点台位`
- `强制对位`

### 5.2 `Terminal.generate_end_sheet(...)`

它也会修改案例 Excel，本地新增或覆盖一个 sheet：

- `End_generated`

这个 sheet 是 Python 终点分配器生成的“程序实际使用的终点表”。

### 5.3 `run_excel_case.py`

这个脚本现在已经落到仓库里了：

- [run_excel_case.py](/Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2_py/run_excel_case.py)

它会按当前 Python 代码链路做三件事：

1. 可选地生成 `Start_with_end`
2. 可选地生成 `End_generated`
3. 读取 `Start` + `End_generated` 正式求解

如果加了：

- `--apply-csharp-export-postprocess`

它还会额外套一层和 C# Console 一样的导出后处理：

- `TrainCars.Reverse()`
- `Put` 动作的 `MoveCars.Reverse()`

这样生成出来的 JSON 更接近 C# Console 的结果表示层。

### 5.4 `DataProvider.init_cars(...)`

正式求解时，它不是读 `End`，而是读：

- `Start`
- `End_generated`

所以如果你不先生成 `End_generated`，这里会直接失败。

## 6. 运行后的产物

跑完以后，通常会有三类结果：

1. Excel 副本里新增：
   - `Start_with_end`
   - `End_generated`
2. 控制台打印每辆车分配后的终点台位
3. 你指定的 JSON 文件，比如：
   - `result_2025-09-04-noon_python.json`

## 7. 常见坑

### 7.1 会原地修改 Excel

`Terminal.add_end_position_to_start_sheet(...)` 和 `Terminal.generate_end_sheet(...)` 都会直接写回原文件。

所以不要直接拿原始样例跑，先复制副本。

### 7.2 `map.xlsx` 路径问题

终点分配阶段的 `TerminalContext.build_terminal_context(...)` 默认从案例文件所在目录找 `map.xlsx`。

也就是说：

- 如果案例在 `A/2025-09-04-noon.run.xlsx`
- 那它会默认去找 `A/map.xlsx`

如果那个目录里没有 `map.xlsx`，终点分配阶段会失败。

### 7.3 只补了 `Start_with_end`，没生成 `End_generated`

这样正式求解还是跑不起来，因为 `init_cars(...)` 明确依赖 `End_generated`。

### 7.4 直接拿 `End` 当正式终点

当前 Python 求解器不是这么接的。

它的标准链路是：

`End` -> 终点分配 -> `End_generated` -> 正式求解

## 8. 最小验证方式

如果你只想确认 Excel 预处理成功，不先跑求解，可以只执行：

```bash
python - <<'PY'
from railwaystation import Terminal

case_path = "/Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2_py/2025-09-04-noon.run.xlsx"

Terminal.add_end_position_to_start_sheet(case_path)
Terminal.generate_end_sheet(case_path)

print("已生成 Start_with_end 和 End_generated")
PY
```

## 9. 如果你想批量跑多个 Excel

当前仓库里已经有单文件 CLI：

- [run_excel_case.py](/Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2_py/run_excel_case.py)

如果要批量跑，最简单的方法是对它外面再包一层 `for` 循环，逐个处理。

如果你需要，我可以下一步直接给你补一个真正可用的 Python CLI，例如：

- `python run_excel_case.py --all --data-dir ...`

这样后面就能直接按目录批量跑。
