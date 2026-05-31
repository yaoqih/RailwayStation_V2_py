from __future__ import annotations

from dataclasses import dataclass, field

from .core import Car
from .terminal_forced_position_mapper import TerminalForcedPositionMapper


@dataclass
class _LineState:
    used_count: dict[str, int] = field(default_factory=dict)
    capacity_dict: dict[str, int] = field(default_factory=dict)
    forced_reservation: dict[str, int] = field(default_factory=dict)
    forced_position_usage: dict[str, set[int]] = field(default_factory=dict)
    forced_position_owner: dict[str, dict[int, str]] = field(default_factory=dict)


class LinePlannerStrategyBase:
    name = "Base"
    repair_outer_capacity = 4

    @property
    def repair_inner_capacity(self) -> int:
        from .terminal import Terminal

        return Terminal.repair_inner_capacity

    def create_capacity_dict(self) -> dict[str, int]:
        inner = self.repair_inner_capacity
        return {
            "修1库外": self.repair_outer_capacity,
            "修2库外": self.repair_outer_capacity,
            "修3库外": self.repair_outer_capacity,
            "修4库外": self.repair_outer_capacity,
            "修1": inner,
            "修2": inner,
            "修3": inner,
            "修4": inner,
            "修1库内": inner,
            "修2库内": inner,
            "修3库内": inner,
            "修4库内": inner,
            "预修": 14,
            "老预修": 14,
            "机库": 5,
            "机库线": 5,
            "机北3": 6,
            "机棚": 8,
            "机走": 14,
            "机走预修": 14,
            "调北": 6,
            "调棚": 11,
            "调梁": 17,
            "轮": 4,
            "卸轮线": 4,
            "油": 9,
            "漆": 9,
            "喷漆": 9,
            "油漆": 9,
            "油漆线": 9,
            "抛": 3,
            "抛丸线": 3,
            "洗北": 8,
            "洗南": 7,
            "洗罐": 15,
            "洗罐线": 15,
            "存1": 9,
            "存1线": 9,
            "存2": 20,
            "存2线": 20,
            "存3": 21,
            "存3线": 21,
            "存4": 25,
            "存4线": 25,
            "存5北": 21,
            "存5南": 12,
            "存5": 33,
            "存5线": 33,
        }

    def get_capacity(self, line_name: str, capacity_dict: dict[str, int]) -> int:
        line_name = self.normalize_raw_candidate_name(line_name)
        return capacity_dict.get(line_name, 2**31 - 1)

    def has_capacity(self, line_name: str, used_count: dict[str, int], capacity_dict: dict[str, int]) -> bool:
        line_name = self.normalize_raw_candidate_name(line_name)
        return used_count.get(line_name, 0) < self.get_capacity(line_name, capacity_dict)

    def get_remain_capacity(self, line_name: str, used_count: dict[str, int], capacity_dict: dict[str, int]) -> int:
        line_name = self.normalize_raw_candidate_name(line_name)
        return self.get_capacity(line_name, capacity_dict) - used_count.get(line_name, 0)

    def split_candidate_line_names(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        return [
            item.strip()
            for item in text.replace("，", ",").replace("；", ",").replace(";", ",").replace("/", ",").replace("、", ",").split(",")
            if item.strip()
        ]

    def normalize_raw_candidate_name(self, line_name: str) -> str:
        if not line_name:
            return ""
        line_name = line_name.strip()
        mapping = {
            "修1库内": "修1",
            "修2库内": "修2",
            "修3库内": "修3",
            "修4库内": "修4",
            "修一": "修1",
            "修二": "修2",
            "修三": "修3",
            "修四": "修4",
            "修一库外": "修1库外",
            "修二库外": "修2库外",
            "修三库外": "修3库外",
            "修四库外": "修4库外",
            "调梁线": "调梁",
            "调梁库": "调梁",
            "调梁库内": "调梁",
            "机库": "机库线",
            "机走线": "机走",
            "机走预修线": "机走",
            "抛丸": "抛",
            "抛丸线": "抛",
            "漆": "油",
            "喷漆": "油",
            "喷漆线": "油",
            "油漆": "油",
            "油漆线": "油",
            "卸轮": "轮",
            "卸轮线": "轮",
            "洗罐区": "洗罐",
            "洗罐线": "洗罐",
            "存1线": "存1",
            "存2线": "存2",
            "存3线": "存3",
            "存4线": "存4",
            "存5线": "存5",
        }
        return mapping.get(line_name, line_name)

    def has_force_constraint(self, car: Car) -> bool:
        return TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text)

    def normalize_possible_lines(self, car: Car) -> list[str]:
        possible = []
        if car.possible_target_line_names:
            possible.extend(car.possible_target_line_names)
        elif car.target_line_name:
            possible.append(car.target_line_name)
        normalized = [
            self.normalize_raw_candidate_name(item.strip())
            for raw in possible
            for item in self.split_candidate_line_names(raw)
            if item.strip() and item.strip() != "未找到"
        ]
        normalized = list(dict.fromkeys(normalized))
        if self.has_force_constraint(car):
            filtered = [line for line in normalized if TerminalForcedPositionMapper.can_map_force_text(car.force_target_position_text, line)]
            if not filtered:
                raise RuntimeError(
                    f"车辆{car.no}的强制对位无法匹配任何候选目标：强制对位={car.force_target_position_text}，候选={','.join(normalized)}"
                )
            normalized = filtered
        car.possible_target_line_names = normalized
        return normalized

    def order_candidate_lines_for_selection(self, possible: list[str], car: Car) -> list[str]:
        normalized = list(dict.fromkeys(self.normalize_raw_candidate_name(line) for line in possible if line.strip()))
        mixed_repair_and_non_repair = not self.has_force_constraint(car) and self.has_mixed_repair_and_non_repair_candidate(normalized)
        if not mixed_repair_and_non_repair:
            return normalized
        return sorted(normalized, key=lambda line: (1 if self.is_repair_line(line) else 0))

    def is_repair_outer_line_candidate(self, line_name: str) -> bool:
        line_name = self.normalize_raw_candidate_name(line_name)
        return line_name in {"修1库外", "修2库外", "修3库外", "修4库外"}

    def is_repair_inner_line_candidate(self, line_name: str) -> bool:
        line_name = self.normalize_raw_candidate_name(line_name)
        return line_name in {"修1", "修2", "修3", "修4"}

    def is_repair_line(self, line_name: str) -> bool:
        return self.is_repair_inner_line_candidate(line_name) or self.is_repair_outer_line_candidate(line_name)

    def is_repair_outer_candidate(self, possible: list[str]) -> bool:
        normalized = list(dict.fromkeys(self.normalize_raw_candidate_name(line) for line in possible if line.strip()))
        return bool(normalized) and all(self.is_repair_outer_line_candidate(line) for line in normalized)

    def is_repair_inner_candidate(self, possible: list[str]) -> bool:
        normalized = list(dict.fromkeys(self.normalize_raw_candidate_name(line) for line in possible if line.strip()))
        return bool(normalized) and all(self.is_repair_inner_line_candidate(line) for line in normalized)

    def has_mixed_repair_and_non_repair_candidate(self, possible: list[str]) -> bool:
        normalized = list(dict.fromkeys(self.normalize_raw_candidate_name(line) for line in possible if line.strip()))
        has_repair = any(self.is_repair_line(line) for line in normalized)
        has_non_repair = any(not self.is_repair_line(line) for line in normalized)
        return has_repair and has_non_repair

    def build_forced_reservation(self, cars: list[Car], capacity_dict: dict[str, int]) -> dict[str, int]:
        result: dict[str, int] = {}
        for car in cars:
            if car is None or not self.has_force_constraint(car):
                continue
            possible = self.normalize_possible_lines(car)
            if len(possible) != 1:
                continue
            line = self.normalize_raw_candidate_name(possible[0])
            result[line] = result.get(line, 0) + 1
        for line, count in result.items():
            capacity = self.get_capacity(line, capacity_dict)
            if count > capacity:
                raise RuntimeError(f"强制对位车辆数量超过线路容量：线路={line}，强制车辆数={count}，容量={capacity}")
        return result

    def has_forced_position_available(self, selected_raw_line_name: str, car: Car, forced_position_usage: dict[str, set[int]]) -> bool:
        selected_raw_line_name = self.normalize_raw_candidate_name(selected_raw_line_name)
        if not self.has_force_constraint(car):
            return True
        allowed_positions = TerminalForcedPositionMapper.parse_allowed_positions(car.force_target_position_text, selected_raw_line_name)
        if not allowed_positions:
            return False
        owner_dict = forced_position_usage.get(selected_raw_line_name, set())
        return any(pos not in owner_dict for pos in allowed_positions)

    def reserve_forced_position_for_car(self, selected_raw_line_name: str, car: Car, forced_position_usage: dict[str, set[int]]) -> int:
        selected_raw_line_name = self.normalize_raw_candidate_name(selected_raw_line_name)
        if not self.has_force_constraint(car):
            return -1
        allowed_positions = TerminalForcedPositionMapper.parse_allowed_positions(car.force_target_position_text, selected_raw_line_name)
        if not allowed_positions:
            raise RuntimeError(f"车辆{car.no}的强制对位无法匹配目标线路：目标={selected_raw_line_name}，强制={car.force_target_position_text}")
        used_positions = forced_position_usage.setdefault(selected_raw_line_name, set())
        selected_position = next((pos for pos in sorted(allowed_positions) if pos not in used_positions), -1)
        if selected_position <= 0:
            raise RuntimeError(
                f"车辆{car.no}的强制对位台位均已被占用：目标={selected_raw_line_name}，强制={car.force_target_position_text}，映射={','.join(map(str, allowed_positions))}"
            )
        used_positions.add(selected_position)
        car.is_force_target_position = True
        car.fixed_target_line_position = selected_position
        car.allowed_target_line_positions = [selected_position]
        return selected_position

    def get_forced_position_choice_score(self, line_name: str, car: Car, forced_position_usage: dict[str, set[int]]) -> int:
        line_name = self.normalize_raw_candidate_name(line_name)
        if not self.has_force_constraint(car):
            return 0
        try:
            allowed = TerminalForcedPositionMapper.parse_allowed_positions(car.force_target_position_text, line_name)
        except Exception:
            return 2**31 - 1
        if not allowed:
            return 2**31 - 1
        used = forced_position_usage.get(line_name, set())
        available_count = sum(1 for pos in allowed if pos not in used)
        return -available_count

    def has_capacity_considering_reservation(
        self,
        line_name: str,
        car: Car,
        used_count: dict[str, int],
        capacity_dict: dict[str, int],
        forced_reservation: dict[str, int],
        forced_position_usage: dict[str, set[int]],
    ) -> bool:
        line_name = self.normalize_raw_candidate_name(line_name)
        used = used_count.get(line_name, 0)
        capacity = self.get_capacity(line_name, capacity_dict)
        if used >= capacity:
            return False
        if self.has_force_constraint(car):
            return self.has_forced_position_available(line_name, car, forced_position_usage)
        reserved = forced_reservation.get(line_name, 0)
        remain_after_assign = capacity - used - 1
        return remain_after_assign >= reserved

    def choose_first_available_line(
        self,
        car: Car,
        possible: list[str],
        used_count: dict[str, int],
        capacity_dict: dict[str, int],
        forced_reservation: dict[str, int],
        forced_position_usage: dict[str, set[int]],
    ) -> str:
        ordered_possible = self.order_candidate_lines_for_selection(possible, car)
        for line in ordered_possible:
            if self.has_capacity_considering_reservation(
                line,
                car,
                used_count,
                capacity_dict,
                forced_reservation,
                forced_position_usage,
            ):
                return line
        raise RuntimeError(f"候选线路均无剩余容量或强制台位，候选={','.join(possible)}")

    def choose_least_used_line(
        self,
        car: Car,
        possible: list[str],
        used_count: dict[str, int],
        capacity_dict: dict[str, int],
        forced_reservation: dict[str, int],
        forced_position_usage: dict[str, set[int]],
    ) -> str:
        ordered_possible = self.order_candidate_lines_for_selection(possible, car)
        mixed_repair_and_non_repair = not self.has_force_constraint(car) and self.has_mixed_repair_and_non_repair_candidate(ordered_possible)
        candidates = [
            (line, index)
            for index, line in enumerate(ordered_possible)
            if self.has_capacity_considering_reservation(
                line,
                car,
                used_count,
                capacity_dict,
                forced_reservation,
                forced_position_usage,
            )
        ]
        if not candidates:
            raise RuntimeError(f"候选线路均无剩余容量或强制台位，候选={','.join(possible)}")
        candidates.sort(
            key=lambda item: (
                1 if mixed_repair_and_non_repair and self.is_repair_line(item[0]) else 0,
                self.get_forced_position_choice_score(item[0], car, forced_position_usage) if self.has_force_constraint(car) else 0,
                used_count.get(item[0], 0),
                self.get_line_priority(item[0]),
                item[1],
            )
        )
        return candidates[0][0]

    def choose_repair_inner_line(
        self,
        car: Car,
        possible: list[str],
        used_count: dict[str, int],
        capacity_dict: dict[str, int],
        forced_reservation: dict[str, int],
        forced_position_usage: dict[str, set[int]],
    ) -> str:
        ordered_possible = self.order_candidate_lines_for_selection(possible, car)
        candidates = [
            (line, index)
            for index, line in enumerate(ordered_possible)
            if self.has_capacity_considering_reservation(
                line,
                car,
                used_count,
                capacity_dict,
                forced_reservation,
                forced_position_usage,
            )
        ]
        if not candidates:
            raise RuntimeError(f"修库内候选线路容量或强制台位不足，候选={','.join(possible)}")
        candidates.sort(
            key=lambda item: (
                self.get_forced_position_choice_score(item[0], car, forced_position_usage) if self.has_force_constraint(car) else 0,
                self.get_line_priority(item[0]),
                used_count.get(item[0], 0),
                item[1],
            )
        )
        return candidates[0][0]

    def assign_car_to_line(
        self,
        car: Car,
        selected_raw_line_name: str,
        used_count: dict[str, int],
        capacity_dict: dict[str, int],
        forced_reservation: dict[str, int],
        forced_position_usage: dict[str, set[int]],
    ) -> None:
        from .terminal import Terminal

        selected_raw_line_name = self.normalize_raw_candidate_name(selected_raw_line_name)
        if not self.has_capacity_considering_reservation(
            selected_raw_line_name,
            car,
            used_count,
            capacity_dict,
            forced_reservation,
            forced_position_usage,
        ):
            raise RuntimeError(f"线路{selected_raw_line_name}容量或强制对位台位不足，不能继续分配车辆{car.no}")
        segment = Terminal.resolve_target_segment(selected_raw_line_name)
        car.target_line_name = segment[0]
        car.target_min_position = segment[1]
        car.target_max_position = segment[2]
        if self.has_force_constraint(car):
            TerminalForcedPositionMapper.apply_to_car(car, selected_raw_line_name)
            self.reserve_forced_position_for_car(selected_raw_line_name, car, forced_position_usage)
        else:
            car.is_force_target_position = False
            car.fixed_target_line_position = -1
            car.allowed_target_line_positions = []
        used_count[selected_raw_line_name] = used_count.get(selected_raw_line_name, 0) + 1
        if self.has_force_constraint(car) and forced_reservation.get(selected_raw_line_name, 0) > 0:
            forced_reservation[selected_raw_line_name] -= 1

    def get_ordered_cars_for_line_planning(self, context) -> list[Car]:
        cars = self.get_all_cars_from_context(context)
        return sorted(
            (
                {
                    "car": car,
                    "has_force": self.has_force_constraint(car),
                    "possible_count": len(self.safe_normalize_possible_lines(car)),
                }
                for car in cars
            ),
            key=lambda item: (
                not item["has_force"],
                item["possible_count"],
                item["car"].origin_line_name,
                item["car"].origin_line_position,
                item["car"].no,
            ),
        )

    def get_all_cars_from_context(self, context) -> list[Car]:
        cars = getattr(context, "cars", None)
        if cars:
            return [car for car in cars.values() if car is not None]
        track_lines = getattr(context, "track_lines", None)
        if not track_lines:
            return []
        result: list[Car] = []
        seen: set[int] = set()
        for line in track_lines.values():
            for car in getattr(line, "current_list", []) or []:
                if car is None or id(car) in seen:
                    continue
                seen.add(id(car))
                result.append(car)
        return result

    def safe_normalize_possible_lines(self, car: Car) -> list[str]:
        try:
            return self.normalize_possible_lines(car)
        except Exception:
            return []

    def build_continuous_groups(self, track_line) -> list[list[Car]]:
        result: list[list[Car]] = []
        current_list = getattr(track_line, "current_list", None) or []
        if not current_list:
            return result
        i = 0
        while i < len(current_list):
            first = current_list[i]
            first_possible = self.normalize_possible_lines(first)
            group = [first]
            j = i + 1
            while j < len(current_list):
                next_car = current_list[j]
                next_possible = self.normalize_possible_lines(next_car)
                if len(first_possible) != len(next_possible) or first_possible != next_possible:
                    break
                group.append(next_car)
                j += 1
            result.append(group)
            i = j
        return result

    def same_set(self, left: list[str], right: list[str]) -> bool:
        if left is None or right is None:
            return False
        left_norm = sorted(set(self.normalize_raw_candidate_name(item) for item in left), key=str)
        right_norm = sorted(set(self.normalize_raw_candidate_name(item) for item in right), key=str)
        return left_norm == right_norm

    def build_continuous_groups_for_strategy(self, track_line) -> list[list[Car]]:
        result: list[list[Car]] = []
        current_list = getattr(track_line, "current_list", None) or []
        if not current_list:
            return result
        i = 0
        while i < len(current_list):
            first_car = current_list[i]
            first_possible = self.get_effective_possible_lines(first_car)
            group = [first_car]
            j = i + 1
            while j < len(current_list):
                next_car = current_list[j]
                next_possible = self.get_effective_possible_lines(next_car)
                if not self.same_set(first_possible, next_possible):
                    break
                group.append(next_car)
                j += 1
            result.append(group)
            i = j
        return result

    def get_effective_possible_lines(self, car: Car) -> list[str]:
        return self.normalize_possible_lines(car)

    def build_initial_forced_position_owner(self, cars: list[Car], state: _LineState) -> None:
        for car in cars:
            if not TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text):
                continue
            possible = self.normalize_possible_lines(car)
            if len(possible) != 1:
                continue
            line = self.normalize_raw_candidate_name(possible[0])
            try:
                positions = TerminalForcedPositionMapper.parse_allowed_positions(car.force_target_position_text, line)
            except Exception:
                continue
            if len(positions) != 1:
                continue
            self.try_reserve_owner(line, positions[0], car.no, state)

    def try_reserve_owner(self, line: str, position: int, car_no: str, state: _LineState) -> None:
        line = self.normalize_raw_candidate_name(line)
        owner_dict = state.forced_position_owner.setdefault(line, {})
        existed_car_no = owner_dict.get(position)
        if existed_car_no is not None and existed_car_no != car_no:
            raise RuntimeError(f"强制对位台位冲突：线路={line}，台位={position}，车辆={existed_car_no} 与 {car_no}")
        owner_dict[position] = car_no

    def has_forced_position_available_with_owner(self, line_name: str, car: Car, state: _LineState) -> bool:
        line_name = self.normalize_raw_candidate_name(line_name)
        try:
            allowed = TerminalForcedPositionMapper.parse_allowed_positions(car.force_target_position_text, line_name)
        except Exception:
            return False
        if not allowed:
            return False
        owner_dict = state.forced_position_owner.get(line_name, {})
        return any(owner_dict.get(pos) in {None, car.no} for pos in allowed)

    def get_forced_position_choice_score_with_owner(self, line_name: str, car: Car, state: _LineState) -> int:
        line_name = self.normalize_raw_candidate_name(line_name)
        if not TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text):
            return 0
        try:
            allowed = TerminalForcedPositionMapper.parse_allowed_positions(car.force_target_position_text, line_name)
        except Exception:
            return 2**31 - 1
        if not allowed:
            return 2**31 - 1
        owner_dict = state.forced_position_owner.get(line_name, {})
        available_count = sum(1 for pos in allowed if owner_dict.get(pos) in {None, car.no})
        return -available_count

    def can_assign_group_to_line_considering_reservation(self, line_name: str, group: list[Car], state: _LineState) -> bool:
        line_name = self.normalize_raw_candidate_name(line_name)
        used = state.used_count.get(line_name, 0)
        capacity = self.get_capacity(line_name, state.capacity_dict)
        reserved = state.forced_reservation.get(line_name, 0)
        temp_owner = dict(state.forced_position_owner.get(line_name, {}))
        for car in group:
            if used >= capacity:
                return False
            if TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text):
                try:
                    allowed = TerminalForcedPositionMapper.parse_allowed_positions(car.force_target_position_text, line_name)
                except Exception:
                    return False
                selected_position = next((pos for pos in allowed if temp_owner.get(pos) in {None, car.no}), -1)
                if selected_position <= 0:
                    return False
                temp_owner[selected_position] = car.no
                used += 1
                if reserved > 0:
                    reserved -= 1
                continue
            remain_after_assign = capacity - used - 1
            if remain_after_assign < reserved:
                return False
            used += 1
        return True

    def reserve_forced_position_for_car_with_owner(self, selected_raw_line_name: str, car: Car, state: _LineState) -> int:
        selected_raw_line_name = self.normalize_raw_candidate_name(selected_raw_line_name)
        allowed_positions = TerminalForcedPositionMapper.parse_allowed_positions(car.force_target_position_text, selected_raw_line_name)
        if not allowed_positions:
            raise RuntimeError(f"车辆{car.no}的强制对位无法匹配目标线路：目标={selected_raw_line_name}，强制={car.force_target_position_text}")
        owner_dict = state.forced_position_owner.setdefault(selected_raw_line_name, {})
        selected_position = next((pos for pos in sorted(allowed_positions) if owner_dict.get(pos) in {None, car.no}), -1)
        if selected_position <= 0:
            raise RuntimeError(
                f"车辆{car.no}的强制对位台位均已被占用：目标={selected_raw_line_name}，强制={car.force_target_position_text}，映射={','.join(map(str, allowed_positions))}"
            )
        owner_dict[selected_position] = car.no
        car.is_force_target_position = True
        car.fixed_target_line_position = selected_position
        car.allowed_target_line_positions = [selected_position]
        return selected_position

    def assign_car_to_line_with_state(self, car: Car, selected_raw_line_name: str, state: _LineState) -> None:
        from .terminal import Terminal

        selected_raw_line_name = self.normalize_raw_candidate_name(selected_raw_line_name)
        if not self.has_capacity_considering_reservation(
            selected_raw_line_name,
            car,
            state.used_count,
            state.capacity_dict,
            state.forced_reservation,
            state.forced_position_usage,
        ):
            raise RuntimeError(f"候选线路均无剩余容量或强制台位，候选={selected_raw_line_name}")
        segment = Terminal.resolve_target_segment(selected_raw_line_name)
        car.target_line_name = segment[0]
        car.target_min_position = segment[1]
        car.target_max_position = segment[2]
        TerminalForcedPositionMapper.apply_to_car(car, selected_raw_line_name)
        if TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text):
            self.reserve_forced_position_for_car_with_owner(selected_raw_line_name, car, state)
        state.used_count[selected_raw_line_name] = state.used_count.get(selected_raw_line_name, 0) + 1
        if TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text) and state.forced_reservation.get(selected_raw_line_name, 0) > 0:
            state.forced_reservation[selected_raw_line_name] -= 1

    def get_line_priority(self, line_name: str) -> int:
        line_name = self.normalize_raw_candidate_name(line_name)
        mapping = {
            "修1": 0,
            "修2": 1,
            "修3": 2,
            "修4": 3,
            "修1库外": 4,
            "修2库外": 5,
            "修3库外": 6,
            "修4库外": 7,
            "抛": 8,
            "油": 9,
            "轮": 10,
            "调北": 11,
            "调棚": 12,
            "调梁": 13,
            "洗北": 14,
            "洗南": 15,
            "洗罐": 16,
            "机棚": 17,
            "机走": 18,
            "机库线": 19,
            "老预修": 20,
            "预修": 21,
        }
        return mapping.get(line_name, 100)

    def assign_lines(self, context) -> None:
        raise NotImplementedError


