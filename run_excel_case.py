from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from railwaystation import BackwardConstructionAlgorithm, DataProvider, StandardCaseConverter, Terminal


def apply_csharp_export_postprocess(operations):
    normalized = copy.deepcopy(operations)
    for operation in normalized:
        operation.train_cars.reverse()
        if operation.action.value == "Put":
            operation.move_cars.reverse()
    return normalized


def car_to_payload(car):
    return {
        "No": car.no,
        "Type": car.type,
        "OriginLineName": car.origin_line_name,
        "OriginLineName_Second": car.origin_line_name_second,
        "OriginLinePosition": car.origin_line_position,
        "TargetLineName": car.target_line_name,
        "TargetLineName_Second": car.target_line_name_second,
        "TargetLinePosition": car.target_line_position,
        "CurrentLineName": car.current_line_name,
        "CurrentDepth": car.current_depth,
        "IsHeavy": car.is_heavy,
        "IsWeigh": car.is_weigh,
        "IsWeighed": car.is_weighed,
        "IsForceTargetPosition": car.is_force_target_position,
        "FixedTargetLinePosition": car.fixed_target_line_position,
    }


def build_result_payload(operations):
    return [
        {
            "Index": op.index,
            "LineName": op.line_name,
            "Action": op.action.value,
            "MoveCarCount": op.move_car_count,
            "TrainCarsCount": op.train_cars_count,
            "LineCarsBeforCount": op.line_cars_befor_count,
            "LineCarsAfterCount": op.line_cars_after_count,
            "MoveCars": [car_to_payload(car) for car in op.move_cars],
            "TrainCars": [car_to_payload(car) for car in op.train_cars],
            "LineCarsBefore": [car_to_payload(car) for car in op.line_cars_before],
            "LineCarsAfter": [car_to_payload(car) for car in op.line_cars_after],
        }
        for op in operations
    ]


def resolve_working_case_path(case_path: Path, prepare_terminal: bool) -> Path:
    from openpyxl import load_workbook

    if prepare_terminal:
        Terminal.generate_end_sheet(str(case_path))
        return StandardCaseConverter.convert_case(str(case_path))

    workbook = load_workbook(case_path, read_only=True)
    try:
        has_end_generated = "End_generated" in workbook.sheetnames
    finally:
        workbook.close()

    if has_end_generated:
        return case_path

    Terminal.generate_end_sheet(str(case_path))
    return StandardCaseConverter.convert_case(str(case_path))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a RailwayStation_V2_py Excel case.")
    parser.add_argument("--file", required=True, type=Path, help="Case xlsx path.")
    parser.add_argument("--map", required=True, type=Path, help="map.xlsx path.")
    parser.add_argument("--output", required=True, type=Path, help="Output json path.")
    parser.add_argument("--prepare-terminal", action="store_true", help="Generate Start_with_end and End_generated before solving.")
    parser.add_argument(
        "--apply-csharp-export-postprocess",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Apply legacy export-side reverse logic. Disabled by default because RailwayStation_V2 parity should preserve the raw operation order; use --apply-csharp-export-postprocess only when you explicitly need the older reversed export format.",
    )
    args = parser.parse_args()

    case_path = args.file.resolve()
    map_path = args.map.resolve()
    output_path = args.output.resolve()

    working_case_path = resolve_working_case_path(case_path, args.prepare_terminal)

    distance_matrix, track_line_capacity = DataProvider.get_map_info(str(map_path))
    track_lines = DataProvider.init_track_lines(track_line_capacity)
    cars = DataProvider.init_cars(track_lines, str(working_case_path))
    operations = BackwardConstructionAlgorithm(track_lines, cars, distance_matrix).run()
    if args.apply_csharp_export_postprocess:
        operations = apply_csharp_export_postprocess(operations)

    output_path.write_text(
        json.dumps(build_result_payload(operations), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"operations={len(operations)}")
    print(f"case_used={working_case_path}")
    print(f"output={output_path}")


if __name__ == "__main__":
    main()
