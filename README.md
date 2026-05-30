# RailwayStation_V2 Python

这是 `PointToArea/RailwayStation_V2` 的 Python 等价实现目录。

当前实现重点放在求解核心：

- 领域对象：`Car`、`TrackLine`、`Train`、`Operation`
- 任务系统：`TaskManager`、`BCTaskManager`
- 核心策略：缓存线选择、取车/放车/清线/称重任务
- 主算法：`BackwardConstructionAlgorithm`

和 C# 原工程相比，这个目录刻意做了两件事：

1. 把 Excel 读写适配层和求解核心拆开。
2. 保留原算法的业务对象与主流程，不做“为了翻译而翻译”的机械代码堆叠。

## 目录

- `railwaystation/core.py`
  求解核心实现。
- `railwaystation/io.py`
  Python 侧上下文结构与占位适配入口。

## 使用方式

```python
from railwaystation.core import BackwardConstructionAlgorithm
from railwaystation.io import TerminalContext

context = TerminalContext(
    distance_matrix=...,
    track_lines=...,
    cars=...,
)

algo = BackwardConstructionAlgorithm(
    track_lines=context.track_lines,
    cars=context.cars,
    distance_matrix=context.distance_matrix,
)
operations = algo.run()
```

## 说明

- 这个版本优先保证“求解器核心”可独立运行、可继续研究验证。
- 原 `Terminal.cs` 里大量 Excel 清洗和输出逻辑没有强行混入核心；如需继续接 Excel，可在 `io.py` 侧追加适配。
# RailwayStation_V2_py