class BalancedLineStrategy(LinePlannerStrategyBase):
    name = "Balanced"

    def assign_lines(self, context) -> None:
        capacity_dict = self.create_capacity_dict()
        all_cars = [item["car"] for item in self.get_ordered_cars_for_line_planning(context)]
        state = _LineState(
            used_count={},
            capacity_dict=capacity_dict,
            forced_reservation=self.build_forced_reservation(all_cars, capacity_dict),
            forced_position_usage={},
        )
        for car in all_cars:
            possible = self.normalize_possible_lines(car)
            if not possible:
                continue
            if len(possible) == 1:
                selected = possible[0]
            elif self.is_repair_outer_candidate(possible):
                selected = self.choose_least_used_line(car, possible, state.used_count, state.capacity_dict, state.forced_reservation, state.forced_position_usage)
            elif self.is_repair_inner_candidate(possible):
                selected = self.choose_repair_inner_line(car, possible, state.used_count, state.capacity_dict, state.forced_reservation, state.forced_position_usage)
            else:
                selected = self.choose_least_used_line(car, possible, state.used_count, state.capacity_dict, state.forced_reservation, state.forced_position_usage)
            self.assign_car_to_line(car, selected, state.used_count, state.capacity_dict, state.forced_reservation, state.forced_position_usage)


