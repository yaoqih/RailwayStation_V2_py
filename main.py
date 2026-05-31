import json
from pathlib import Path

from railwaystation import BackwardConstructionAlgorithm, DataProvider, Terminal

case_path = Path("/Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2_py/Data/2025-09-04-noon.xlsx")
map_path = Path("/Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2_py/Data/map.xlsx")
output_path = Path("/Users/huyaoqi/Documents/train_cal/PointToArea/RailwayStation_V2_py/result_2025-09-04-noon_python.json")
working_case_path = Terminal.prepare_standardized_case(str(case_path))

# 第一步：补 Start_with_end
Terminal.add_end_position_to_start_sheet(str(working_case_path))

# 第二步：生成 End_generated
Terminal.generate_end_sheet(str(case_path))

# 第三步：正式求解
distance_matrix, track_line_capacity = DataProvider.get_map_info(str(map_path))
track_lines = DataProvider.init_track_lines(track_line_capacity)
cars = DataProvider.init_cars(track_lines, str(working_case_path))
operations = BackwardConstructionAlgorithm(track_lines, cars, distance_matrix).run()

payload = [
    {
        "Index": op.index,
        "LineName": op.line_name,
        "Action": op.action.value,
        "MoveCars": [car.no for car in op.move_cars],
        "TrainCars": [car.no for car in op.train_cars],
        "LineCarsBefore": [car.no for car in op.line_cars_before],
        "LineCarsAfter": [car.no for car in op.line_cars_after],
    }
    for op in operations
]

output_path.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
)

print(f"生成操作数: {len(operations)}")
print(f"结果文件: {output_path}")
