from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .core import Car, CarGroup, TrackLine
from .terminal_forced_position_mapper import TerminalForcedPositionMapper


class ITerminalStrategy:
    name = "Base"

    def assign(self, terminal, context) -> None:
        raise NotImplementedError


@dataclass
class PlacementGroup:
    source_line: TrackLine
    cars: list[Car]
    start_index: int
    blocker_count: int
    distance: int
    is_same_line: bool
    chunk_index: int
    source_order: int
    normalized_source_line_name: str = ""
    normalized_target_line_name: str = ""
    source_priority: int = 0
    is_same_canonical_line: bool = False
    order_index: int = 0


@dataclass
class GroupPlacementPlan:
    group: PlacementGroup
    has_forced_car: bool
    can_use_exact_block: bool = False
    exact_start: int = -1
    exact_end: int = -1


@dataclass
class SegmentBucket:
    min_position: int
    max_position: int
    groups: list[PlacementGroup] = field(default_factory=list)


@dataclass
class SourceBucket:
    key: str
    normalized_key: str
    groups: list[PlacementGroup] = field(default_factory=list)


class ExternalGroupOrderingMode(str, Enum):
    HEAD_SCORE_ROUND_ROBIN = "HeadScoreRoundRobin"
    PRIORITY_CLUSTER = "PriorityCluster"
    BLOCKER_WAVE_ROUND_ROBIN = "BlockerWaveRoundRobin"
    LEGACY_ROUND_ROBIN = "LegacyRoundRobin"


class FreeBlockSelectionMode(str, Enum):
    ADJACENCY_TAIL_PREFERRED = "AdjacencyTailPreferred"
    ADJACENCY_HEAD_PREFERRED = "AdjacencyHeadPreferred"
    WIDEST_INTERVAL_TAIL_PREFERRED = "WidestIntervalTailPreferred"
    ALTERNATING_OUTER_EDGE = "AlternatingOuterEdge"


class PositionFillMode(str, Enum):
    COMPACT_TAIL_WINDOW = "CompactTailWindow"
    ALTERNATING_EDGES_TAIL_FIRST = "AlternatingEdgesTailFirst"
    ALTERNATING_EDGES_HEAD_FIRST = "AlternatingEdgesHeadFirst"


@dataclass
class TerminalStrategyOptions:
    use_normalized_source_priority: bool = True
    treat_canonical_same_line_as_same_line: bool = False
    bucket_by_normalized_source_line: bool = False
    split_same_line_groups: bool = False
    split_storage_like_sources: bool = True
    split_when_multiple_external_sources: bool = True
    split_when_same_line_groups_exist: bool = True
    prefer_group_block_placement: bool = False
    interleave_same_line_groups: bool = False
    use_right_aligned_position_span: bool = True
    max_continuous_chunk_size: int = 4
    split_source_priority_threshold: int = 5
    deep_blocker_threshold: int = 4
    deep_blocker_min_cars: int = 4
    multi_source_split_min_cars: int = 4
    same_line_coexist_split_min_cars: int = 4
    blocker_wave_size: int = 2
    blocker_weight: float = 100.0
    source_priority_weight: float = 25.0
    distance_weight: float = 1.0
    chunk_index_weight: float = 15.0
    group_size_weight: float = 5.0
    source_order_weight: float = 0.1
    step_weight: float = 0.0
    same_source_repeat_penalty: float = 80.0
    same_canonical_source_repeat_penalty: float = 40.0
    same_canonical_line_penalty: float = 200.0
    same_line_merge_bias_score: float = 120.0
    external_ordering_mode: ExternalGroupOrderingMode = ExternalGroupOrderingMode.HEAD_SCORE_ROUND_ROBIN
    free_block_selection_mode: FreeBlockSelectionMode = FreeBlockSelectionMode.ADJACENCY_TAIL_PREFERRED
    position_fill_mode: PositionFillMode = PositionFillMode.COMPACT_TAIL_WINDOW


