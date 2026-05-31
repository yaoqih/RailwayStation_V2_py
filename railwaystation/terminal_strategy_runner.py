from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile

from .core import BackwardConstructionAlgorithm, Operation
from .data_provider import DataProvider
from .io import TerminalContext
from .line_planner import (
    BalancedLineStrategy,
    ConservativeLineStrategy,
    LinePlannerStrategyBase,
    RepairOverflowSpreadLineStrategy,
    SameSourceContinuousLineStrategy,
)
from .terminal_strategies import (
    AggressiveBlindSpotTerminalStrategy,
    ITerminalStrategy,
    MinimizeBlockTerminalStrategy,
    SameLineReliefTerminalStrategy,
    SolverBlindSpotAvoidanceTerminalStrategy,
    SourcePriorityTerminalStrategy,
)


@dataclass
class TerminalStrategyRunResult:
    strategy_name: str
    operations: list[Operation]
    context: TerminalContext
    line_strategy: LinePlannerStrategyBase
    terminal_strategy: ITerminalStrategy


class TerminalStrategyRunner:
    @staticmethod
    def get_line_strategies() -> list[LinePlannerStrategyBase]:
        return [
            SameSourceContinuousLineStrategy(),
            RepairOverflowSpreadLineStrategy(),
            BalancedLineStrategy(),
            ConservativeLineStrategy(),
        ]

    @staticmethod
    def get_terminal_strategies() -> list[ITerminalStrategy]:
        return [
            SolverBlindSpotAvoidanceTerminalStrategy(),
            SourcePriorityTerminalStrategy(),
            AggressiveBlindSpotTerminalStrategy(),
            SameLineReliefTerminalStrategy(),
            MinimizeBlockTerminalStrategy(),
        ]

    @staticmethod
    def build_operation_signature(operations: list[Operation]) -> str:
        if not operations:
            return ""
        lines: list[str] = []
        for operation in operations:
            move_cars = ",".join(sorted(car.no for car in operation.move_cars))
            train_cars = ",".join(sorted(car.no for car in operation.train_cars))
            line_cars_before = ",".join(sorted(car.no for car in operation.line_cars_before))
            line_cars_after = ",".join(sorted(car.no for car in operation.line_cars_after))
            lines.append(
                "|".join(
                    [
                        str(operation.index),
                        operation.action.value,
                        operation.line_name,
                        move_cars,
                        train_cars,
                        line_cars_before,
                        line_cars_after,
                    ]
                )
            )
        return "\n".join(lines)

    @staticmethod
    def _run_single_strategy_pair(
        file_path: str,
        distance_matrix,
        track_line_capacity,
        line_strategy: LinePlannerStrategyBase,
        terminal_strategy: ITerminalStrategy,
    ) -> TerminalStrategyRunResult:
        from .terminal import Terminal
        from .standard_converter import StandardCaseConverter

        with tempfile.TemporaryDirectory(prefix="railwaystation_strategy_") as temp_dir:
            temp_case_path = Path(temp_dir) / Path(file_path).name
            shutil.copyfile(file_path, temp_case_path)
            source_map_path = Path(file_path).with_name("map.xlsx")
            if source_map_path.exists():
                shutil.copyfile(source_map_path, Path(temp_dir) / "map.xlsx")

            standardized_case_path = StandardCaseConverter.convert_case(str(temp_case_path))
            Terminal.ensure_start_with_end_sheet(str(standardized_case_path))
            context = TerminalContext.build_terminal_context(str(standardized_case_path))
            LinePlannerStrategyRunnerHelper.reset_context_targets(context)
            from .line_planner import LinePlanner

            LinePlanner.assign(context, line_strategy)
            terminal = Terminal()
            terminal_strategy.assign(terminal, context)

            Terminal.copy_source_file(str(standardized_case_path))
            Terminal.output_file(str(standardized_case_path), context)

            solved_track_lines = DataProvider.init_track_lines(track_line_capacity)
            solved_cars = DataProvider.init_cars(solved_track_lines, str(standardized_case_path))
            operations = BackwardConstructionAlgorithm(solved_track_lines, solved_cars, distance_matrix).run()
            return TerminalStrategyRunResult(
                strategy_name=f"{line_strategy.name}+{terminal_strategy.name}",
                operations=operations,
                context=context,
                line_strategy=line_strategy,
                terminal_strategy=terminal_strategy,
            )

    @staticmethod
    def find_best_solve(file_path: str, distance_matrix, track_line_capacity) -> TerminalStrategyRunResult:
        best_result: TerminalStrategyRunResult | None = None
        errors: list[str] = []

        for line_strategy in TerminalStrategyRunner.get_line_strategies():
            for terminal_strategy in TerminalStrategyRunner.get_terminal_strategies():
                try:
                    result = TerminalStrategyRunner._run_single_strategy_pair(
                        file_path,
                        distance_matrix,
                        track_line_capacity,
                        line_strategy,
                        terminal_strategy,
                    )
                    signature = TerminalStrategyRunner.build_operation_signature(result.operations)
                    if best_result is None:
                        best_result = result
                        continue
                    if len(result.operations) < len(best_result.operations):
                        best_result = result
                except Exception as exc:
                    errors.append(f"{line_strategy.name}+{terminal_strategy.name}: {exc}")

        if best_result is None:
            raise RuntimeError(f"所有Terminal策略均失败：{' | '.join(errors)}")
        return best_result


class LinePlannerStrategyRunnerHelper:
    @staticmethod
    def reset_context_targets(context: TerminalContext) -> None:
        for car in context.cars.values():
            if len(car.possible_target_line_names) <= 1:
                continue
            car.target_line_name = ""
            car.target_line_name_second = ""
            car.target_line_position = -1
            car.target_min_position = 0
            car.target_max_position = -1
            car.target_line = None