class ConservativeLineStrategy(LinePlannerStrategyBase):
    name = "Conservative"

    def assign_lines(self, context) -> None:
        capacity_dict = self.create_capacity_dict()
        all_cars = [item["car"] for item in self.get_ordered_cars_for_line_planning(context)]
        state = _LineState(
            used_count={},
            capacity_dict=capacity_dict,
            forced_reservation=self.build_forced_reservation(all_cars, capacity_dict),
            forced_position_usage={},
        )
        for car in all_cars:
            possible = self.normalize_possible_lines(car)
            if not possible:
                continue
            if len(possible) == 1:
                selected = possible[0]
            elif self.is_repair_outer_candidate(possible):
                selected = self.choose_first_available_line(car, possible, state.used_count, state.capacity_dict, state.forced_reservation, state.forced_position_usage)
            elif self.is_repair_inner_candidate(possible):
                selected = self.choose_repair_inner_line(car, possible, state.used_count, state.capacity_dict, state.forced_reservation, state.forced_position_usage)
            else:
                selected = self.choose_first_available_line(car, possible, state.used_count, state.capacity_dict, state.forced_reservation, state.forced_position_usage)
            self.assign_car_to_line(car, selected, state.used_count, state.capacity_dict, state.forced_reservation, state.forced_position_usage)