class LegacyCompatibleTerminalStrategyBase(ITerminalStrategy):
    max_continuous_chunk_size = 5

    def assign(self, terminal, context) -> None:
        global_dict = terminal.build_global_dict(context.track_lines)
        if not self.assign_position_direct(global_dict, context, terminal):
            raise RuntimeError("台位分配失败。")

    def assign_position_direct(self, global_dict, context, terminal) -> bool:
        for target_line_name, source_groups in global_dict.items():
            if target_line_name not in context.track_lines:
                raise RuntimeError(f"目标线{target_line_name}不存在。")
            if target_line_name not in context.start_position_dict:
                raise RuntimeError(f"目标线{target_line_name}缺少末尾台位信息。")

            target_track = context.track_lines[target_line_name]
            target_track.target_list.clear()
            line_max_position = context.start_position_dict[target_line_name]

            placement_groups = self.build_placement_groups(source_groups, context, terminal, target_line_name)
            if not placement_groups:
                continue

            segment_buckets = self.build_segment_buckets(placement_groups, line_max_position)
            assigned_position_dict: dict[Car, int] = {}
            for segment_bucket in segment_buckets:
                min_position = segment_bucket.min_position
                max_position = segment_bucket.max_position
                all_cars = [car for group in segment_bucket.groups for car in group.cars]
                if not all_cars:
                    continue
                if min_position > max_position:
                    raise RuntimeError(f"目标线{target_line_name}台位区间非法：[{min_position},{max_position}]")
                capacity = max_position - min_position + 1
                if len(all_cars) > capacity:
                    raise RuntimeError(
                        f"目标线{target_line_name}区间[{min_position},{max_position}]剩余台位不够分，车辆数={len(all_cars)}，容量={capacity}"
                    )
                if any(TerminalForcedPositionMapper.has_position_constraint(car) for car in all_cars):
                    success, segment_assigned = self.try_build_force_aware_assigned_position_dict(
                        segment_bucket.groups,
                        min_position,
                        max_position,
                    )
                    if not success:
                        segment_assigned = self.build_assigned_position_dict(
                            all_cars,
                            min_position,
                            max_position,
                        )
                else:
                    segment_assigned = self.build_assigned_position_dict(
                        all_cars,
                        min_position,
                        max_position,
                    )
                assigned_position_dict.update(segment_assigned)

            target_cars = list(assigned_position_dict.keys())
            for car in target_cars:
                car.target_line = target_track
                car.target_line_name = target_track.name
                car.target_line_position = assigned_position_dict[car]
            for car in sorted(target_cars, key=lambda o: (o.target_line_position, o.origin_line_position)):
                target_track.unshift_target(car)
        return True

    def build_segment_buckets(self, placement_groups: list[PlacementGroup], line_max_position: int) -> list[SegmentBucket]:
        buckets: dict[tuple[int, int], SegmentBucket] = {}
        split_groups = [
            split_group
            for group in placement_groups
            for split_group in self.split_placement_group_by_segment(group, line_max_position)
        ]
        for group in split_groups:
            min_position, max_position = self.resolve_group_segment(group.cars, line_max_position)
            key = (min_position, max_position)
            if key not in buckets:
                buckets[key] = SegmentBucket(min_position=min_position, max_position=max_position)
            buckets[key].groups.append(group)
        return [buckets[key] for key in sorted(buckets, key=lambda item: (item[0], item[1]))]

    def split_placement_group_by_segment(self, group: PlacementGroup, line_max_position: int) -> list[PlacementGroup]:
        if not group.cars:
            return []
        result: list[PlacementGroup] = []
        start_index = 0
        chunk_index = 0
        while start_index < len(group.cars):
            current_segment = self.resolve_car_segment(group.cars[start_index], line_max_position)
            end_index = start_index + 1
            while end_index < len(group.cars):
                next_segment = self.resolve_car_segment(group.cars[end_index], line_max_position)
                if next_segment != current_segment:
                    break
                end_index += 1
            cars = group.cars[start_index:end_index]
            result.append(
                PlacementGroup(
                    source_line=group.source_line,
                    cars=cars,
                    normalized_source_line_name=group.normalized_source_line_name,
                    normalized_target_line_name=group.normalized_target_line_name,
                    start_index=cars[0].origin_line_position,
                    blocker_count=group.blocker_count + start_index,
                    distance=group.distance,
                    is_same_line=group.is_same_line,
                    is_same_canonical_line=group.is_same_canonical_line,
                    chunk_index=group.chunk_index * 1000 + chunk_index,
                    source_order=group.source_order,
                    source_priority=group.source_priority,
                    order_index=group.order_index * 1000 + chunk_index,
                )
            )
            chunk_index += 1
            start_index = end_index
        return result

    def resolve_group_segment(self, cars: list[Car], line_max_position: int) -> tuple[int, int]:
        min_position = max((car.target_min_position for car in cars if car.target_min_position > 0), default=1)
        max_position = min((car.target_max_position for car in cars if car.target_max_position > 0), default=line_max_position)
        max_position = min(max_position, line_max_position)
        return min_position, max_position

    def resolve_car_segment(self, car: Car, line_max_position: int) -> tuple[int, int]:
        min_position = car.target_min_position if car.target_min_position > 0 else 1
        max_position = car.target_max_position if car.target_max_position > 0 else line_max_position
        return min_position, min(max_position, line_max_position)

    def build_assigned_position_dict(self, cars: list[Car], min_position: int, max_position: int) -> dict[Car, int]:
        result: dict[Car, int] = {}
        occupied_positions: set[int] = set()

        constrained_cars = sorted(
            [car for car in cars if TerminalForcedPositionMapper.has_position_constraint(car)],
            key=lambda car: (
                len(TerminalForcedPositionMapper.get_allowed_positions_in_range(car, min_position, max_position)),
                car.no,
            ),
        )
        for car in constrained_cars:
            allowed_positions = TerminalForcedPositionMapper.get_allowed_positions_in_range(car, min_position, max_position)
            if not allowed_positions:
                raise RuntimeError(
                    f"车辆{car.no}的强制对位台位不在允许区间内：强制={car.force_target_position_text}，"
                    f"映射={','.join(str(pos) for pos in car.allowed_target_line_positions)}，允许区间=[{min_position},{max_position}]"
                )
            selected_position = next((pos for pos in allowed_positions if pos not in occupied_positions), -1)
            if selected_position <= 0:
                raise RuntimeError(
                    f"车辆{car.no}的强制对位台位均已被占用：强制={car.force_target_position_text}，"
                    f"映射={','.join(str(pos) for pos in allowed_positions)}"
                )
            result[car] = selected_position
            occupied_positions.add(selected_position)

        remain_count = len(cars) - len(constrained_cars)
        remain_positions = self.find_compact_remain_positions(min_position, max_position, occupied_positions, remain_count)
        remain_index = 0
        for car in cars:
            if car in result:
                continue
            result[car] = remain_positions[remain_index]
            remain_index += 1
        return result

    def try_build_force_aware_assigned_position_dict(
        self,
        placement_groups: list[PlacementGroup],
        min_position: int,
        max_position: int,
    ) -> tuple[bool, dict[Car, int]]:
        result: dict[Car, int] = {}
        if not placement_groups:
            return True, result

        plans = self.build_group_placement_plans(placement_groups, min_position, max_position)
        if any(plan.has_forced_car and not plan.can_use_exact_block for plan in plans):
            return False, {}

        occupied_positions = [False] * (max_position + 1)
        for plan in sorted(
            [plan for plan in plans if plan.can_use_exact_block],
            key=lambda plan: (plan.exact_start, plan.exact_end),
        ):
            for position in range(plan.exact_start, plan.exact_end + 1):
                if occupied_positions[position]:
                    return False, {}
            for i, car in enumerate(plan.group.cars):
                position = plan.exact_start + i
                if not TerminalForcedPositionMapper.is_position_allowed(car, position, min_position, max_position):
                    return False, {}
                occupied_positions[position] = True
                result[car] = position

        for plan in self.order_unanchored_plans(plans):
            if not self.try_assign_unanchored_group(plan, occupied_positions, min_position, max_position, result):
                return False, {}
        return True, result

    def order_unanchored_plans(self, plans: list[GroupPlacementPlan]) -> list[GroupPlacementPlan]:
        return sorted(
            [plan for plan in plans if not plan.can_use_exact_block],
            key=lambda plan: (
                plan.group.is_same_line,
                -len(plan.group.cars),
                self.placement_group_ease_key(plan.group),
            ),
        )

    def build_group_placement_plans(
        self,
        placement_groups: list[PlacementGroup],
        min_position: int,
        max_position: int,
    ) -> list[GroupPlacementPlan]:
        result: list[GroupPlacementPlan] = []
        for placement_group in placement_groups:
            forced_cars = [
                (car, index)
                for index, car in enumerate(placement_group.cars)
                if TerminalForcedPositionMapper.has_position_constraint(car)
            ]
            plan = GroupPlacementPlan(group=placement_group, has_forced_car=bool(forced_cars))
            if not forced_cars:
                result.append(plan)
                continue
            start_candidates: set[int] | None = None
            for car, index in forced_cars:
                allowed_positions = TerminalForcedPositionMapper.get_allowed_positions_in_range(car, min_position, max_position)
                if not allowed_positions:
                    start_candidates = set()
                    break
                current_start_candidates = {pos - index for pos in allowed_positions}
                start_candidates = current_start_candidates if start_candidates is None else (start_candidates & current_start_candidates)
            start_candidates = start_candidates or set()
            if len(start_candidates) == 1:
                exact_start = next(iter(start_candidates))
                exact_end = exact_start + len(placement_group.cars) - 1
                if exact_start >= min_position and exact_end <= max_position:
                    plan.can_use_exact_block = True
                    plan.exact_start = exact_start
                    plan.exact_end = exact_end
            result.append(plan)
        return result

    def try_assign_unanchored_group(
        self,
        plan: GroupPlacementPlan,
        occupied_positions: list[bool],
        min_position: int,
        max_position: int,
        result: dict[Car, int],
    ) -> bool:
        group_length = len(plan.group.cars)
        free_intervals = self.get_free_intervals(occupied_positions, min_position, max_position)
        best_block = None
        best_adjacency = -1
        best_end = -1
        best_start = -1
        for start, end in free_intervals:
            if end - start + 1 < group_length:
                continue
            candidate_blocks = {(start, start + group_length - 1), (end - group_length + 1, end)}
            for candidate_start, candidate_end in candidate_blocks:
                valid_for_all_cars = True
                for i, car in enumerate(plan.group.cars):
                    position = candidate_start + i
                    if not TerminalForcedPositionMapper.is_position_allowed(car, position, min_position, max_position):
                        valid_for_all_cars = False
                        break
                if not valid_for_all_cars:
                    continue
                adjacency = 0
                if candidate_start > min_position and occupied_positions[candidate_start - 1]:
                    adjacency += 1
                if candidate_end < max_position and occupied_positions[candidate_end + 1]:
                    adjacency += 1
                if (
                    adjacency > best_adjacency
                    or (adjacency == best_adjacency and candidate_end > best_end)
                    or (adjacency == best_adjacency and candidate_end == best_end and candidate_start > best_start)
                ):
                    best_adjacency = adjacency
                    best_end = candidate_end
                    best_start = candidate_start
                    best_block = (candidate_start, candidate_end)
        if best_block is None:
            return False
        for i, car in enumerate(plan.group.cars):
            position = best_block[0] + i
            occupied_positions[position] = True
            result[car] = position
        return True

    def get_free_intervals(self, occupied_positions: list[bool], min_position: int, max_position: int) -> list[tuple[int, int]]:
        result: list[tuple[int, int]] = []
        start = None
        for position in range(min_position, max_position + 1):
            if not occupied_positions[position]:
                if start is None:
                    start = position
            elif start is not None:
                result.append((start, position - 1))
                start = None
        if start is not None:
            result.append((start, max_position))
        return result

    def find_compact_remain_positions(
        self,
        min_position: int,
        max_position: int,
        forced_positions: set[int],
        remain_count: int,
    ) -> list[int]:
        result: list[int] = []
        if remain_count <= 0:
            return result
        forced_min = min(forced_positions) if forced_positions else -1
        forced_max = max(forced_positions) if forced_positions else -1
        best_start = -1
        best_end = -1
        best_span = 2**31 - 1
        for start in range(min_position, max_position + 1):
            if forced_positions and start > forced_min:
                break
            end_start = max(start, forced_max) if forced_positions else start
            for end in range(end_start, max_position + 1):
                free_count = sum(1 for pos in range(start, end + 1) if pos not in forced_positions)
                if free_count < remain_count:
                    continue
                span = end - start + 1
                if (
                    span < best_span
                    or (span == best_span and end > best_end)
                    or (span == best_span and end == best_end and start > best_start)
                ):
                    best_span = span
                    best_start = start
                    best_end = end
        if best_start < 0:
            raise RuntimeError("剩余台位不够分")
        for pos in range(best_start, best_end + 1):
            if pos not in forced_positions:
                result.append(pos)
        if len(result) < remain_count:
            raise RuntimeError("剩余台位不够分")
        return result[:remain_count]

    def create_placement_group(self, group: CarGroup, context, terminal, target_line_name: str, source_order: int) -> PlacementGroup:
        top_car = group.top_car
        normalized_source_line_name = terminal.normalize_track_name_for_distance(group.current_line.name)
        normalized_target_line_name = terminal.normalize_track_name_for_distance(target_line_name)
        return PlacementGroup(
            source_line=group.current_line,
            cars=list(group.cars),
            normalized_source_line_name=normalized_source_line_name,
            normalized_target_line_name=normalized_target_line_name,
            start_index=top_car.origin_line_position,
            blocker_count=top_car.current_depth,
            distance=terminal.get_distance(context.distance_matrix, group.current_line.name, target_line_name),
            is_same_line=group.current_line.name == target_line_name,
            is_same_canonical_line=normalized_source_line_name == normalized_target_line_name,
            chunk_index=0,
            source_order=source_order,
            source_priority=terminal.get_source_priority(group.current_line.name, use_normalized=True),
            order_index=0,
        )

    def build_placement_groups(self, source_groups, context, terminal, target_line_name: str) -> list[PlacementGroup]:
        result: list[PlacementGroup] = []
        for _, groups in source_groups.items():
            for index, group in enumerate(groups):
                result.append(self.create_placement_group(group, context, terminal, target_line_name, index))
        external_groups = [group for group in result if not group.is_same_line]
        same_line_groups = [group for group in result if group.is_same_line]
        external_groups.sort(
            key=lambda g: (
                g.source_priority,
                g.blocker_count,
                g.distance,
                g.chunk_index,
                g.start_index,
                g.source_order,
                len(g.cars),
            )
        )
        same_line_groups.sort(key=lambda g: (g.source_order, g.start_index))
        return external_groups + same_line_groups

    def split_placement_group(self, group: PlacementGroup) -> list[PlacementGroup]:
        if (
            len(group.cars) <= self.max_continuous_chunk_size
            or any(TerminalForcedPositionMapper.has_position_constraint(car) for car in group.cars)
        ):
            return [group]
        result: list[PlacementGroup] = []
        chunk_index = 0
        for i in range(0, len(group.cars), self.max_continuous_chunk_size):
            cars = group.cars[i : i + self.max_continuous_chunk_size]
            result.append(
                PlacementGroup(
                    source_line=group.source_line,
                    cars=cars,
                    normalized_source_line_name=group.normalized_source_line_name,
                    normalized_target_line_name=group.normalized_target_line_name,
                    start_index=cars[0].origin_line_position,
                    blocker_count=group.blocker_count + i,
                    distance=group.distance,
                    is_same_line=group.is_same_line,
                    is_same_canonical_line=group.is_same_canonical_line,
                    chunk_index=chunk_index,
                    source_order=group.source_order,
                    source_priority=group.source_priority,
                    order_index=group.order_index,
                )
            )
            chunk_index += 1
        return result

    def placement_group_ease_key(self, group: PlacementGroup) -> tuple:
        return (
            group.is_same_line,
            group.blocker_count,
            group.distance,
            group.chunk_index,
            group.start_index,
            group.source_order,
            len(group.cars),
        )