class SameSourceContinuousLineStrategy(LinePlannerStrategyBase):
    name = "SameSourceContinuous"

    def assign_lines(self, context) -> None:
        all_cars = self.get_all_cars_from_context(context)
        state = _LineState(
            used_count={},
            capacity_dict=self.create_capacity_dict(),
            forced_reservation=self.build_forced_reservation(all_cars, self.create_capacity_dict()),
            forced_position_usage={},
            forced_position_owner={},
        )
        self.build_initial_forced_position_owner(all_cars, state)
        for track_line in getattr(context, "track_lines", {}).values():
            current_list = getattr(track_line, "current_list", None) or []
            if not current_list:
                continue
            groups = self.build_continuous_groups_for_strategy(track_line)
            for group in groups:
                self.assign_group(group, state)

    def assign_group(self, group: list[Car], state: _LineState) -> None:
        if not group:
            return
        first_possible = self.get_effective_possible_lines(group[0])
        if not first_possible:
            return
        all_same_candidate_set = all(self.same_set(first_possible, self.get_effective_possible_lines(car)) for car in group)
        if all_same_candidate_set:
            self.assign_same_candidate_group_continuously(group, first_possible, state)
            return
        for car in group:
            possible = self.get_effective_possible_lines(car)
            if not possible:
                continue
            selected = self.choose_line_for_single_car(car, possible, state)
            self.assign_car_to_line_with_state(car, selected, state)

    def assign_same_candidate_group_continuously(self, group: list[Car], possible: list[str], state: _LineState) -> None:
        selected_line = self.choose_line_for_whole_group(possible, group, state)
        if selected_line:
            for car in group:
                self.assign_car_to_line_with_state(car, selected_line, state)
            return
        for car in group:
            selected = self.choose_line_for_single_car(car, possible, state)
            self.assign_car_to_line_with_state(car, selected, state)

    def choose_line_for_whole_group(self, possible: list[str], group: list[Car], state: _LineState) -> str | None:
        if not possible or not group:
            return None
        mixed_repair_and_non_repair = all(not TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text) for car in group) and self.has_mixed_repair_and_non_repair_candidate(possible)
        candidates = sorted(
            [(self.normalize_raw_candidate_name(line), index) for index, line in enumerate(dict.fromkeys(possible))],
            key=lambda item: (
                1 if mixed_repair_and_non_repair and self.is_repair_line(item[0]) else 0,
                self.get_line_priority_for_this_strategy(item[0]),
                state.used_count.get(item[0], 0),
                item[1],
            ),
        )
        for line, _ in candidates:
            if self.can_assign_group_to_line_considering_reservation(line, group, state):
                return line
        return None

    def choose_line_for_single_car(self, car: Car, possible: list[str], state: _LineState) -> str:
        if not possible:
            raise RuntimeError(f"车辆{car.no}没有可用候选线路。")
        mixed_repair_and_non_repair = not TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text) and self.has_mixed_repair_and_non_repair_candidate(possible)
        candidates = [
            (self.normalize_raw_candidate_name(line), index)
            for index, line in enumerate(dict.fromkeys(possible))
            if self.has_capacity_considering_reservation(
                line,
                car,
                state.used_count,
                state.capacity_dict,
                state.forced_reservation,
                state.forced_position_usage,
            )
        ]
        candidates.sort(
            key=lambda item: (
                1 if mixed_repair_and_non_repair and self.is_repair_line(item[0]) else 0,
                self.get_forced_position_choice_score_with_owner(item[0], car, state) if TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text) else 0,
                self.get_line_priority_for_this_strategy(item[0]),
                state.used_count.get(item[0], 0),
                item[1],
            )
        )
        if not candidates:
            raise RuntimeError(f"候选线路均无剩余容量或强制台位，候选={','.join(possible)}")
        return candidates[0][0]

    def get_line_priority_for_this_strategy(self, line_name: str) -> int:
        line_name = self.normalize_raw_candidate_name(line_name)
        mapping = {
            "修1": 0, "修2": 1, "修3": 2, "修4": 3,
            "修1库外": 4, "修2库外": 5, "修3库外": 6, "修4库外": 7,
        }
        return mapping.get(line_name, 20)