class SolverBlindSpotAvoidanceTerminalStrategy(LegacyCompatibleTerminalStrategyBase):
    name = "SolverBlindSpotAvoidanceTerminalStrategy"
    max_continuous_chunk_size = 3

    def order_unanchored_plans(self, plans: list[GroupPlacementPlan]) -> list[GroupPlacementPlan]:
        return sorted(
            [plan for plan in plans if not plan.can_use_exact_block],
            key=lambda plan: (
                plan.group.is_same_line,
                plan.group.blocker_count,
                plan.group.source_priority,
                plan.group.distance,
                plan.group.chunk_index,
                plan.group.start_index,
                plan.group.source_order,
            ),
        )

    def build_placement_groups(self, source_groups, context, terminal, target_line_name: str) -> list[PlacementGroup]:
        raw_groups = [
            self.create_placement_group(group, context, terminal, target_line_name, index)
            for source in source_groups.values()
            for index, group in enumerate(source)
        ]
        if not raw_groups:
            return []

        external_groups = [group for group in raw_groups if not group.is_same_line]
        same_line_groups = [group for group in raw_groups if group.is_same_line]
        if not external_groups:
            return sorted(same_line_groups, key=lambda g: (g.blocker_count, g.source_order, g.start_index))

        should_split_external_groups = (
            len({group.source_line.name for group in external_groups}) > 1
            or bool(same_line_groups)
            or any(self.should_split_placement_group(group) for group in external_groups)
        )
        if should_split_external_groups:
            external_groups = [item for group in external_groups for item in self.split_placement_group(group)]

        grouped_external: dict[str, list[PlacementGroup]] = {}
        for group in external_groups:
            grouped_external.setdefault(group.source_line.name, []).append(group)

        ordered_external_groups: list[PlacementGroup] = []
        for source_name, groups in sorted(
            grouped_external.items(),
            key=lambda item: (
                min(group.source_priority for group in item[1]),
                min(group.blocker_count for group in item[1]),
                min(group.distance for group in item[1]),
                item[0],
            ),
        ):
            ordered_external_groups.extend(
                sorted(
                    groups,
                    key=lambda g: (
                        g.blocker_count,
                        g.source_priority,
                        g.distance,
                        g.chunk_index,
                        len(g.cars),
                        g.start_index,
                        g.source_order,
                    ),
                )
            )

        same_line_groups = sorted(same_line_groups, key=lambda g: (g.blocker_count, g.source_order, g.start_index))
        ordered_external_groups.extend(same_line_groups)
        return ordered_external_groups

    def split_placement_group(self, group: PlacementGroup) -> list[PlacementGroup]:
        if (
            len(group.cars) <= self.max_continuous_chunk_size
            or any(TerminalForcedPositionMapper.has_position_constraint(car) for car in group.cars)
            or not self.should_split_placement_group(group)
        ):
            return [group]
        return super().split_placement_group(group)

    def should_split_placement_group(self, group: PlacementGroup) -> bool:
        if len(group.cars) <= 3:
            return False
        if any(TerminalForcedPositionMapper.has_position_constraint(car) for car in group.cars):
            return False
        if group.source_priority >= 5:
            return True
        return group.blocker_count >= 3 and len(group.cars) >= 4