class RepairOverflowSpreadLineStrategy(LinePlannerStrategyBase):
    name = "RepairOverflowSpread"

    def assign_lines(self, context) -> None:
        all_cars = self.get_all_cars_from_context(context)
        capacity_dict = self.create_capacity_dict()
        state = _LineState(
            used_count={},
            capacity_dict=capacity_dict,
            forced_reservation=self.build_forced_reservation(all_cars, capacity_dict),
            forced_position_usage={},
            forced_position_owner={},
        )
        self.build_initial_forced_position_owner(all_cars, state)
        for track_line in getattr(context, "track_lines", {}).values():
            current_list = getattr(track_line, "current_list", None) or []
            if not current_list:
                continue
            groups = self.build_continuous_groups_for_strategy(track_line)
            for group in groups:
                self.assign_group(group, state)

    def assign_group(self, group: list[Car], state: _LineState) -> None:
        if not group:
            return
        first_possible = self.get_effective_possible_lines(group[0])
        if not first_possible:
            return
        all_same_candidate = all(self.same_set(first_possible, self.get_effective_possible_lines(car)) for car in group)
        if all_same_candidate:
            selected_line = self.choose_line_for_whole_group(first_possible, group, state)
            if selected_line:
                for car in group:
                    self.assign_car_to_line_with_state(car, selected_line, state)
                return
        for car in group:
            possible = self.get_effective_possible_lines(car)
            if not possible:
                continue
            selected = self.choose_line_for_single_car(car, possible, state)
            self.assign_car_to_line_with_state(car, selected, state)

    def choose_line_for_whole_group(self, possible: list[str], group: list[Car], state: _LineState) -> str | None:
        if not possible or not group:
            return None
        mixed_repair_and_non_repair = all(
            not TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text) for car in group
        ) and self.has_mixed_repair_and_non_repair_candidate(possible)
        candidates = sorted(
            [(self.normalize_raw_candidate_name(line), index) for index, line in enumerate(dict.fromkeys(possible))],
            key=lambda item: (
                1 if mixed_repair_and_non_repair and self.is_repair_line(item[0]) else 0,
                state.used_count.get(item[0], 0),
                self.get_line_priority_for_this_strategy(item[0]),
                item[1],
            ),
        )
        for line, _ in candidates:
            if self.can_assign_group_to_line_considering_reservation(line, group, state):
                return line
        return None

    def choose_line_for_single_car(self, car: Car, possible: list[str], state: _LineState) -> str:
        if not possible:
            raise RuntimeError(f"车辆{car.no}没有可用候选线路。")
        mixed_repair_and_non_repair = (
            not TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text)
            and self.has_mixed_repair_and_non_repair_candidate(possible)
        )
        candidates = [
            (self.normalize_raw_candidate_name(line), index)
            for index, line in enumerate(dict.fromkeys(possible))
            if self.has_capacity_considering_reservation(
                line,
                car,
                state.used_count,
                state.capacity_dict,
                state.forced_reservation,
                state.forced_position_usage,
            )
        ]
        candidates.sort(
            key=lambda item: (
                1 if mixed_repair_and_non_repair and self.is_repair_line(item[0]) else 0,
                self.get_forced_position_choice_score_with_owner(item[0], car, state)
                if TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text)
                else 0,
                state.used_count.get(item[0], 0),
                self.get_line_priority_for_this_strategy(item[0]),
                item[1],
            )
        )
        if not candidates:
            raise RuntimeError(f"候选线路均无剩余容量或强制台位，候选={','.join(possible)}")
        return candidates[0][0]

    def get_line_priority_for_this_strategy(self, line_name: str) -> int:
        line_name = self.normalize_raw_candidate_name(line_name)
        mapping = {
            "修1": 0, "修2": 1, "修3": 2, "修4": 3,
            "修1库外": 4, "修2库外": 5, "修3库外": 6, "修4库外": 7,
        }
        return mapping.get(line_name, 20)


class LinePlanner:
    @staticmethod
    def assign(context, strategy: LinePlannerStrategyBase | None = None) -> None:
        from .terminal import Terminal

        if context is None:
            raise RuntimeError("TerminalContext为空，无法执行线规划。")
        planner = strategy or BalancedLineStrategy()
        if planner is None:
            raise RuntimeError("LinePlannerStrategy为空，无法执行线规划。")

        cars = getattr(context, "cars", None)
        if cars is None:
            cars = getattr(context, "CarDict")

        for car in cars.values():
            if car.possible_target_line_names is None:
                car.possible_target_line_names = []
            if not car.possible_target_line_names and car.target_line_name:
                car.possible_target_line_names.append(car.target_line_name)
            if len(car.possible_target_line_names) == 1:
                segment = Terminal.resolve_target_segment(car.possible_target_line_names[0])
                car.target_line_name = segment[0]
                car.target_min_position = segment[1]
                car.target_max_position = segment[2]
            else:
                car.target_line_name = ""
                car.target_min_position = 0
                car.target_max_position = -1

        planner.assign_lines(context)

        unassigned = [car.no for car in cars.values() if not car.target_line_name]
        if unassigned:
            sample = ", ".join(unassigned[:10])
            raise RuntimeError(f"LineStrategy={planner.name} 未完成线路分配：{len(unassigned)}辆车，示例：{sample}")