class BlindSpotAwareTerminalStrategyBase(LegacyCompatibleTerminalStrategyBase):
    name = "BlindSpotAwareTerminalStrategyBase"

    def create_options(self) -> TerminalStrategyOptions:
        return TerminalStrategyOptions()

    def assign(self, terminal, context) -> None:
        global_dict = terminal.build_global_dict(context.track_lines)
        options = self.create_options()
        if not self.assign_position_direct_with_options(global_dict, context, terminal, options):
            raise RuntimeError("台位分配失败。")

    def assign_position_direct_with_options(self, global_dict, context, terminal, options: TerminalStrategyOptions) -> bool:
        for target_line_name, source_groups in global_dict.items():
            if target_line_name not in context.track_lines:
                raise RuntimeError(f"目标线{target_line_name}不存在。")
            if target_line_name not in context.start_position_dict:
                raise RuntimeError(f"目标线{target_line_name}缺少末尾台位信息。")

            target_track = context.track_lines[target_line_name]
            target_track.target_list.clear()
            line_max_position = context.start_position_dict[target_line_name]
            placement_groups = self.build_placement_groups_with_options(
                source_groups,
                context,
                terminal,
                target_line_name,
                options,
            )
            if not placement_groups:
                continue

            segment_buckets = self.build_segment_buckets(placement_groups, line_max_position)
            assigned_position_dict: dict[Car, int] = {}
            for segment_bucket in segment_buckets:
                segment_groups = segment_bucket.groups
                all_cars = [car for group in segment_groups for car in group.cars]
                if not all_cars:
                    continue
                has_forced = any(TerminalForcedPositionMapper.has_position_constraint(car) for car in all_cars)
                min_position = (
                    max(segment_bucket.min_position, segment_bucket.max_position - len(all_cars) + 1)
                    if options.use_right_aligned_position_span and not has_forced
                    else segment_bucket.min_position
                )
                max_position = segment_bucket.max_position
                capacity = max_position - min_position + 1
                if len(all_cars) > capacity:
                    raise RuntimeError(
                        f"目标线{target_line_name}区间[{min_position},{max_position}]剩余台位不够分，车辆数={len(all_cars)}，容量={capacity}"
                    )
                if options.prefer_group_block_placement or has_forced:
                    success, segment_assigned = self.try_build_group_aware_assigned_position_dict(
                        segment_groups,
                        min_position,
                        max_position,
                        options,
                    )
                    if not success:
                        segment_assigned = self.build_assigned_position_dict(
                            all_cars,
                            min_position,
                            max_position,
                            options.position_fill_mode,
                        )
                else:
                    segment_assigned = self.build_assigned_position_dict(
                        all_cars,
                        min_position,
                        max_position,
                        options.position_fill_mode,
                    )
                assigned_position_dict.update(segment_assigned)

            target_cars = list(assigned_position_dict.keys())
            for car in target_cars:
                car.target_line = target_track
                car.target_line_name = target_track.name
                car.target_line_position = assigned_position_dict[car]
            for car in sorted(target_cars, key=lambda o: (o.target_line_position, o.origin_line_position)):
                target_track.unshift_target(car)
        return True

    def build_placement_groups_with_options(self, source_groups, context, terminal, target_line_name: str, options: TerminalStrategyOptions) -> list[PlacementGroup]:
        normalized_target_line_name = terminal.normalize_track_name_for_distance(target_line_name)
        raw_groups = [
            self.create_placement_group_with_options(group, context, terminal, target_line_name, normalized_target_line_name, index, options)
            for source in source_groups.values()
            for index, group in enumerate(source)
        ]
        if not raw_groups:
            return []

        external_groups = [group for group in raw_groups if not group.is_same_line]
        same_line_groups = [group for group in raw_groups if group.is_same_line]
        if not external_groups:
            ordered_same_line = sorted(
                same_line_groups,
                key=lambda g: (g.blocker_count, g.source_priority, g.start_index, g.source_order),
            )
            for index, group in enumerate(ordered_same_line):
                group.order_index = index
            return ordered_same_line

        if options.bucket_by_normalized_source_line:
            has_multiple_external_sources = len({group.normalized_source_line_name for group in external_groups}) > 1
        else:
            has_multiple_external_sources = len({group.source_line.name for group in external_groups}) > 1
        has_same_line_groups = bool(same_line_groups)

        split_external_groups: list[PlacementGroup] = []
        for group in external_groups:
            if self.should_split_placement_group_with_options(group, options, has_multiple_external_sources, has_same_line_groups):
                split_external_groups.extend(self.split_placement_group(group))
            else:
                split_external_groups.append(group)

        ordered_external = self.order_external_groups_with_options(split_external_groups, options)
        same_line_groups = sorted(
            same_line_groups,
            key=lambda g: (g.blocker_count, g.source_priority, g.start_index, g.source_order),
        )
        if not options.interleave_same_line_groups:
            result = ordered_external + same_line_groups
        else:
            result = self.merge_same_line_groups(ordered_external, same_line_groups, options)

        for index, group in enumerate(result):
            group.order_index = index
        return result

    def create_placement_group_with_options(
        self,
        group: CarGroup,
        context,
        terminal,
        target_line_name: str,
        normalized_target_line_name: str,
        source_order: int,
        options: TerminalStrategyOptions,
    ) -> PlacementGroup:
        placement_group = self.create_placement_group(group, context, terminal, target_line_name, source_order)
        normalized_source_line_name = terminal.normalize_track_name_for_distance(group.current_line.name)
        is_same_line = group.current_line.name == target_line_name
        if not is_same_line and options.treat_canonical_same_line_as_same_line:
            is_same_line = normalized_source_line_name == normalized_target_line_name
        placement_group.is_same_line = is_same_line
        placement_group.normalized_source_line_name = normalized_source_line_name
        placement_group.normalized_target_line_name = normalized_target_line_name
        placement_group.is_same_canonical_line = normalized_source_line_name == normalized_target_line_name
        placement_group.source_priority = terminal.get_source_priority(group.current_line.name, use_normalized=options.use_normalized_source_priority)
        return placement_group

    def should_split_placement_group_with_options(
        self,
        group: PlacementGroup,
        options: TerminalStrategyOptions,
        has_multiple_external_sources: bool,
        has_same_line_groups: bool,
    ) -> bool:
        if len(group.cars) <= options.max_continuous_chunk_size:
            return False
        if any(TerminalForcedPositionMapper.has_position_constraint(car) for car in group.cars):
            return False
        if group.is_same_line and not options.split_same_line_groups:
            return False
        if options.split_storage_like_sources and self.is_storage_like_source(group.normalized_source_line_name):
            return True
        if group.source_priority >= options.split_source_priority_threshold:
            return True
        if group.blocker_count >= options.deep_blocker_threshold and len(group.cars) >= options.deep_blocker_min_cars:
            return True
        if options.split_when_multiple_external_sources and has_multiple_external_sources and len(group.cars) >= options.multi_source_split_min_cars:
            return True
        if options.split_when_same_line_groups_exist and has_same_line_groups and len(group.cars) >= options.same_line_coexist_split_min_cars:
            return True
        return False

    def is_storage_like_source(self, normalized_source_line_name: str) -> bool:
        if not normalized_source_line_name or not normalized_source_line_name.strip():
            return False
        return normalized_source_line_name == "老预修" or normalized_source_line_name.startswith("存")

    def order_external_groups_with_options(self, external_groups: list[PlacementGroup], options: TerminalStrategyOptions) -> list[PlacementGroup]:
        if options.external_ordering_mode == ExternalGroupOrderingMode.PRIORITY_CLUSTER:
            buckets = self.build_source_buckets(
                external_groups,
                options,
                lambda groups: sorted(groups, key=lambda g: (g.chunk_index, g.start_index, g.source_order, len(g.cars))),
            )
            buckets.sort(key=lambda b: (b.groups[0].source_priority, b.groups[0].blocker_count, b.groups[0].distance, b.key))
            result: list[PlacementGroup] = []
            for bucket in buckets:
                result.extend(bucket.groups)
            return result
        if options.external_ordering_mode == ExternalGroupOrderingMode.BLOCKER_WAVE_ROUND_ROBIN:
            wave_size = max(1, options.blocker_wave_size)
            result: list[PlacementGroup] = []
            wave_keys = sorted({group.blocker_count // wave_size for group in external_groups})
            for wave_key in wave_keys:
                wave_groups = [group for group in external_groups if group.blocker_count // wave_size == wave_key]
                wave_buckets = self.build_source_buckets(
                    wave_groups,
                    options,
                    lambda groups: sorted(groups, key=lambda g: (g.blocker_count, g.source_priority, g.chunk_index, g.start_index, g.source_order)),
                )
                wave_buckets.sort(key=lambda b: (b.groups[0].blocker_count, b.groups[0].source_priority, b.key))
                result.extend(self.drain_buckets_round_robin(wave_buckets, options))
            return result
        if options.external_ordering_mode == ExternalGroupOrderingMode.LEGACY_ROUND_ROBIN:
            return self.order_external_groups_by_legacy_pattern(external_groups)
        buckets = self.build_source_buckets(
            external_groups,
            options,
            lambda groups: sorted(
                groups,
                key=lambda g: (g.blocker_count, g.source_priority, g.distance, g.chunk_index, len(g.cars), g.start_index, g.source_order),
            ),
        )
        buckets.sort(key=lambda b: self.calculate_head_score(b.groups[0], b, None, None, options, 0))
        return self.drain_buckets_round_robin(buckets, options)

    def order_external_groups_by_legacy_pattern(self, external_groups: list[PlacementGroup]) -> list[PlacementGroup]:
        source_buckets = []
        grouped: dict[str, list[PlacementGroup]] = {}
        for group in external_groups:
            grouped.setdefault(group.source_line.name, []).append(group)
        for groups in grouped.values():
            source_buckets.append(sorted(groups, key=lambda g: (g.chunk_index, g.start_index, g.source_order)))
        source_buckets.sort(key=lambda bucket: self.placement_group_ease_key(bucket[0]))

        result: list[PlacementGroup] = []
        has_group = True
        while has_group:
            has_group = False
            for bucket in source_buckets:
                if not bucket:
                    continue
                result.append(bucket.pop(0))
                has_group = True
        return result

    def build_source_buckets(
        self,
        external_groups: list[PlacementGroup],
        options: TerminalStrategyOptions,
        order_factory,
    ) -> list[SourceBucket]:
        grouped: dict[str, list[PlacementGroup]] = {}
        for group in external_groups:
            key = group.normalized_source_line_name if options.bucket_by_normalized_source_line else group.source_line.name
            grouped.setdefault(key, []).append(group)
        result: list[SourceBucket] = []
        for key, groups in grouped.items():
            ordered_groups = order_factory(groups)
            result.append(
                SourceBucket(
                    key=key,
                    normalized_key=ordered_groups[0].normalized_source_line_name,
                    groups=list(ordered_groups),
                )
            )
        return result

    def build_assigned_position_dict(
        self,
        cars: list[Car],
        min_position: int,
        max_position: int,
        position_fill_mode: PositionFillMode,
    ) -> dict[Car, int]:
        result: dict[Car, int] = {}
        occupied_positions: set[int] = set()

        constrained_cars = sorted(
            [car for car in cars if TerminalForcedPositionMapper.has_position_constraint(car)],
            key=lambda car: (
                len(TerminalForcedPositionMapper.get_allowed_positions_in_range(car, min_position, max_position)),
                car.no,
            ),
        )
        for car in constrained_cars:
            allowed_positions = TerminalForcedPositionMapper.get_allowed_positions_in_range(car, min_position, max_position)
            if not allowed_positions:
                raise RuntimeError(
                    f"车辆{car.no}的强制对位台位不在允许区间内：强制={car.force_target_position_text}，"
                    f"映射={','.join(str(pos) for pos in car.allowed_target_line_positions)}，允许区间=[{min_position},{max_position}]"
                )
            selected_position = next((pos for pos in allowed_positions if pos not in occupied_positions), -1)
            if selected_position <= 0:
                raise RuntimeError(
                    f"车辆{car.no}的强制对位台位均已被占用：强制={car.force_target_position_text}，"
                    f"映射={','.join(str(pos) for pos in allowed_positions)}"
                )
            result[car] = selected_position
            occupied_positions.add(selected_position)

        remain_count = len(cars) - len(constrained_cars)
        if position_fill_mode == PositionFillMode.ALTERNATING_EDGES_HEAD_FIRST:
            remain_positions = self.find_alternating_edge_remain_positions(
                min_position,
                max_position,
                occupied_positions,
                remain_count,
                tail_first=False,
            )
        elif position_fill_mode == PositionFillMode.ALTERNATING_EDGES_TAIL_FIRST:
            remain_positions = self.find_alternating_edge_remain_positions(
                min_position,
                max_position,
                occupied_positions,
                remain_count,
                tail_first=True,
            )
        else:
            remain_positions = self.find_compact_remain_positions(
                min_position,
                max_position,
                occupied_positions,
                remain_count,
            )

        remain_index = 0
        for car in cars:
            if car in result:
                continue
            result[car] = remain_positions[remain_index]
            remain_index += 1
        return result

    def try_build_group_aware_assigned_position_dict(
        self,
        placement_groups: list[PlacementGroup],
        min_position: int,
        max_position: int,
        options: TerminalStrategyOptions,
    ) -> tuple[bool, dict[Car, int]]:
        result: dict[Car, int] = {}
        if not placement_groups:
            return True, result

        plans = self.build_group_placement_plans(placement_groups, min_position, max_position)
        if any(plan.has_forced_car and not plan.can_use_exact_block for plan in plans):
            return False, {}

        occupied_positions = [False] * (max_position + 1)
        for plan in sorted(
            [plan for plan in plans if plan.can_use_exact_block],
            key=lambda plan: (plan.exact_start, plan.exact_end),
        ):
            for position in range(plan.exact_start, plan.exact_end + 1):
                if occupied_positions[position]:
                    return False, {}
            for i, car in enumerate(plan.group.cars):
                position = plan.exact_start + i
                if not TerminalForcedPositionMapper.is_position_allowed(car, position, min_position, max_position):
                    return False, {}
                occupied_positions[position] = True
                result[car] = position

        unanchored_plans = sorted(
            [plan for plan in plans if not plan.can_use_exact_block],
            key=lambda plan: plan.group.order_index,
        )
        for step, plan in enumerate(unanchored_plans):
            if not self.try_assign_unanchored_group(
                plan,
                occupied_positions,
                min_position,
                max_position,
                options,
                result,
                step,
            ):
                return False, {}
        return True, result

    def try_assign_unanchored_group(
        self,
        plan: GroupPlacementPlan,
        occupied_positions: list[bool],
        min_position: int,
        max_position: int,
        options: TerminalStrategyOptions,
        result: dict[Car, int],
        step: int,
    ) -> bool:
        group_length = len(plan.group.cars)
        free_intervals = self.get_free_intervals(occupied_positions, min_position, max_position)
        if not free_intervals:
            return False

        candidates: list[tuple[int, int, int, int]] = []
        for start, end in free_intervals:
            interval_length = end - start + 1
            if interval_length < group_length:
                continue
            candidate_blocks = {
                (start, start + group_length - 1),
                (end - group_length + 1, end),
            }
            for candidate_start, candidate_end in candidate_blocks:
                adjacency = 0
                if candidate_start > min_position and occupied_positions[candidate_start - 1]:
                    adjacency += 1
                if candidate_end < max_position and occupied_positions[candidate_end + 1]:
                    adjacency += 1
                candidates.append((candidate_start, candidate_end, interval_length, adjacency))

        if not candidates:
            return False

        if options.free_block_selection_mode == FreeBlockSelectionMode.ADJACENCY_HEAD_PREFERRED:
            ordered_candidates = sorted(candidates, key=lambda item: (-item[3], item[0], item[1]))
        elif options.free_block_selection_mode == FreeBlockSelectionMode.WIDEST_INTERVAL_TAIL_PREFERRED:
            ordered_candidates = sorted(candidates, key=lambda item: (-item[2], -item[3], -item[1], -item[0]))
        elif options.free_block_selection_mode == FreeBlockSelectionMode.ALTERNATING_OUTER_EDGE:
            if step % 2 == 0:
                ordered_candidates = sorted(candidates, key=lambda item: (item[0], -item[3], -item[2], item[1]))
            else:
                ordered_candidates = sorted(candidates, key=lambda item: (-item[1], -item[3], -item[2], -item[0]))
        else:
            ordered_candidates = sorted(candidates, key=lambda item: (-item[3], -item[1], -item[0]))

        best_start, _, _, _ = ordered_candidates[0]
        for i, car in enumerate(plan.group.cars):
            position = best_start + i
            occupied_positions[position] = True
            result[car] = position
        return True

    def find_alternating_edge_remain_positions(
        self,
        min_position: int,
        max_position: int,
        forced_positions: set[int],
        remain_count: int,
        tail_first: bool,
    ) -> list[int]:
        result: list[int] = []
        if remain_count <= 0:
            return result

        positions: list[int] = []
        left = min_position
        right = max_position
        take_right = tail_first
        while left <= right:
            if take_right:
                if right not in forced_positions:
                    positions.append(right)
                right -= 1
            else:
                if left not in forced_positions:
                    positions.append(left)
                left += 1
            take_right = not take_right

        if len(positions) < remain_count:
            raise RuntimeError("剩余台位不够分")
        return positions[:remain_count]

    def drain_buckets_round_robin(self, buckets: list[SourceBucket], options: TerminalStrategyOptions) -> list[PlacementGroup]:
        result: list[PlacementGroup] = []
        last_bucket_key: str | None = None
        last_normalized_bucket_key: str | None = None
        step = 0
        while any(bucket.groups for bucket in buckets):
            next_bucket = min(
                (bucket for bucket in buckets if bucket.groups),
                key=lambda bucket: (
                    self.calculate_head_score(bucket.groups[0], bucket, last_bucket_key, last_normalized_bucket_key, options, step),
                    bucket.key,
                ),
            )
            next_group = next_bucket.groups.pop(0)
            result.append(next_group)
            last_bucket_key = next_bucket.key
            last_normalized_bucket_key = next_bucket.normalized_key
            step += 1
        return result

    def calculate_inline_merge_score(self, group: PlacementGroup, is_same_line_group: bool, options: TerminalStrategyOptions) -> float:
        score = (
            group.blocker_count * options.blocker_weight
            + group.source_priority * options.source_priority_weight
            + group.distance * options.distance_weight
            + group.chunk_index * options.chunk_index_weight
            + group.source_order * options.source_order_weight
        )
        if is_same_line_group:
            score += options.same_line_merge_bias_score
        if group.is_same_canonical_line:
            score += options.same_canonical_line_penalty
        return score

    def calculate_head_score(
        self,
        group: PlacementGroup,
        bucket: SourceBucket,
        last_bucket_key: str | None,
        last_normalized_bucket_key: str | None,
        options: TerminalStrategyOptions,
        step: int,
    ) -> float:
        score = (
            group.blocker_count * options.blocker_weight
            + group.source_priority * options.source_priority_weight
            + group.distance * options.distance_weight
            + group.chunk_index * options.chunk_index_weight
            + len(group.cars) * options.group_size_weight
            + group.source_order * options.source_order_weight
            + step * options.step_weight
        )
        if last_bucket_key and last_bucket_key == bucket.key:
            score += options.same_source_repeat_penalty
        if last_normalized_bucket_key and last_normalized_bucket_key == bucket.normalized_key:
            score += options.same_canonical_source_repeat_penalty
        if group.is_same_canonical_line:
            score += options.same_canonical_line_penalty
        return score

    def merge_same_line_groups(
        self,
        external_groups: list[PlacementGroup],
        same_line_groups: list[PlacementGroup],
        options: TerminalStrategyOptions,
    ) -> list[PlacementGroup]:
        external_queue = list(external_groups)
        same_line_queue = list(same_line_groups)
        result: list[PlacementGroup] = []
        while external_queue or same_line_queue:
            if not external_queue:
                result.append(same_line_queue.pop(0))
                continue
            if not same_line_queue:
                result.append(external_queue.pop(0))
                continue
            external_head = external_queue[0]
            same_line_head = same_line_queue[0]
            same_line_score = self.calculate_inline_merge_score(same_line_head, True, options)
            external_score = self.calculate_inline_merge_score(external_head, False, options)
            if same_line_score <= external_score:
                result.append(same_line_queue.pop(0))
            else:
                result.append(external_queue.pop(0))
        return result


class SourcePriorityTerminalStrategy(BlindSpotAwareTerminalStrategyBase):
    name = "SourcePriorityTerminalStrategy"

    def create_options(self) -> TerminalStrategyOptions:
        return TerminalStrategyOptions(
            use_normalized_source_priority=False,
            treat_canonical_same_line_as_same_line=False,
            bucket_by_normalized_source_line=False,
            split_same_line_groups=False,
            split_storage_like_sources=True,
            split_when_multiple_external_sources=False,
            split_when_same_line_groups_exist=False,
            prefer_group_block_placement=False,
            interleave_same_line_groups=False,
            use_right_aligned_position_span=True,
            max_continuous_chunk_size=5,
            split_source_priority_threshold=2**31 - 1,
            deep_blocker_threshold=2**31 - 1,
            deep_blocker_min_cars=2**31 - 1,
            multi_source_split_min_cars=2**31 - 1,
            same_line_coexist_split_min_cars=2**31 - 1,
            blocker_wave_size=2,
            blocker_weight=100.0,
            source_priority_weight=40.0,
            distance_weight=1.0,
            chunk_index_weight=15.0,
            group_size_weight=5.0,
            source_order_weight=0.1,
            step_weight=0.0,
            same_source_repeat_penalty=0.0,
            same_canonical_source_repeat_penalty=0.0,
            same_canonical_line_penalty=200.0,
            same_line_merge_bias_score=120.0,
            external_ordering_mode=ExternalGroupOrderingMode.PRIORITY_CLUSTER,
            free_block_selection_mode=FreeBlockSelectionMode.ADJACENCY_TAIL_PREFERRED,
            position_fill_mode=PositionFillMode.COMPACT_TAIL_WINDOW,
        )


class AggressiveBlindSpotTerminalStrategy(BlindSpotAwareTerminalStrategyBase):
    name = "AggressiveBlindSpotTerminalStrategy"

    def create_options(self) -> TerminalStrategyOptions:
        return TerminalStrategyOptions(
            use_normalized_source_priority=True,
            treat_canonical_same_line_as_same_line=True,
            bucket_by_normalized_source_line=True,
            split_same_line_groups=False,
            split_storage_like_sources=True,
            split_when_multiple_external_sources=True,
            split_when_same_line_groups_exist=True,
            max_continuous_chunk_size=2,
            split_source_priority_threshold=4,
            deep_blocker_threshold=2,
            deep_blocker_min_cars=3,
            multi_source_split_min_cars=3,
            same_line_coexist_split_min_cars=3,
            blocker_weight=140.0,
            source_priority_weight=32.0,
            distance_weight=1.5,
            chunk_index_weight=22.0,
            group_size_weight=3.0,
            source_order_weight=0.2,
            same_source_repeat_penalty=260.0,
            same_canonical_source_repeat_penalty=140.0,
            same_canonical_line_penalty=340.0,
        )


class SameLineReliefTerminalStrategy(BlindSpotAwareTerminalStrategyBase):
    name = "SameLineReliefTerminalStrategy"

    def create_options(self) -> TerminalStrategyOptions:
        return TerminalStrategyOptions(
            use_normalized_source_priority=True,
            treat_canonical_same_line_as_same_line=True,
            bucket_by_normalized_source_line=True,
            split_same_line_groups=True,
            split_storage_like_sources=True,
            split_when_multiple_external_sources=True,
            split_when_same_line_groups_exist=True,
            prefer_group_block_placement=True,
            interleave_same_line_groups=True,
            use_right_aligned_position_span=True,
            max_continuous_chunk_size=3,
            split_source_priority_threshold=4,
            deep_blocker_threshold=3,
            deep_blocker_min_cars=3,
            multi_source_split_min_cars=3,
            same_line_coexist_split_min_cars=2,
            blocker_wave_size=2,
            blocker_weight=130.0,
            source_priority_weight=30.0,
            distance_weight=1.0,
            chunk_index_weight=18.0,
            group_size_weight=3.0,
            source_order_weight=0.15,
            same_source_repeat_penalty=180.0,
            same_canonical_source_repeat_penalty=100.0,
            same_canonical_line_penalty=240.0,
            same_line_merge_bias_score=-45.0,
            external_ordering_mode=ExternalGroupOrderingMode.HEAD_SCORE_ROUND_ROBIN,
            free_block_selection_mode=FreeBlockSelectionMode.WIDEST_INTERVAL_TAIL_PREFERRED,
            position_fill_mode=PositionFillMode.COMPACT_TAIL_WINDOW,
        )


class MinimizeBlockTerminalStrategy(BlindSpotAwareTerminalStrategyBase):
    name = "MinimizeBlockTerminalStrategy"

    def create_options(self) -> TerminalStrategyOptions:
        return TerminalStrategyOptions(
            use_normalized_source_priority=False,
            treat_canonical_same_line_as_same_line=False,
            bucket_by_normalized_source_line=False,
            split_same_line_groups=True,
            split_storage_like_sources=False,
            split_when_multiple_external_sources=True,
            split_when_same_line_groups_exist=True,
            prefer_group_block_placement=False,
            interleave_same_line_groups=False,
            use_right_aligned_position_span=False,
            max_continuous_chunk_size=2,
            split_source_priority_threshold=3,
            deep_blocker_threshold=3,
            multi_source_split_min_cars=1,
            same_line_coexist_split_min_cars=1,
            blocker_weight=300.0,
            source_priority_weight=0.0,
            distance_weight=0.0,
            chunk_index_weight=0.0,
            group_size_weight=10.0,
            source_order_weight=0.0,
            same_source_repeat_penalty=300.0,
            same_canonical_source_repeat_penalty=300.0,
            same_canonical_line_penalty=300.0,
            same_line_merge_bias_score=0.0,
            external_ordering_mode=ExternalGroupOrderingMode.HEAD_SCORE_ROUND_ROBIN,
            free_block_selection_mode=FreeBlockSelectionMode.WIDEST_INTERVAL_TAIL_PREFERRED,
            position_fill_mode=PositionFillMode.COMPACT_TAIL_WINDOW,
        )
