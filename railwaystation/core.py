from __future__ import annotations

import os

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Callable, Iterable


class ActionType(str, Enum):
    GET = "Get"
    PUT = "Put"
    WEIGH = "Weigh"


class TaskStatus(Enum):
    NOT_STARTED = 0
    COMPLETED = 1
    RUNNING = 2
    SKIPPED = 3
    PAUSED = 4


class TrackLineName(str, Enum):
    机库线 = "机库线"
    调梁 = "调梁"
    机走 = "机走"
    老预修 = "老预修"
    喷漆 = "喷漆"
    洗罐 = "洗罐"
    抛丸线 = "抛丸线"
    卸轮线 = "卸轮线"
    修1 = "修1"
    修2 = "修2"
    修3 = "修3"
    修4 = "修4"
    存1线 = "存1线"
    存2线 = "存2线"
    存3线 = "存3线"
    存4线 = "存4线"
    存5线 = "存5线"
    Z1_Z2_Z3 = "Z1_Z2_Z3"
    train = "train"


class FileTrackName(str, Enum):
    老预修 = "老预修"
    喷漆库 = "喷漆库"
    机库线 = "机库线"
    机走预修 = "机走预修"
    调梁库 = "调梁库"
    修1库外 = "修1库外"
    修1库内 = "修1库内"
    修2库外 = "修2库外"
    修2库内 = "修2库内"
    卸轮线 = "卸轮线"
    存1线 = "存1线"
    存3线 = "存3线"
    存5线北 = "存5线北"
    存5线南 = "存5线南"
    抛丸线 = "抛丸线"
    洗罐线 = "洗罐线"
    修3库外 = "修3库外"
    修3库内 = "修3库内"
    修4库外 = "修4库外"
    修4库内 = "修4库内"
    存2线 = "存2线"
    存4线 = "存4线"
    喷漆库外 = "喷漆库外"
    喷漆库内 = "喷漆库内"
    调梁库外 = "调梁库外"
    调梁库内 = "调梁库内"
    洗罐线外 = "洗罐线外"
    洗罐线内 = "洗罐线内"
    洗罐库外 = "洗罐库外"
    洗罐库内 = "洗罐库内"


class Constraint:
    is_put_jz_finished = False
    is_put_cun4_finished = False
    max_train_count = 20

    @classmethod
    def is_over_train_count_limit(cls, train: "Train", add_cars: list["Car"]) -> bool:
        train_heavy_count = sum(1 for car in train.current_list if car.is_heavy)
        add_heavy_count = sum(1 for car in add_cars if car.is_heavy)
        total_heavy_count = train_heavy_count + add_heavy_count
        over_heavy_limit = total_heavy_count > 2
        over_count_limit = len(train.current_list) + len(add_cars) + total_heavy_count * 3 > cls.max_train_count
        return over_heavy_limit or over_count_limit

    IsOverTrainCountLimit = is_over_train_count_limit


TRACE_ENABLED = os.environ.get("RAILWAY_TRACE", "") == "1"
TRACE_ROUNDS = {
    int(item)
    for item in os.environ.get("RAILWAY_TRACE_ROUNDS", "").split(",")
    if item.strip().isdigit()
}


def _trace_enabled(round_idx: int | None = None) -> bool:
    if not TRACE_ENABLED:
        return False
    if not TRACE_ROUNDS:
        return True
    if round_idx is None:
        return True
    return round_idx in TRACE_ROUNDS


def _trace(message: str, round_idx: int | None = None) -> None:
    if _trace_enabled(round_idx):
        print(f"[TRACE]{'' if round_idx is None else f'[R{round_idx}]'} {message}")


@dataclass(eq=False)
class Car:
    no: str = ""
    type: str = ""
    length: Decimal = Decimal("11")
    current_line_id: int = 0
    origin_line_name: str = ""
    origin_line_name_second: str = ""
    origin_line_position: int = 0
    possible_target_line_names: list[str] = field(default_factory=list)
    target_min_position: int = 0
    target_max_position: int = -1
    target_line_id: int = 0
    target_line_name: str = ""
    target_line_name_second: str = ""
    target_line_position: int = 0
    is_force_target_position: bool = False
    fixed_target_line_position: int = -1
    force_target_position_text: str = ""
    allowed_target_line_positions: list[int] = field(default_factory=list)
    is_closed_door: bool = False
    is_heavy: bool = False
    is_weigh: bool = False
    is_weighed: bool = False
    current_line: "TrackLine" | None = None
    target_line: "TrackLine" | None = None

    @staticmethod
    def _try_index(items: list["Car"], target: "Car") -> int:
        for index, item in enumerate(items):
            if item is target:
                return index
        return -1

    @property
    def current_line_name(self) -> str:
        return self.current_line.name if self.current_line else ""

    @property
    def is_current_top(self) -> bool:
        return bool(self.current_line and self.current_line.current_top_car is self)

    @property
    def is_target_top(self) -> bool:
        return bool(self.target_line and self.target_line.target_top_car is self)

    @property
    def is_in_train(self) -> bool:
        return self.current_line_name == TrackLineName.train.value

    @property
    def current_depth(self) -> int:
        return self._try_index(self.current_line.current_list, self)

    @property
    def current_bottom_depth(self) -> int:
        return len(self.current_line.current_list) - self._try_index(self.current_line.current_list, self)

    @property
    def target_depth(self) -> int:
        return self._try_index(self.target_line.target_list, self)

    @property
    def origin_target_bottom_depth(self) -> int:
        return len(self.current_line.origin_target_list) - self._try_index(self.current_line.origin_target_list, self)

    @property
    def is_need_move(self) -> bool:
        return self.current_line_name != self.target_line_name or self.current_bottom_depth != self.origin_target_bottom_depth

    @property
    def is_current_top_and_can_get_direct(self) -> bool:
        return self.is_current_top and self.current_line.is_can_arrived and self.current_line.track_line_name != TrackLineName.机走

    @property
    def continuous_cars(self) -> list["Car"]:
        cars = [self]
        current_line = self.current_line
        target_line = self.target_line
        current_index = current_line.current_list.index(self)
        origin_target_index = target_line.origin_target_list.index(self)
        length = 1

        if current_line.track_line_name == TrackLineName.train:
            while (
                current_index + length <= len(current_line.current_list) - 1
                and origin_target_index - length >= 0
                and current_line.current_list[current_index + length].target_line is target_line
                and current_line.current_list[current_index + length].target_line_position
                == target_line.origin_target_list[origin_target_index - length].target_line_position
            ):
                car = current_line.current_list[current_index + length]
                if car.is_heavy or car.is_weigh:
                    break
                cars.append(car)
                length += 1
        else:
            while (
                current_index + length <= len(current_line.current_list) - 1
                and origin_target_index + length <= len(target_line.origin_target_list) - 1
                and current_line.current_list[current_index + length].target_line is target_line
                and current_line.current_list[current_index + length].target_line_position
                == target_line.origin_target_list[origin_target_index + length].target_line_position
            ):
                car = current_line.current_list[current_index + length]
                if car.is_heavy or car.is_weigh:
                    break
                cars.append(car)
                length += 1
        return cars

    @property
    def is_target_line_wanted_continuous(self) -> bool:
        target_list = [car for car in self.target_line.origin_target_list if car.is_need_move]
        continuous_cars = self.continuous_cars
        if len(continuous_cars) > len(target_list):
            raise RuntimeError("连续车辆数量已经超过目标线需求")
        last_target_index = len(target_list) - 1
        return all(continuous_cars[i] is target_list[last_target_index - i] for i in range(len(continuous_cars)))

    @property
    def next_target_car(self) -> "Car | None":
        line = self.target_line
        index = self._try_index(line.target_list, self)
        if index == len(line.target_list) - 1:
            return None
        car = line.target_list[index + 1]
        return car if car.is_need_move else None

    @property
    def next_car(self) -> "Car | None":
        line = self.target_line
        index = self._try_index(line.origin_target_list, self)
        if index == len(line.origin_target_list) - 1:
            return None
        car = line.origin_target_list[index + 1]
        return car if car.is_need_move else None

    @property
    def remain_origin_target_cars(self) -> list["Car"]:
        result: list[Car] = []
        index = self._try_index(self.target_line.origin_target_list, self)
        if index < 0:
            return result
        movable = [car for car in self.target_line.origin_target_list if car.is_need_move]
        if not movable:
            return result
        last_need_move_car = movable[-1]
        last_index = self._try_index(self.target_line.origin_target_list, last_need_move_car)
        if last_index < 0:
            return result
        for i in range(index + 1, last_index + 1):
            result.append(self.target_line.origin_target_list[i])
        return result

    No = property(lambda self: self.no, lambda self, value: setattr(self, "no", value))
    Type = property(lambda self: self.type, lambda self, value: setattr(self, "type", value))
    Length = property(lambda self: self.length, lambda self, value: setattr(self, "length", value))
    CurrentLineId = property(lambda self: self.current_line_id, lambda self, value: setattr(self, "current_line_id", value))
    CurrentLineName = property(lambda self: self.current_line_name)
    OriginLineName = property(lambda self: self.origin_line_name, lambda self, value: setattr(self, "origin_line_name", value))
    OriginLineName_Second = property(lambda self: self.origin_line_name_second, lambda self, value: setattr(self, "origin_line_name_second", value))
    OriginLinePosition = property(lambda self: self.origin_line_position, lambda self, value: setattr(self, "origin_line_position", value))
    PossibleTargetLineNames = property(lambda self: self.possible_target_line_names, lambda self, value: setattr(self, "possible_target_line_names", value))
    TargetMinPosition = property(lambda self: self.target_min_position, lambda self, value: setattr(self, "target_min_position", value))
    TargetMaxPosition = property(lambda self: self.target_max_position, lambda self, value: setattr(self, "target_max_position", value))
    TargetLineId = property(lambda self: self.target_line_id, lambda self, value: setattr(self, "target_line_id", value))
    TargetLineName = property(lambda self: self.target_line_name, lambda self, value: setattr(self, "target_line_name", value))
    TargetLineName_Second = property(lambda self: self.target_line_name_second, lambda self, value: setattr(self, "target_line_name_second", value))
    TargetLinePosition = property(lambda self: self.target_line_position, lambda self, value: setattr(self, "target_line_position", value))
    IsForceTargetPosition = property(lambda self: self.is_force_target_position, lambda self, value: setattr(self, "is_force_target_position", value))
    FixedTargetLinePosition = property(lambda self: self.fixed_target_line_position, lambda self, value: setattr(self, "fixed_target_line_position", value))
    ForceTargetPositionText = property(lambda self: self.force_target_position_text, lambda self, value: setattr(self, "force_target_position_text", value))
    AllowedTargetLinePositions = property(lambda self: self.allowed_target_line_positions, lambda self, value: setattr(self, "allowed_target_line_positions", value))
    IsClosedDoor = property(lambda self: self.is_closed_door, lambda self, value: setattr(self, "is_closed_door", value))
    IsHeavy = property(lambda self: self.is_heavy, lambda self, value: setattr(self, "is_heavy", value))
    IsWeigh = property(lambda self: self.is_weigh, lambda self, value: setattr(self, "is_weigh", value))
    IsWeighed = property(lambda self: self.is_weighed, lambda self, value: setattr(self, "is_weighed", value))
    CurrentLine = property(lambda self: self.current_line, lambda self, value: setattr(self, "current_line", value))
    TargetLine = property(lambda self: self.target_line, lambda self, value: setattr(self, "target_line", value))
    IsCurrentTop = property(lambda self: self.is_current_top)
    IsTargetTop = property(lambda self: self.is_target_top)
    IsInTrain = property(lambda self: self.is_in_train)
    CurrentDepth = property(lambda self: self.current_depth)
    CurrentBottomDepth = property(lambda self: self.current_bottom_depth)
    TargetDepth = property(lambda self: self.target_depth)
    OriginTargetBottomDepth = property(lambda self: self.origin_target_bottom_depth)
    IsNeedMove = property(lambda self: self.is_need_move)
    IsCurrentTopAndCanGetDirect = property(lambda self: self.is_current_top_and_can_get_direct)
    ContinuousCars = property(lambda self: self.continuous_cars)
    IsTargetLineWantedContinuous = property(lambda self: self.is_target_line_wanted_continuous)
    NextTargetCar = property(lambda self: self.next_target_car)
    NextCar = property(lambda self: self.next_car)
    RemainOriginTargetCars = property(lambda self: self.remain_origin_target_cars)


@dataclass(eq=False)
class TrackLine:
    id: int = 0
    name: str = ""
    ori_capacity: Decimal = Decimal("0")
    current_list: list[Car] = field(default_factory=list)
    target_list: list[Car] = field(default_factory=list)
    origin_target_list: list[Car] = field(default_factory=list)
    priority: int = 0
    is_can_arrived: bool = True
    is_cache: bool = False
    cache_reserved_capacity: Decimal = Decimal("0")
    on_current_cleared: list[Callable[["TrackLine"], None]] = field(default_factory=list)
    on_target_cleared: list[Callable[["TrackLine"], None]] = field(default_factory=list)
    on_blocked: list[Callable[["TrackLine"], None]] = field(default_factory=list)
    on_finished: list[Callable[["TrackLine"], None]] = field(default_factory=list)

    @property
    def track_line_name(self) -> TrackLineName:
        return TrackLineName(self.name)

    @property
    def rem_capacity(self) -> Decimal:
        return self.ori_capacity - sum((car.length for car in self.current_list), Decimal("0"))

    @property
    def cache_usable_capacity(self) -> Decimal:
        result = self.rem_capacity - self.cache_reserved_capacity
        return result if result > 0 else Decimal("0")

    @property
    def current_top_car(self) -> Car | None:
        if not any(car.is_need_move for car in self.current_list):
            return None
        return self.current_list[0]

    @property
    def target_top_car(self) -> Car | None:
        if not any(car.is_need_move for car in self.target_list):
            return None
        return self.target_list[0]

    @property
    def is_cleared(self) -> bool:
        return not any(car.is_need_move for car in self.current_list)

    @property
    def is_finished(self) -> bool:
        return all(car in self.current_list for car in self.origin_target_list)

    @property
    def is_blocked(self) -> bool:
        return bool(self.current_list)

    @property
    def is_all_target_can_arrived(self) -> bool:
        return all(car.current_line.is_can_arrived for car in self.target_list if car.is_need_move)

    def _emit(self, callbacks: list[Callable[["TrackLine"], None]]) -> None:
        for callback in callbacks:
            callback(self)

    def push_current(self, car: Car) -> None:
        if not self.current_list:
            self._emit(self.on_blocked)
        self.current_list.insert(0, car)
        car.current_line = self
        if self.is_finished:
            self._emit(self.on_finished)

    def pop_current(self) -> Car | None:
        if not self.current_list:
            return None
        car = self.current_list.pop(0)
        if self.is_cleared:
            self._emit(self.on_current_cleared)
        if self.is_finished:
            self._emit(self.on_finished)
        return car

    def push_target(self, car: Car) -> None:
        self.target_list.insert(0, car)

    def pop_target(self) -> Car | None:
        if not self.target_list:
            return None
        car = self.target_list.pop(0)
        if self.target_top_car is None:
            self._emit(self.on_target_cleared)
        return car

    def unshift_current(self, car: Car) -> None:
        self.current_list.append(car)
        car.current_line = self

    def shift_current(self) -> Car | None:
        if not self.current_list:
            return None
        car = self.current_list.pop()
        return car

    def unshift_target(self, car: Car) -> None:
        self.target_list.append(car)
        car.target_line = self

    def shift_target(self) -> Car | None:
        if not self.target_list:
            return None
        car = self.target_list[-1]
        self.target_list.pop(len(self.current_list) - 1)
        return car

    def unshift_origin_target(self, car: Car) -> None:
        self.origin_target_list.append(car)

    def receive_line_cleared_notification(self, track_line: "TrackLine", track_line_manager: "TrackLineManager") -> None:
        if not self.is_can_arrived and any(car.target_line is track_line for car in self.current_list):
            if (
                self.current_top_car
                and self.current_top_car.target_line.track_line_name == TrackLineName.机走
                and len(track_line_manager.remain_target_track_line_list) > 1
            ):
                return
            if not Constraint.is_put_jz_finished and Actions.is_can_cache_in_jzyx(self.track_line_name):
                return
            if self.track_line_name == TrackLineName.机走 and not Constraint.is_put_cun4_finished:
                return
            if self.track_line_name in {TrackLineName.喷漆, TrackLineName.洗罐}:
                self.is_can_arrived = not track_line_manager.get_track_line(TrackLineName.机走).is_blocked
            else:
                self.is_can_arrived = True

    def print_info(self) -> None:
        print(f"{self.name},可达:{self.is_can_arrived}")
        print("当前车辆：" + "".join(
            f"{'*' if car.is_current_top else ''}【{car.current_depth}::{car.type}-{car.no}=>{car.target_line_name}{car.target_line_name_second}-{car.target_line_position}"
            f"{'*重车' if car.is_heavy else ''}"
            f"{'*称重' if car.is_weigh else ''}】"
            for car in self.current_list
        ))
        print("剩余目标：" + "".join(
            f"{'*' if car.is_target_top else ''}【{car.target_depth}::{car.type}-{car.no}=>{car.target_line_name}-{car.target_line_name_second}-{car.target_line_position}】"
            for car in self.target_list
        ))
        print("初始目标：" + "".join(
            f"{'*' if car.is_target_top else ''}【{index}::{car.type}-{car.no}=>{car.current_line.track_line_name.value}-{car.current_depth},{car.current_line.is_can_arrived}】"
            for index, car in enumerate(self.origin_target_list)
        ))

    def get_car_groups(self) -> list["CarGroup"]:
        car_groups: list[CarGroup] = []
        car = self.current_list[0] if self.current_list else None
        while car is not None and self.current_list.index(car) <= len(self.current_list) - 1:
            continuous_cars = car.continuous_cars
            car_group = CarGroup()
            for tmp_car in continuous_cars:
                car_group.cars.append(tmp_car)
            car_groups.append(car_group)
            last_index = self.current_list.index(continuous_cars[-1])
            if last_index < len(self.current_list) - 1:
                car = self.current_list[last_index + 1]
            else:
                break
        return car_groups

    Id = property(lambda self: self.id, lambda self, value: setattr(self, "id", value))
    Name = property(lambda self: self.name, lambda self, value: setattr(self, "name", value))
    Ori_capacity = property(lambda self: self.ori_capacity, lambda self, value: setattr(self, "ori_capacity", value))
    Rem_capacity = property(lambda self: self.rem_capacity)
    TrackLineName = property(lambda self: self.track_line_name)
    CurrentList = property(lambda self: self.current_list, lambda self, value: setattr(self, "current_list", value))
    TargetList = property(lambda self: self.target_list, lambda self, value: setattr(self, "target_list", value))
    OriginTargetList = property(lambda self: self.origin_target_list, lambda self, value: setattr(self, "origin_target_list", value))
    Priority = property(lambda self: self.priority, lambda self, value: setattr(self, "priority", value))
    CurrentTopCar = property(lambda self: self.current_top_car)
    TargetTopCar = property(lambda self: self.target_top_car)
    IsCanArrived = property(lambda self: self.is_can_arrived, lambda self, value: setattr(self, "is_can_arrived", value))
    IsCache = property(lambda self: self.is_cache, lambda self, value: setattr(self, "is_cache", value))
    CacheReservedCapacity = property(lambda self: self.cache_reserved_capacity, lambda self, value: setattr(self, "cache_reserved_capacity", value))
    CacheUsableCapacity = property(lambda self: self.cache_usable_capacity)
    IsCleared = property(lambda self: self.is_cleared)
    IsFinished = property(lambda self: self.is_finished)
    IsBlocked = property(lambda self: self.is_blocked)
    IsAllTargetCanArrived = property(lambda self: self.is_all_target_can_arrived)
    PushCurrent = push_current
    PopCurrent = pop_current
    PushTarget = push_target
    PopTarget = pop_target
    UnshiftCurrent = unshift_current
    ShiftCurrent = shift_current
    UnshiftTarget = unshift_target
    ShiftTarget = shift_target
    UnshiftOriginTarget = unshift_origin_target
    ReceiveLineClearedNotification = receive_line_cleared_notification
    PrintInfo = print_info
    GetCarGroups = get_car_groups


@dataclass
class CarGroup:
    cars: list[Car] = field(default_factory=list)

    @property
    def top_car(self) -> Car:
        return self.cars[0]

    @property
    def bottom_car(self) -> Car:
        return self.cars[-1]

    @property
    def target_line(self) -> TrackLine:
        return self.top_car.target_line

    @property
    def current_line(self) -> TrackLine:
        return self.top_car.current_line

    @property
    def is_target_top(self) -> bool:
        return self.top_car.is_target_top

    @property
    def next_target_car(self) -> Car | None:
        return self.bottom_car.next_target_car

    Cars = property(lambda self: self.cars, lambda self, value: setattr(self, "cars", value))
    TopCar = property(lambda self: self.top_car)
    BottomCar = property(lambda self: self.bottom_car)
    TargetLine = property(lambda self: self.target_line)
    CurrentLine = property(lambda self: self.current_line)
    IsTargetTop = property(lambda self: self.is_target_top)
    NextTargetCar = property(lambda self: self.next_target_car)


@dataclass(eq=False)
class Train(TrackLine):
    @property
    def current_list_count(self) -> int:
        return len(self.current_list)

    @property
    def wanted_car(self) -> Car | None:
        return self.current_top_car.next_target_car if self.current_top_car else None

    def is_contain_all_line_target(self, track_line: TrackLine) -> bool:
        target_list = [car for car in track_line.origin_target_list if car.is_need_move]
        all_cars = self.current_list + track_line.current_list
        return all(car in all_cars for car in target_list)

    def get_not_contain_target_cars(self, track_line: TrackLine) -> list[Car]:
        target_list = [car for car in track_line.origin_target_list if car.is_need_move]
        return [car for car in target_list if car not in self.current_list]

    def get_target_line_is_all_contained(self) -> dict[TrackLine, bool]:
        status: dict[TrackLine, bool] = {}
        for car in self.current_list:
            line = car.target_line
            if line not in status:
                status[line] = False
        for line in list(status.keys()):
            status[line] = self.is_contain_all_line_target(line)
        return status

    def is_current_top_continuous_fit_targets(self, cached_cars: list[Car] | None = None) -> bool:
        if self.current_top_car is None:
            return False
        cars: list[Car] = []
        i = 0
        last_car: Car | None = None
        while i < len(self.current_list):
            current_car = self.current_list[i]
            if last_car is not None and last_car.target_line is not current_car.target_line:
                break
            cars.append(current_car)
            last_car = current_car
            i += 1
        target_list = [car for car in self.current_top_car.target_line.origin_target_list if car.is_need_move]
        all_cars = list(cars) + list(self.current_top_car.target_line.current_list)
        if cached_cars is not None:
            all_cars.extend(cached_cars)
        return all(car in all_cars for car in target_list)

    def print_train_info(self) -> None:
        print(
            f"TrainInfo::{len(self.current_list)},重车【{sum(1 for item in self.current_list if item.is_heavy)}】,"
            f"称重【{sum(1 for item in self.current_list if item.is_weigh)}】"
            + "".join(
                f"【{'*' if item.is_current_top else ''}{item.no}-{item.origin_line_name}-{item.origin_line_position} -> {item.target_line_name}-{item.target_line_position}"
                f"{'*重车' if item.is_heavy else ''}"
                f"{'*称重' if item.is_weigh else ''}】"
                for item in self.current_list
            )
        )

    CurrentListCount = property(lambda self: self.current_list_count)
    WantedCar = property(lambda self: self.wanted_car)
    IsContainAllLineTarget = is_contain_all_line_target
    GetNotContainTargetCars = get_not_contain_target_cars
    GetTargetLineIsAllContained = get_target_line_is_all_contained
    IsCurrentTopContinuousFitTargets = is_current_top_continuous_fit_targets
    PrintTrainInfo = print_train_info


@dataclass
class Operation:
    line_name: str = ""
    action: ActionType = ActionType.GET
    index: int = 0
    move_cars: list[Car] = field(default_factory=list)
    train_cars: list[Car] = field(default_factory=list)
    line_cars_before: list[Car] = field(default_factory=list)
    line_cars_after: list[Car] = field(default_factory=list)

    @property
    def move_car_count(self) -> int:
        return len(self.move_cars)

    @property
    def train_cars_count(self) -> int:
        return len(self.train_cars)

    @property
    def line_cars_befor_count(self) -> int:
        return len(self.line_cars_before)

    @property
    def line_cars_after_count(self) -> int:
        return len(self.line_cars_after)

    def copy_train_cars(self, train: Train) -> None:
        for item in train.current_list:
            self.train_cars.append(item)

    def copy_line_cars_before(self, line: TrackLine) -> None:
        for item in line.current_list:
            self.line_cars_before.append(item)

    def copy_line_cars_after(self, line: TrackLine) -> None:
        for item in line.current_list:
            self.line_cars_after.append(item)

    LineName = property(lambda self: self.line_name, lambda self, value: setattr(self, "line_name", value))
    Action = property(lambda self: self.action, lambda self, value: setattr(self, "action", value))
    Index = property(lambda self: self.index, lambda self, value: setattr(self, "index", value))
    MoveCars = property(lambda self: self.move_cars, lambda self, value: setattr(self, "move_cars", value))
    TrainCars = property(lambda self: self.train_cars, lambda self, value: setattr(self, "train_cars", value))
    LineCarsBefore = property(lambda self: self.line_cars_before, lambda self, value: setattr(self, "line_cars_before", value))
    LineCarsAfter = property(lambda self: self.line_cars_after, lambda self, value: setattr(self, "line_cars_after", value))
    MoveCarCount = property(lambda self: self.move_car_count)
    TrainCarsCount = property(lambda self: self.train_cars_count)
    LineCarsBeforCount = property(lambda self: self.line_cars_befor_count)
    LineCarsAfterCount = property(lambda self: self.line_cars_after_count)
    CopyTrainCars = copy_train_cars
    CopyLineCarsBefore = copy_line_cars_before
    CopyLineCarsAfter = copy_line_cars_after


class Actions:
    @staticmethod
    def move_car_from_line_to_train_continuously(car: Car, train: Train, operation: Operation) -> None:
        current_line = car.current_line
        target_line = car.target_line
        _trace(
            "continuous_get start "
            f"seed={car.no} line={current_line.name} target={target_line.name} "
            f"target_top={(target_line.target_top_car.no if target_line.target_top_car else None)}",
        )
        Actions.move_car_from_line_to_train(car, train, True)
        operation.move_cars.append(car)
        while (
            current_line.current_top_car
            and target_line.target_top_car
            and current_line.current_top_car.target_line_name == target_line.name
            and current_line.current_top_car.target_line_position == target_line.target_top_car.target_line_position
            and not Constraint.is_over_train_count_limit(train, [current_line.current_top_car])
        ):
            tmp = current_line.current_top_car
            _trace(
                "continuous_get extend "
                f"next={tmp.no} next_target_pos={tmp.target_line_position} "
                f"target_top={(target_line.target_top_car.no if target_line.target_top_car else None)}:"
                f"{(target_line.target_top_car.target_line_position if target_line.target_top_car else None)}",
            )
            Actions.move_car_from_line_to_train(tmp, train, True)
            operation.move_cars.append(tmp)
        _trace(
            "continuous_get end "
            f"cars={[item.no for item in operation.move_cars]} "
            f"remaining_top={(current_line.current_top_car.no if current_line.current_top_car else None)}",
        )

    @staticmethod
    def move_car_from_line_to_train(car: Car, train: Train, is_remove_from_target: bool) -> None:
        if not car.is_current_top:
            raise RuntimeError(f"目标车辆【{car.no}】不是第一节，无法取车")
        if Constraint.is_over_train_count_limit(train, [car]):
            raise RuntimeError(f"机车超限，无法取车：{car.no}")
        car.current_line.pop_current()
        train.push_current(car)
        if is_remove_from_target and car is car.target_line.target_top_car:
            car.target_line.pop_target()

    @staticmethod
    def move_car_from_train_to_line(car: Car, train: Train, target_track_line: TrackLine, is_push_to_target_list: bool = False) -> None:
        if not car.is_current_top:
            raise RuntimeError(f"目标车辆【{car.no}】不是第一节，无法从列车释放")
        train.pop_current()
        target_track_line.push_current(car)
        if is_push_to_target_list and car not in car.target_line.target_list:
            car.target_line.push_target(car)

    @staticmethod
    def try_get_previous_car(car: Car) -> tuple[bool, Car | None]:
        for item in car.target_line.target_list:
            if item.is_in_train:
                continue
            if not item.current_line.is_can_arrived:
                return False, item
            if item.no == car.no:
                return True, None
        return False, None

    @staticmethod
    def print_remain_car_count(cars: dict[str, Car]) -> None:
        remain_count = sum(1 for car in cars.values() if car.is_need_move)
        print(f"剩余车辆：【{remain_count}】")

    @staticmethod
    def increase_last_target_line_put_priority(train: Train, task_manager: "TaskManager") -> None:
        last_target = train.current_top_car.target_line if train.current_top_car else None
        if last_target and train.current_top_car.is_target_line_wanted_continuous:
            task = task_manager.get_task(f"Put_{last_target.track_line_name.value}")
            if task:
                task.priority = BackwardConstructionAlgorithm.current_put_car_task_priority
                BackwardConstructionAlgorithm.current_put_car_task_priority += 1

    @staticmethod
    def is_can_cache_in_jzyx(track_line_name: TrackLineName) -> bool:
        return (
            track_line_name == TrackLineName.机走
            or track_line_name == TrackLineName.卸轮线
            or track_line_name.value.startswith("修")
        )

    IsCanCacheInJZYX = is_can_cache_in_jzyx
    MoveCarFromLineToTrainContinuously = move_car_from_line_to_train_continuously
    MoveCarFromLineToTrain = move_car_from_line_to_train
    MoveCarFromTrainToLine = move_car_from_train_to_line
    TryGetPreviousCar = try_get_previous_car
    PrintRemainCarCount = print_remain_car_count
    IncreaseLastTargetLinePutPriority = increase_last_target_line_put_priority


class TaskItem:
    def __init__(self, task_id: str, priority: int = 0, dependencies: Iterable[str] | None = None, can_skip: bool = False) -> None:
        self.id = task_id
        self.priority = priority
        self.dependencies = set(dependencies or [])
        self.can_skip = can_skip

    def execute(self) -> tuple[TaskStatus, bool]:
        raise NotImplementedError

    Id = property(lambda self: self.id)
    Priority = property(lambda self: self.priority, lambda self, value: setattr(self, "priority", value))
    Dependencies = property(lambda self: self.dependencies)
    CanSkip = property(lambda self: self.can_skip)


class TaskManager:
    def __init__(self) -> None:
        self.on_task_completed: list[Callable[[TaskItem], None]] = []
        self._tasks: dict[str, TaskItem] = {}
        self._task_status: dict[str, TaskStatus] = {}

    def add_task(self, task: TaskItem) -> None:
        if task.id in self._tasks:
            task.priority = max(self._tasks[task.id].priority, task.priority)
        self._tasks[task.id] = task
        self._task_status[task.id] = TaskStatus.NOT_STARTED

    def get_all_task_ids(self) -> list[str]:
        return list(self._tasks.keys())

    def get_ready_tasks(self) -> list[TaskItem]:
        ready: list[tuple[TaskItem, TaskStatus]] = []
        for task_id, task in self._tasks.items():
            status = self._task_status[task_id]
            if status == TaskStatus.COMPLETED:
                continue
            deps_satisfied = all(self._task_status.get(dep) == TaskStatus.COMPLETED for dep in task.dependencies)
            if not deps_satisfied:
                continue
            if status in {TaskStatus.NOT_STARTED, TaskStatus.RUNNING, TaskStatus.SKIPPED}:
                ready.append((task, status))
        ready.sort(key=lambda item: (item[1].value, -item[0].priority))
        return [task for task, _ in ready]

    def set_task_status(self, task_id: str, status: TaskStatus) -> None:
        if task_id not in self._tasks:
            return
        if status == TaskStatus.COMPLETED:
            for callback in self.on_task_completed:
                callback(self._tasks[task_id])
        self._task_status[task_id] = status

    def get_task(self, task_id: str) -> TaskItem | None:
        return self._tasks.get(task_id)

    def get_task_status(self, task_id: str) -> TaskStatus:
        return self._task_status.get(task_id, TaskStatus.NOT_STARTED)

    def pause_all_tasks(self) -> None:
        for task_id, status in list(self._task_status.items()):
            if status != TaskStatus.COMPLETED:
                self._task_status[task_id] = TaskStatus.PAUSED

    def resume_all_tasks(self) -> None:
        for task_id, status in list(self._task_status.items()):
            if status == TaskStatus.PAUSED:
                self._task_status[task_id] = TaskStatus.NOT_STARTED

    AddTask = add_task
    GetAllTaskIds = get_all_task_ids
    GetReadyTasks = get_ready_tasks
    SetTaskStatus = set_task_status
    GetTask = get_task
    GetTaskStatus = get_task_status
    PauseAllTasks = pause_all_tasks
    ResumeAllTasks = resume_all_tasks


class BCTaskManager(TaskManager):
    def reset_all_task_priority_to_zero(self) -> None:
        for task in self._tasks.values():
            task.priority = 0

    def remove_tasks_except_put(self) -> None:
        keys = [key for key in self._tasks if not key.startswith("Put_")]
        for key in keys:
            self._tasks.pop(key, None)
            self._task_status.pop(key, None)

    def remove_get_tasks(self) -> None:
        keys = [key for key in self._tasks if key.startswith("Get_")]
        for key in keys:
            self._tasks.pop(key, None)
            self._task_status.pop(key, None)

    def create_clear_line_task(self, cache_line: TrackLine, track_line_manager: "TrackLineManager", train: Train) -> None:
        task_id = f"Clear_{cache_line.track_line_name.value}"
        task = self.get_task(task_id)
        if task is None:
            self.add_task(ClearLine(cache_line.track_line_name, track_line_manager, self, train, priority=1, can_skip=True))
        else:
            self.set_task_status(task.id, TaskStatus.NOT_STARTED)

    ResetAllTaskPriorityToZero = reset_all_task_priority_to_zero
    RemoveTasksExceptPut = remove_tasks_except_put
    RemoveGetTasks = remove_get_tasks
    CreateClearLineTask = create_clear_line_task


class CarManager:
    def __init__(self, cars: dict[str, Car]) -> None:
        self.cars = cars

    @property
    def cars_dict(self) -> dict[str, Car]:
        return self.cars

    @property
    def jzyx_remain(self) -> list[Car]:
        return [
            car
            for car in self.cars.values()
            if car.current_line.track_line_name != TrackLineName.机走
            and Actions.is_can_cache_in_jzyx(car.target_line.track_line_name)
            and car.current_line.is_can_arrived
            and car.is_need_move
        ]

    @property
    def is_jzyx_finished(self) -> bool:
        return not self.jzyx_remain

    @property
    def remain_cars(self) -> list[Car]:
        return [car for car in self.cars.values() if car.is_need_move]

    @property
    def remain_weigh_cars(self) -> list[Car]:
        return [car for car in self.cars.values() if car.is_weigh and not car.is_weighed]

    def print_remain_car_info(self) -> None:
        print("剩余可移动车辆：")
        print("".join(
            f"【{item.no},{item.current_line.is_can_arrived}:{item.current_line.track_line_name.value}-{item.current_bottom_depth}"
            f"=>{item.target_line_name}{item.target_line_name_second}-{item.target_line_position}】"
            for item in self.remain_cars
        ))

    Cars = property(lambda self: self.cars)
    IsJZYXFinished = property(lambda self: self.is_jzyx_finished)
    JZYXRemain = property(lambda self: self.jzyx_remain)
    RemainCars = property(lambda self: self.remain_cars)
    RemainWeighCars = property(lambda self: self.remain_weigh_cars)
    PrintRemainCarInfo = print_remain_car_info


class OperationManager:
    def __init__(self, train: Train) -> None:
        self.train = train
        self.operations: list[Operation] = []

    def add(self, operation: Operation) -> None:
        last_operation = self.operations[-1] if self.operations else None
        _trace(
            "OperationManager.add before "
            f"line={operation.line_name} action={operation.action.value} "
            f"cars={[car.no for car in operation.move_cars]}",
        )
        if last_operation and last_operation.action == operation.action and last_operation.line_name == operation.line_name:
            last_operation.move_cars.extend(operation.move_cars)
            last_operation.train_cars = operation.train_cars
            last_operation.line_cars_after = operation.line_cars_after
            _trace(
                "OperationManager.add merged "
                f"line={last_operation.line_name} action={last_operation.action.value} "
                f"cars={[car.no for car in last_operation.move_cars]}",
            )
            return
        self.operations.append(operation)
        operation.index = len(self.operations)
        _trace(
            "OperationManager.add appended "
            f"index={operation.index} line={operation.line_name} action={operation.action.value} "
            f"cars={[car.no for car in operation.move_cars]}",
        )

    def print_operations_info(self) -> None:
        for item in self.operations:
            self.print_operation(item)

    def print_operation(self, operation: Operation) -> None:
        action_name = {
            ActionType.GET: "取车",
            ActionType.PUT: "存车",
            ActionType.WEIGH: "称重",
        }[operation.action]
        op_index = self.operations.index(operation) + 1 if operation in self.operations else operation.index
        print(f"========={action_name}操作 {op_index} =========")
        print(
            f"Action::{operation.line_name},{operation.action.value},{len(operation.move_cars)},"
            + "".join(
                f"【{item.no}-{item.origin_line_name}-{item.origin_line_position} -> {item.target_line_name}-{item.target_line_position}】"
                for item in operation.move_cars
            )
        )
        print(
            f"CopyTrainInfo::{len(operation.train_cars)}"
            + "".join(
                f"【{'*' if item.is_current_top else ''}{item.no}-{item.origin_line_name}-{item.origin_line_position} -> {item.target_line_name}-{item.target_line_position}】"
                for item in operation.train_cars
            )
        )
        print(
            f"LineCarsAfter::{operation.line_cars_after_count}"
            + "".join(
                f"【{item.no}-{item.current_line_name}-{item.current_depth} -> {item.target_line_name}-{item.target_line_position}】"
                for item in operation.line_cars_after
            )
        )
        if operation.action == ActionType.PUT:
            seen: list[TrackLine] = []
            for item in operation.move_cars:
                if item.target_line not in seen:
                    seen.append(item.target_line)
            for line in seen:
                line.print_info()

    Operations = property(lambda self: self.operations)
    Add = add
    PrintOperationsInfo = print_operations_info
    PrintOperation = print_operation


class CacheStrategySimple:
    functional_lines = {"喷漆库", "调梁库"}

    def __init__(self, distance_calculator: Callable[[str, str], int]) -> None:
        self.distance_calculator = distance_calculator

    def select_best_cache_line(
        self,
        current_source_line: TrackLine,
        blocking_cars_batch: list[Car],
        all_lines: Iterable[TrackLine],
        last_used_cache_line: TrackLine | None,
    ) -> TrackLine | None:
        if not blocking_cars_batch:
            return None
        total_length = sum(car.length for car in blocking_cars_batch)
        candidates = [
            line
            for line in all_lines
            if line.is_cache and line.is_can_arrived and line.cache_usable_capacity >= total_length and line.name != current_source_line.name
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda line: self._calculate_cost(line, current_source_line, blocking_cars_batch, last_used_cache_line),
        )

    def _calculate_cost(
        self,
        line: TrackLine,
        current: TrackLine,
        cars: list[Car],
        last_used: TrackLine | None,
    ) -> float:
        cost = self.distance_calculator(current.name, line.name) * 2.0
        is_jzx_car = any(car.target_line_name == TrackLineName.机走.value or "机走" in car.target_line_name for car in cars)
        has_continuous_car = any(car.is_target_line_wanted_continuous for car in cars)
        if is_jzx_car and line.current_list:
            return 1_000_000.0
        cost += -1000 if not line.current_list and has_continuous_car else -600 if not line.current_list else 800 if has_continuous_car else 400
        if last_used and line.name == last_used.name:
            cost -= 500
        if line.track_line_name == TrackLineName.机走:
            cost += 600
        if line.track_line_name == TrackLineName.老预修 and not any(car.target_line is line for car in cars):
            cost -= 900
        is_functional = line.name in self.functional_lines or line.track_line_name.value in self.functional_lines
        if is_functional:
            is_target_for_batch = any(car.target_line_name in {line.name, line.track_line_name.value} for car in cars)
            if not is_target_for_batch:
                cost += 3000
        return cost

    def calculate_cost(
        self,
        line: TrackLine,
        current: TrackLine,
        cars: list[Car],
        last_used: TrackLine | None,
    ) -> float:
        return self._calculate_cost(line, current, cars, last_used)

    SelectBestCacheLine = select_best_cache_line
    CalculateCost = calculate_cost


class TrackLineManager:
    shared_cache_replacement_line = TrackLineName.老预修
    disabled_dedicated_cache_line = TrackLineName.Z1_Z2_Z3

    def __init__(self, track_lines: dict[str, TrackLine], cars: dict[str, Car], distance_matrix: dict[str, dict[str, int]]) -> None:
        self.track_lines = track_lines
        self.cars = cars
        self.distance_matrix = distance_matrix
        self.cache_strategy = CacheStrategySimple(self.get_distance)
        self._init_cache_line()
        for line in track_lines.values():
            line.on_blocked.append(self.on_line_blocked)
            line.on_current_cleared.append(self.on_line_current_cleared)
            line.on_finished.append(self.on_line_finished)
        self._refresh_dynamic_cache_line_state()

    @property
    def track_lines_dict(self) -> dict[str, TrackLine]:
        return self.track_lines

    def get_distance(self, from_node: str, to_node: str) -> int:
        return self.distance_matrix.get(from_node, {}).get(to_node, 0)

    @property
    def remain_target_track_line_list(self) -> list[TrackLine]:
        result: list[TrackLine] = []
        for car in self.cars.values():
            if not car.is_need_move:
                continue
            if car.target_line not in result:
                result.append(car.target_line)
        return result

    def on_line_finished(self, line: TrackLine) -> None:
        if len(self.remain_target_track_line_list) == 1 and self.remain_target_track_line_list[0].track_line_name == TrackLineName.机走:
            for car in self.cars.values():
                if car.target_line.track_line_name == TrackLineName.机走 and car.is_need_move:
                    car.current_line.is_can_arrived = True
        if line.track_line_name not in {
            TrackLineName.机走,
            self.disabled_dedicated_cache_line,
            self.shared_cache_replacement_line,
        }:
            line.is_cache = True
        self._refresh_dynamic_cache_line_state()

    def on_line_blocked(self, line: TrackLine) -> None:
        if line.track_line_name == TrackLineName.机走:
            self.track_lines[TrackLineName.喷漆.value].is_can_arrived = False
            self.track_lines[TrackLineName.洗罐.value].is_can_arrived = False
        self._refresh_dynamic_cache_line_state()

    def on_line_current_cleared(self, line: TrackLine) -> None:
        if line.track_line_name == TrackLineName.机走:
            self.track_lines[TrackLineName.喷漆.value].is_can_arrived = True
            self.track_lines[TrackLineName.洗罐.value].is_can_arrived = True
        if line.track_line_name in {TrackLineName.喷漆, TrackLineName.洗罐} and self.track_lines[TrackLineName.机走.value].is_blocked:
            return
        for item in self.track_lines.values():
            if item.track_line_name == TrackLineName.train:
                continue
            item.receive_line_cleared_notification(line, self)
        self._refresh_dynamic_cache_line_state()

    def _init_cache_line(self) -> None:
        for line in self.track_lines.values():
            line.is_cache = line.is_finished
            line.cache_reserved_capacity = Decimal("0")
        for line_name in [TrackLineName.修1, TrackLineName.修2, TrackLineName.修3, TrackLineName.修4, TrackLineName.机走]:
            self.track_lines[line_name.value].is_cache = False
        if self.disabled_dedicated_cache_line.value in self.track_lines:
            self.track_lines[self.disabled_dedicated_cache_line.value].is_cache = False
        if self.shared_cache_replacement_line.value in self.track_lines:
            self.track_lines[self.shared_cache_replacement_line.value].is_cache = False
        self._refresh_dynamic_cache_line_state()

    def _refresh_dynamic_cache_line_state(self) -> None:
        disabled = self.track_lines.get(self.disabled_dedicated_cache_line.value)
        if disabled is not None:
            disabled.is_cache = False
            disabled.cache_reserved_capacity = Decimal("0")

        shared = self.track_lines.get(self.shared_cache_replacement_line.value)
        if shared is None:
            return

        shared.cache_reserved_capacity = sum(
            (
                car.length
                for car in self.cars.values()
                if car.is_need_move and car.target_line is shared and car.current_line is not shared
            ),
            Decimal("0"),
        )
        has_movable_cars_on_line = any(car.is_need_move for car in shared.current_list)
        shared.is_cache = not has_movable_cars_on_line and shared.cache_usable_capacity > 0

    def _get_emergency_shared_cache_line(self, current_line: TrackLine, cache_car_list: list[Car]) -> TrackLine | None:
        shared = self.track_lines.get(self.shared_cache_replacement_line.value)
        if shared is None or shared is current_line or not shared.is_can_arrived:
            return None
        total_cache_length = sum((car.length for car in cache_car_list), Decimal("0"))
        if shared.rem_capacity < total_cache_length:
            return None
        return shared

    def get_track_line(self, track_line_name: TrackLineName) -> TrackLine:
        return self.track_lines[track_line_name.value]

    def open_repair_lines(self, task_manager: BCTaskManager) -> None:
        for line_name in [TrackLineName.修1, TrackLineName.修2, TrackLineName.修3, TrackLineName.修4, TrackLineName.卸轮线]:
            self.track_lines[line_name.value].is_can_arrived = True
        for line in self.track_lines.values():
            line.priority = 1 if line.track_line_name == TrackLineName.存4线 else 0
        task_manager.add_task(GetCar(TrackLineName.存4线, self, priority=1, can_skip=True))

    def reset_cache_jz_line_priority_to_max(self) -> None:
        for line in self.track_lines.values():
            line.priority = int(2**31 - 1) if Actions.is_can_cache_in_jzyx(line.track_line_name) else 0

    def print_track_line_info_simple(self) -> None:
        parts = [
            f"【{item.name},可达:{item.is_can_arrived},优先级:{item.priority},车辆数:{len(item.current_list)}】"
            for item in self.track_lines.values()
        ]
        print("=========轨道信息=========")
        print("".join(parts))

    def print_track_line_info(self) -> None:
        for _, track_line in sorted(self.track_lines.items(), key=lambda item: item[0]):
            track_line.print_info()

    def init_track_line(self) -> None:
        for line_name in [TrackLineName.修1, TrackLineName.修2, TrackLineName.修3, TrackLineName.修4, TrackLineName.卸轮线]:
            self.track_lines[line_name.value].is_can_arrived = False
        if self.track_lines[TrackLineName.机走.value].current_list:
            self.track_lines[TrackLineName.喷漆.value].is_can_arrived = False
            self.track_lines[TrackLineName.洗罐.value].is_can_arrived = False

    def get_cache_line(
        self,
        current_line: TrackLine,
        cache_car_list: list[Car],
        car_manager: CarManager,
        last_used_cache_line: TrackLine | None = None,
        target_car: Car | None = None,
    ) -> TrackLine:
        self._refresh_dynamic_cache_line_state()
        first_car = cache_car_list[0] if cache_car_list else None
        if first_car is None:
            raise RuntimeError("没有需要缓存的车辆")
        total_cache_length = sum(car.length for car in cache_car_list)
        is_shared_cache_target_batch = any(
            car.target_line.track_line_name == self.shared_cache_replacement_line for car in cache_car_list
        )

        if (
            first_car.is_target_line_wanted_continuous
            and first_car.target_line.track_line_name != TrackLineName.机走
            and first_car.target_line.is_cleared
            and first_car.target_line.is_can_arrived
            and first_car.target_line.rem_capacity >= total_cache_length
        ):
            return first_car.target_line

        if (
            not first_car.target_line.is_can_arrived
            and Actions.is_can_cache_in_jzyx(first_car.target_line.track_line_name)
            and first_car.is_target_line_wanted_continuous
            and (
                target_car is None
                or target_car.current_line.track_line_name not in {TrackLineName.喷漆, TrackLineName.洗罐}
            )
        ):
            return self.track_lines[TrackLineName.机走.value]

        track_lines = list(self.track_lines.values())
        if car_manager.remain_weigh_cars:
            track_lines = [line for line in track_lines if line.track_line_name != TrackLineName.机库线]
        if is_shared_cache_target_batch:
            track_lines = [line for line in track_lines if line.track_line_name != self.shared_cache_replacement_line]
        if not Constraint.is_put_jz_finished:
            track_lines = [
                line
                for line in track_lines
                if not any(Actions.is_can_cache_in_jzyx(car.target_line.track_line_name) for car in line.current_list)
            ]
        track_lines = [line for line in track_lines if line.cache_usable_capacity >= total_cache_length]
        best_line = self.cache_strategy.select_best_cache_line(current_line, cache_car_list, track_lines, last_used_cache_line)
        if best_line:
            return best_line
        if last_used_cache_line and last_used_cache_line.cache_usable_capacity >= total_cache_length:
            return last_used_cache_line
        emergency_shared_cache_line = self._get_emergency_shared_cache_line(current_line, cache_car_list)
        if emergency_shared_cache_line is not None:
            return emergency_shared_cache_line
        raise RuntimeError("全场缓存空间耗尽，调度死锁。")

    TrackLines = property(lambda self: self.track_lines)
    RemainTargetTrackLineList = property(lambda self: self.remain_target_track_line_list)
    GetDistance = get_distance
    OnLineFinished = on_line_finished
    OnLineBlocked = on_line_blocked
    OnLineCurrentCleared = on_line_current_cleared
    GetTrackLine = get_track_line
    OpenRepairLines = open_repair_lines
    ResetCacheJZLinePriorityToMax = reset_cache_jz_line_priority_to_max
    PrintTrackLineInfoSimple = print_track_line_info_simple
    PrintTrackLineInfo = print_track_line_info
    InitTrackLine = init_track_line
    GetCacheLine = get_cache_line
    _InitCacheLine = _init_cache_line
    _RefreshDynamicCacheLineState = _refresh_dynamic_cache_line_state


class GetCar(TaskItem):
    def __init__(self, track_line_name: TrackLineName, track_line_manager: TrackLineManager, priority: int = 0, dependencies: Iterable[str] | None = None, can_skip: bool = False) -> None:
        super().__init__(f"Get_{track_line_name.value}", priority, dependencies, can_skip)
        self.track_line_name = track_line_name
        self.track_manager = track_line_manager

    def execute(self) -> tuple[TaskStatus, bool]:
        line = self.track_manager.get_track_line(self.track_line_name)
        if line.target_top_car is None:
            return TaskStatus.COMPLETED, False
        line.priority += self.priority
        return TaskStatus.RUNNING, False

    Execute = execute


class ClearLine(TaskItem):
    def __init__(self, track_line_name: TrackLineName, track_lines: TrackLineManager, task_manager: TaskManager, train: Train, priority: int = 0, dependencies: Iterable[str] | None = None, can_skip: bool = False) -> None:
        super().__init__(f"Clear_{track_line_name.value}", priority, dependencies, can_skip)
        self.track_line_name = track_line_name
        self.track_manager = track_lines
        self.task_manager = task_manager
        self.train = train

    def execute(self) -> tuple[TaskStatus, bool]:
        if self.task_manager.get_task_status(self.id) == TaskStatus.PAUSED:
            return TaskStatus.PAUSED, False
        line = self.track_manager.get_track_line(self.track_line_name)
        car = line.current_top_car
        if car is None:
            return TaskStatus.COMPLETED, False
        result, not_get_car = Actions.try_get_previous_car(car)
        if result:
            target_lines: list[TrackLine] = []
            for item in line.current_list:
                if not item.is_need_move:
                    continue
                if item.target_line not in target_lines:
                    target_lines.append(item.target_line)
            for item in target_lines:
                item.priority = min((2**31 - 1), item.priority + self.priority)
            return TaskStatus.RUNNING, False
        if self.can_skip:
            return TaskStatus.SKIPPED, False
        car = line.current_top_car
        while line.current_top_car is not None:
            Actions.move_car_from_line_to_train(car, self.train, True)
        return TaskStatus.COMPLETED, False

    Execute = execute


class PutCar(TaskItem):
    def __init__(self, task_manager: BCTaskManager, target_line_name: TrackLineName, track_line_manager: TrackLineManager, train: Train, car_manager: CarManager, operation_manager: OperationManager, priority: int = 0, dependencies: Iterable[str] | None = None) -> None:
        super().__init__(f"Put_{target_line_name.value}", priority, dependencies, can_skip=True)
        self.task_manager = task_manager
        self.target_line_name = target_line_name
        self.track_line_manager = track_line_manager
        self.train = train
        self.car_manager = car_manager
        self.operation_manager = operation_manager

    def execute(self) -> tuple[TaskStatus, bool]:
        if self.task_manager.get_task_status(self.id) == TaskStatus.PAUSED:
            return TaskStatus.PAUSED, False
        target_line = self.track_line_manager.get_track_line(self.target_line_name)
        if target_line.is_finished:
            return TaskStatus.COMPLETED, False
        need_skip, force_skip_other_task = self._is_need_skip(target_line)
        if need_skip:
            return TaskStatus.SKIPPED, force_skip_other_task
        cache_line: TrackLine | None = None
        is_need_get_back = False
        if self.train.current_top_car and (
            self.train.current_top_car.target_line is not target_line
            or (self.train.current_top_car.target_line is target_line and not self.train.current_top_car.is_target_line_wanted_continuous)
        ):
            status, cache_line, is_need_get_back = self._cache_different_target_cars(target_line)
            if status == TaskStatus.SKIPPED:
                return TaskStatus.SKIPPED, True
        self._put_target_cars(target_line)
        if is_need_get_back and cache_line is not None:
            self._get_cached_cars(cache_line)
        Actions.increase_last_target_line_put_priority(self.train, self.task_manager)
        if target_line.is_finished:
            return TaskStatus.COMPLETED, False
        return TaskStatus.SKIPPED, True

    def _is_need_skip(self, target_line: TrackLine) -> tuple[bool, bool]:
        if self.train.current_top_car is None:
            return True, False
        if not target_line.is_can_arrived:
            return True, False
        if not target_line.is_cleared:
            task = self.task_manager.get_task(f"Clear_{target_line.track_line_name.value}")
            if task is None:
                self.task_manager.add_task(ClearLine(target_line.track_line_name, self.track_line_manager, self.task_manager, self.train, priority=1, can_skip=True))
            return True, False
        if self.train.wanted_car and self.train.wanted_car.is_current_top_and_can_get_direct:
            return True, False
        if (
            self.train.current_top_car
            and self.train.current_top_car.target_line is target_line
            and self.train.current_top_car.is_target_line_wanted_continuous
            and not self.train.current_top_car.target_line.is_all_target_can_arrived
        ):
            return False, False
        if not self.train.is_contain_all_line_target(target_line):
            task = self.task_manager.get_task(f"Get_{target_line.track_line_name.value}")
            if task is None:
                task = GetCar(target_line.track_line_name, self.track_line_manager, can_skip=True)
                self.task_manager.add_task(task)
            task.priority += 1
            return True, False
        return False, False

    def _get_cached_cars(self, cache_line: TrackLine) -> None:
        operation_get = Operation(line_name=cache_line.name, action=ActionType.GET)
        operation_get.copy_line_cars_before(cache_line)
        while cache_line.current_top_car is not None:
            tmp = cache_line.current_top_car
            operation_get.move_cars.append(tmp)
            Actions.move_car_from_line_to_train(tmp, self.train, False)
        self.operation_manager.add(operation_get)
        operation_get.copy_train_cars(self.train)
        operation_get.copy_line_cars_after(cache_line)

    def _put_target_cars(self, target_line: TrackLine) -> None:
        operation_put = Operation(line_name=self.target_line_name.value, action=ActionType.PUT)
        operation_put.copy_line_cars_before(target_line)
        while self.train.current_top_car is not None and self.train.current_top_car.target_line is target_line and self.train.current_top_car.is_target_line_wanted_continuous:
            tmp = self.train.current_top_car
            operation_put.move_cars.append(tmp)
            Actions.move_car_from_train_to_line(tmp, self.train, target_line, False)
        is_put_more = False
        while target_line.is_finished and self.train.current_top_car is not None and not self.train.current_top_car.target_line.is_cleared:
            task_put_jz = self.task_manager.get_task(f"Put_{TrackLineName.机走.value}")
            if task_put_jz is None or Actions.is_can_cache_in_jzyx(self.train.current_top_car.target_line.track_line_name):
                break
            line = self.train.current_top_car.target_line
            while self.train.current_top_car is not None and self.train.current_top_car.target_line is line:
                tmp = self.train.current_top_car
                operation_put.move_cars.append(tmp)
                Actions.move_car_from_train_to_line(tmp, self.train, target_line, True)
            is_put_more = True
        if is_put_more:
            target_line.is_can_arrived = False
            task = self.task_manager.get_task(f"Clear_{target_line.track_line_name.value}")
            if task is None:
                self.task_manager.add_task(ClearLine(target_line.track_line_name, self.track_line_manager, self.task_manager, self.train, priority=1, can_skip=True))
        self.operation_manager.add(operation_put)
        operation_put.copy_train_cars(self.train)
        operation_put.copy_line_cars_after(target_line)

    def _cache_different_target_cars(self, target_line: TrackLine) -> tuple[TaskStatus, TrackLine | None, bool]:
        operation_cache: Operation | None = None
        cache_line: TrackLine | None = None
        is_need_get_back = False
        while self.train.current_top_car is not None and (
            self.train.current_top_car.target_line is not target_line
            or (self.train.current_top_car.target_line is target_line and not self.train.current_top_car.is_target_line_wanted_continuous)
        ):
            tmp = self.train.current_top_car
            if tmp.is_target_line_wanted_continuous and tmp.target_line.is_can_arrived and tmp.target_line.is_cleared:
                Actions.increase_last_target_line_put_priority(self.train, self.task_manager)
                return TaskStatus.SKIPPED, None, False
            if self.train.wanted_car is not None and self.train.wanted_car.is_current_top_and_can_get_direct:
                return TaskStatus.SKIPPED, None, False
            cars = tmp.continuous_cars
            cache_line = self.track_line_manager.get_cache_line(target_line, cars, self.car_manager)
            operation_cache = Operation(line_name=cache_line.name, action=ActionType.PUT)
            operation_cache.copy_line_cars_before(cache_line)
            for car in cars:
                Actions.move_car_from_train_to_line(car, self.train, cache_line, True)
                operation_cache.move_cars.append(car)
            self.operation_manager.add(operation_cache)
            operation_cache.copy_train_cars(self.train)
            operation_cache.copy_line_cars_after(cache_line)
            if cache_line.track_line_name != TrackLineName.机走 and (not cars[0].target_line.is_can_arrived or not cars[0].target_line.is_cleared):
                cache_line.is_can_arrived = False
                self.task_manager.create_clear_line_task(cache_line, self.track_line_manager, self.train)
            if cache_line.track_line_name == TrackLineName.机走:
                task = PutCarToJZLine(self.track_line_manager, self.train, self.operation_manager, self.task_manager, self.car_manager, priority=1)
                self.task_manager.add_task(task)
        return TaskStatus.RUNNING, cache_line, is_need_get_back

    Execute = execute
    _IsNeedSkip = _is_need_skip
    _GetCachedCars = _get_cached_cars
    _PutTargetCars = _put_target_cars
    _CacheDiffrentTargetCars = _cache_different_target_cars


class PutCarToJZLine(TaskItem):
    def __init__(self, track_line_manager: TrackLineManager, train: Train, operation_manager: OperationManager, task_manager: BCTaskManager, car_manager: CarManager, priority: int = 0, dependencies: Iterable[str] | None = None, can_skip: bool = False) -> None:
        super().__init__(f"Put_{TrackLineName.机走.value}", priority, dependencies, can_skip)
        self.track_line_manager = track_line_manager
        self.train = train
        self.operation_manager = operation_manager
        self.task_manager = task_manager
        self.car_manager = car_manager
        self.is_already_set_line_priority = False
        self.is_completed_once = False

    def execute(self) -> tuple[TaskStatus, bool]:
        if self.task_manager.get_task_status(self.id) == TaskStatus.PAUSED:
            return TaskStatus.PAUSED, False
        target_line = self.track_line_manager.get_track_line(TrackLineName.机走)
        if (
            self.car_manager.jzyx_remain
            and not Constraint.is_over_train_count_limit(self.train, self.car_manager.jzyx_remain)
            and self.train.current_top_car
            and self.train.current_top_car.target_line.track_line_name != TrackLineName.机走
        ):
            return TaskStatus.SKIPPED, False
        if (
            self.car_manager.jzyx_remain
            and not any(
                Actions.is_can_cache_in_jzyx(car.target_line.track_line_name) and self._is_car_can_put(car, target_line)
                for car in self.train.current_list
            )
        ):
            return TaskStatus.SKIPPED, False
        if self.train.wanted_car and self.train.wanted_car.is_current_top_and_can_get_direct:
            return TaskStatus.SKIPPED, False
        if (
            self.train.current_top_car
            and self.train.current_top_car.target_line.track_line_name == TrackLineName.机走
            and len(self.track_line_manager.remain_target_track_line_list) > 1
        ):
            cars = self.train.current_top_car.continuous_cars
            cache_line = self.track_line_manager.get_cache_line(target_line, cars, self.car_manager)
            operation_cache = Operation(line_name=cache_line.name, action=ActionType.PUT)
            operation_cache.copy_line_cars_before(cache_line)
            self.operation_manager.add(operation_cache)
            for put_car in cars:
                operation_cache.move_cars.append(put_car)
                Actions.move_car_from_train_to_line(put_car, self.train, cache_line, True)
            cache_line.is_can_arrived = False
            operation_cache.copy_train_cars(self.train)
            operation_cache.copy_line_cars_after(cache_line)
            Actions.increase_last_target_line_put_priority(self.train, self.task_manager)
            return TaskStatus.SKIPPED, False
        if not self.is_already_set_line_priority:
            self.track_line_manager.reset_cache_jz_line_priority_to_max()
            self.task_manager.pause_all_tasks()
            self.is_already_set_line_priority = True
        last_type = "Init"
        current_type = "Init"
        current_operation_list: list[Operation] = []
        operation = Operation(action=ActionType.PUT)
        current_operation_list.append(operation)
        cache_line: TrackLine | None = None
        is_break = False
        while self.train.current_top_car:
            if not any(Actions.is_can_cache_in_jzyx(car.target_line.track_line_name) for car in self.train.current_list) or all(
                not self._is_car_can_put(car, target_line) for car in self.train.current_list
            ):
                operation.copy_train_cars(self.train)
                if operation.line_name:
                    operation.copy_line_cars_after(self.track_line_manager.track_lines[operation.line_name])
                break
            car = self.train.current_top_car
            cars = car.continuous_cars
            if self._is_car_can_put(car, target_line):
                if not operation.line_cars_before:
                    operation.copy_line_cars_before(target_line)
                destination = target_line
                current_type = "Put"
            else:
                cache_line = self.track_line_manager.get_cache_line(target_line, cars, self.car_manager, last_used_cache_line=cache_line)
                destination = cache_line
                if not operation.line_cars_before:
                    operation.copy_line_cars_before(cache_line)
                current_type = "Cache"
            for put_car in cars:
                Actions.move_car_from_train_to_line(put_car, self.train, destination, True)
            if current_type == "Cache" and self.train.wanted_car and self.train.wanted_car.is_current_top_and_can_get_direct:
                is_break = True
            if last_type != "Init" and current_type != last_type:
                operation.copy_train_cars(self.train)
                operation.copy_line_cars_after(self.track_line_manager.track_lines[operation.line_name])
                operation = Operation(action=ActionType.PUT)
                current_operation_list.append(operation)
            operation.line_name = destination.name
            operation.move_cars.extend(cars)
            last_type = current_type
            if is_break:
                break
        if not operation.line_cars_after:
            operation.copy_line_cars_after(target_line)
        for item in [o for o in current_operation_list if o.move_cars]:
            self.operation_manager.add(item)
        if is_break:
            return TaskStatus.SKIPPED, False
        if len(target_line.current_list) == Constraint.max_train_count or not self.car_manager.jzyx_remain:
            self.task_manager.pause_all_tasks()
            self.task_manager.remove_get_tasks()
            self.track_line_manager.open_repair_lines(self.task_manager)
            target_line.is_can_arrived = False
            self.is_completed_once = True
            Constraint.is_put_jz_finished = True
            return TaskStatus.COMPLETED, False
        return TaskStatus.SKIPPED, False

    def _is_car_can_put(self, car: Car, target_line: TrackLine) -> bool:
        if not Actions.is_can_cache_in_jzyx(car.target_line.track_line_name):
            return False
        if self.is_completed_once and car.target_line.track_line_name != TrackLineName.机走:
            return False
        targets_in_line = [item for item in target_line.current_list if item.target_line is car.target_line]
        target_cars = [item for item in car.target_line.origin_target_list if item.is_need_move and item.current_line.is_can_arrived]
        remaining = [item for item in target_cars if item not in targets_in_line]
        target = remaining[-1] if remaining else None
        if target is None:
            return True
        return car is target

    Execute = execute
    _IsCarCanPut = _is_car_can_put


class Weigh(TaskItem):
    def __init__(self, train: Train, task_manager: TaskManager, car_manager: CarManager, track_line_manager: TrackLineManager, operation_manager: OperationManager) -> None:
        super().__init__("Weigh", priority=2**31 - 1, can_skip=True)
        self.train = train
        self.task_manager = task_manager
        self.car_manager = car_manager
        self.track_line_manager = track_line_manager
        self.operation_manager = operation_manager

    def execute(self) -> tuple[TaskStatus, bool]:
        if self.task_manager.get_task_status(self.id) == TaskStatus.PAUSED:
            return TaskStatus.PAUSED, False
        last_weigh_car = next((car for car in self.train.current_list if car.is_weigh and not car.is_weighed), None)
        if last_weigh_car is None:
            return TaskStatus.SKIPPED, False
        is_all_get = True
        for item in last_weigh_car.remain_origin_target_cars:
            if item.is_need_move and item.current_line.track_line_name not in {TrackLineName.train, TrackLineName.机走} and item.current_line.is_can_arrived:
                is_all_get = False
                break
        if not is_all_get:
            return TaskStatus.SKIPPED, False
        if not self.track_line_manager.track_lines[TrackLineName.机库线.value].is_cleared:
            return TaskStatus.SKIPPED, False
        cache_line: TrackLine | None = None
        while last_weigh_car is not None:
            last_weigh_car_index = self.train.current_list.index(last_weigh_car)
            need_cache_cars = self.train.current_list[:last_weigh_car_index]
            if need_cache_cars:
                if cache_line is None:
                    cache_line = self.track_line_manager.get_cache_line(
                        self.track_line_manager.track_lines[TrackLineName.机库线.value],
                        need_cache_cars,
                        self.car_manager,
                    )
                operation_cache = Operation(line_name=cache_line.name, action=ActionType.PUT)
                operation_cache.copy_line_cars_before(cache_line)
                for item in list(need_cache_cars):
                    # 与 V3 一致：称重前缓存到机走时需要还原目标列表，缓存到其它线则不还原目标列表。
                    Actions.move_car_from_train_to_line(item, self.train, cache_line, cache_line.track_line_name == TrackLineName.机走)
                    operation_cache.move_cars.append(item)
                operation_cache.copy_line_cars_after(cache_line)
                operation_cache.copy_train_cars(self.train)
                self.operation_manager.add(operation_cache)
            operation_weigh = Operation(line_name=TrackLineName.机库线.value, action=ActionType.WEIGH)
            operation_weigh.move_cars.append(last_weigh_car)
            self.operation_manager.add(operation_weigh)
            last_weigh_car.is_weighed = True
            last_weigh_car = next((car for car in self.train.current_list if car.is_weigh and not car.is_weighed), None)
        if not self.car_manager.remain_weigh_cars:
            return TaskStatus.COMPLETED, False
        return TaskStatus.RUNNING, False

    Execute = execute


class BackwardConstructionAlgorithm:
    current_put_car_task_priority = 10

    def __init__(self, track_lines: dict[str, TrackLine], cars: dict[str, Car], distance_matrix: dict[str, dict[str, int]]) -> None:
        BackwardConstructionAlgorithm.current_put_car_task_priority = 10
        Constraint.is_put_jz_finished = False
        Constraint.is_put_cun4_finished = False
        self._sort_track_line_cars(track_lines)
        self.task_manager = BCTaskManager()
        self.task_manager.on_task_completed.append(self.on_task_completed)
        self.car_manager = CarManager(cars)
        self.track_line_manager = TrackLineManager(track_lines, cars, distance_matrix)
        self.cars = cars
        self.train = Train(name=TrackLineName.train.value, is_can_arrived=False)
        self.track_line_manager.track_lines[TrackLineName.train.value] = self.train
        self.operation_manager = OperationManager(self.train)
        for line in track_lines.values():
            line.on_current_cleared.append(self.on_line_current_cleared)
            line.on_target_cleared.append(self.on_line_target_cleared)

    def run(self) -> list[Operation]:
        self.track_line_manager.init_track_line()
        self._init_task()
        round_idx = 1
        while any(car.is_need_move for car in self.cars.values()):
            if round_idx > 100:
                raise RuntimeError("超过100轮未完成")
            round_idx += 1
            task_list = self.task_manager.get_ready_tasks()
            _trace(
                "ready_tasks="
                + str([(task.id, task.priority, self.task_manager.get_task_status(task.id).name) for task in task_list]),
                round_idx,
            )
            is_contain_completed = False
            force_skip_other_task = False
            for task in task_list:
                status, force_skip_other_task = task.execute()
                self.task_manager.set_task_status(task.id, status)
                if force_skip_other_task:
                    break
                if status == TaskStatus.COMPLETED:
                    is_contain_completed = True
                    break
            if is_contain_completed or force_skip_other_task:
                continue
            target = self._get_best_target(self.track_line_manager.track_lines, self.train)
            if target is None:
                if not self.car_manager.remain_cars:
                    break
                cannot_arrived_lines = [line for line in self.track_line_manager.track_lines.values() if not line.is_can_arrived]
                if cannot_arrived_lines:
                    for item in cannot_arrived_lines:
                        item.is_can_arrived = True
                    continue
                raise RuntimeError("未取到车辆，程序异常终止")
            _trace(
                "selected_target="
                f"{target.no}@{target.current_line_name}:{target.current_depth}"
                f"->{target.target_line_name}:{target.target_line_position}",
                round_idx,
            )
            self._move_car(target, self.train, self.operation_manager)
        return self.operation_manager.operations

    def _sort_track_line_cars(self, track_lines: dict[str, TrackLine]) -> None:
        for line in track_lines.values():
            line.current_list.sort(key=lambda car: car.origin_line_position)
            line.target_list.sort(key=lambda car: car.target_line_position)
            line.origin_target_list.sort(key=lambda car: car.target_line_position)

    def on_line_target_cleared(self, line: TrackLine) -> None:
        if line.current_top_car is None:
            self._create_put_task(line)
        else:
            task = ClearLine(line.track_line_name, self.track_line_manager, self.task_manager, self.train, 1, [f"Clear_{TrackLineName.机走.value}"], True)
            self.task_manager.add_task(task)
            self._create_put_task(line, [task.id])

    def on_line_current_cleared(self, line: TrackLine) -> None:
        if line.track_line_name == TrackLineName.机走 or not line.origin_target_list:
            return
        if line.is_cache and line.track_line_name != TrackLineName.老预修:
            return
        self._create_put_task(line)

    def _create_put_task(self, line: TrackLine, dependencies: Iterable[str] | None = None) -> None:
        if line.track_line_name == TrackLineName.机走:
            task: TaskItem = PutCarToJZLine(
                self.track_line_manager,
                self.train,
                self.operation_manager,
                self.task_manager,
                self.car_manager,
                priority=BackwardConstructionAlgorithm.current_put_car_task_priority,
            )
        else:
            task = PutCar(
                self.task_manager,
                line.track_line_name,
                self.track_line_manager,
                self.train,
                self.car_manager,
                self.operation_manager,
                priority=BackwardConstructionAlgorithm.current_put_car_task_priority,
                dependencies=dependencies,
            )
        BackwardConstructionAlgorithm.current_put_car_task_priority += 1
        self.task_manager.add_task(task)

    def on_task_completed(self, task: TaskItem) -> None:
        if task.id == f"Put_{TrackLineName.存4线.value}":
            Constraint.is_put_cun4_finished = True
            self.track_line_manager.track_lines[TrackLineName.机走.value].is_can_arrived = True
            self._move_all_car_in_jzx_to_train()
            self.task_manager.resume_all_tasks()
            self.task_manager.remove_get_tasks()

    def _move_all_car_in_jzx_to_train(self) -> None:
        jzx_line = self.track_line_manager.get_track_line(TrackLineName.机走)
        if jzx_line.current_top_car is None:
            return
        jzx_line.is_can_arrived = True
        if Constraint.is_over_train_count_limit(self.train, list(jzx_line.current_list)):
            cache_line = self.track_line_manager.get_cache_line(jzx_line, list(self.train.current_list), self.car_manager)
            operation_cache = Operation(action=ActionType.PUT, line_name=cache_line.name)
            operation_cache.copy_train_cars(self.train)
            operation_cache.copy_line_cars_before(cache_line)
            while Constraint.is_over_train_count_limit(self.train, list(jzx_line.current_list)) and self.train.current_top_car is not None:
                continuous_cars = self.train.current_top_car.continuous_cars
                for item in continuous_cars:
                    Actions.move_car_from_train_to_line(item, self.train, cache_line, True)
                    operation_cache.move_cars.append(item)
            operation_cache.copy_line_cars_after(cache_line)
            self.operation_manager.add(operation_cache)
        operation = Operation(line_name=jzx_line.name, action=ActionType.GET)
        operation.copy_line_cars_before(jzx_line)
        self.operation_manager.add(operation)
        while jzx_line.current_top_car is not None:
            car = jzx_line.current_top_car
            Actions.move_car_from_line_to_train(car, self.train, True)
            operation.move_cars.append(car)
        operation.copy_train_cars(self.train)
        operation.copy_line_cars_after(jzx_line)
        target_is_all_contain = list(self.train.get_target_line_is_all_contained().items())[::-1]
        for target_line, is_all_contain in target_is_all_contain:
            if is_all_contain and target_line.is_cleared:
                put_task = PutCar(self.task_manager, target_line.track_line_name, self.track_line_manager, self.train, self.car_manager, self.operation_manager, BackwardConstructionAlgorithm.current_put_car_task_priority)
                BackwardConstructionAlgorithm.current_put_car_task_priority += 1
                self.task_manager.add_task(put_task)

    def _init_task(self) -> None:
        task_clear_jzx = ClearLine(TrackLineName.机走, self.track_line_manager, self.task_manager, self.train, priority=1, can_skip=True)
        self.task_manager.add_task(task_clear_jzx)
        for line_name in [
            TrackLineName.喷漆,
            TrackLineName.洗罐,
            TrackLineName.抛丸线,
            TrackLineName.机库线,
            TrackLineName.调梁,
            TrackLineName.老预修,
            TrackLineName.存1线,
            TrackLineName.存2线,
            TrackLineName.存3线,
        ]:
            self.task_manager.add_task(GetCar(line_name, self.track_line_manager, 1, [task_clear_jzx.id], True))
        if self.car_manager.remain_weigh_cars:
            self.task_manager.add_task(Weigh(self.train, self.task_manager, self.car_manager, self.track_line_manager, self.operation_manager))

    def _get_best_target(self, track_lines: dict[str, TrackLine], train: Train) -> Car | None:
        if train.wanted_car and train.wanted_car.is_current_top_and_can_get_direct:
            _trace(
                "best_target shortcut train.wanted_car="
                f"{train.wanted_car.no}@{train.wanted_car.current_line_name}",
            )
            return train.wanted_car
        candidates = [
            line.target_top_car
            for line in track_lines.values()
            if line.target_top_car is not None and not line.target_top_car.is_in_train and line.target_top_car.current_line.is_can_arrived
        ]
        if train.current_list_count == 0:
            non_closed_door_candidates = [
                car for car in candidates if not (car.is_closed_door and car.target_line.track_line_name != TrackLineName.存4线)
            ]
            if non_closed_door_candidates:
                candidates = non_closed_door_candidates
        _trace(
            "best_target candidates="
            + str([
                (
                    car.no,
                    car.current_line_name,
                    car.current_depth,
                    car.target_line_name,
                    car.target_line.priority,
                )
                for car in candidates
            ]),
        )
        task = self.task_manager.get_task(f"Put_{TrackLineName.机走.value}")
        if task is not None and self.task_manager.get_task_status(task.id) != TaskStatus.COMPLETED:
            candidates = [car for car in candidates if car.current_line.track_line_name != TrackLineName.机走]
        best_target = sorted(
            [car for car in candidates if car.is_current_top],
            key=lambda car: (-int(self._is_train_wanted_car(car)), -car.target_line.priority),
        )
        if best_target:
            return best_target[0]
        best_target = sorted(
            candidates,
            key=lambda car: (-int(self._is_train_wanted_car(car)), car.current_depth, -len(car.target_line.target_list)),
        )
        return best_target[0] if best_target else None

    def _is_train_wanted_car(self, car: Car) -> bool:
        return self.train.wanted_car is car if self.train.wanted_car else False

    def _move_car(self, car: Car, train: Train, operation_manager: OperationManager) -> None:
        current_line = car.current_line
        continuous_cars = car.continuous_cars
        block_cars = car.current_line.current_list[: car.current_depth]
        _trace(
            "_move_car "
            f"target={car.no} line={car.current_line_name} depth={car.current_depth} "
            f"continuous={[item.no for item in continuous_cars]} "
            f"block={[item.no for item in block_cars]}",
        )
        if Constraint.is_over_train_count_limit(self.train, continuous_cars) or Constraint.is_over_train_count_limit(self.train, block_cars):
            task = self.task_manager.get_task(f"Put_{TrackLineName.机走.value}")
            if task is None:
                task = PutCarToJZLine(self.track_line_manager, self.train, operation_manager, self.task_manager, self.car_manager, priority=BackwardConstructionAlgorithm.current_put_car_task_priority)
                BackwardConstructionAlgorithm.current_put_car_task_priority += 1
                self.task_manager.add_task(task)
                return
            if continuous_cars:
                self._cache_cars_when_over_count_limit_in_get(train, car, len(continuous_cars))
                return
            raise RuntimeError("机车容量超限，且当前分支未覆盖")
        if not car.is_current_top:
            is_need_skip = self._move_block_cars_to_cache(car, train, operation_manager)
            if is_need_skip:
                return
        operation = Operation(line_name=car.current_line_name, action=ActionType.GET)
        operation.copy_line_cars_before(current_line)
        Actions.move_car_from_line_to_train_continuously(car, train, operation)
        operation.copy_train_cars(train)
        operation.copy_line_cars_after(current_line)
        operation_manager.add(operation)
        Actions.increase_last_target_line_put_priority(self.train, self.task_manager)

    def _cache_cars_when_over_count_limit_in_get(self, train: Train, target_car: Car, length: int) -> None:
        current_line = self.train.current_top_car.target_line
        operation = Operation(action=ActionType.PUT, line_name=target_car.current_line.name)
        operation.copy_line_cars_before(target_car.current_line)
        if target_car.is_current_top and self.train.current_top_car and self.train.current_top_car.next_car is target_car:
            while self.train.current_top_car and self.train.current_top_car.target_line is target_car.target_line:
                tmp = self.train.current_top_car
                Actions.move_car_from_train_to_line(tmp, train, target_car.current_line, True)
                operation.move_cars.append(tmp)
            if operation.move_cars:
                operation.copy_train_cars(self.train)
                operation.copy_line_cars_after(target_car.current_line)
                self.operation_manager.add(operation)
        cache_line = self.track_line_manager.get_cache_line(current_line, self.train.current_top_car.continuous_cars, self.car_manager)
        operation = Operation(action=ActionType.PUT, line_name=cache_line.name)
        operation.copy_line_cars_before(cache_line)
        while self.train.current_top_car and self.train.current_top_car.target_line is not target_car.target_line:
            tmp = self.train.current_top_car
            Actions.move_car_from_train_to_line(tmp, train, cache_line, True)
            operation.move_cars.append(tmp)
        if operation.move_cars:
            operation.copy_train_cars(self.train)
            operation.copy_line_cars_after(cache_line)
            self.operation_manager.add(operation)
        operation = Operation(action=ActionType.GET, line_name=target_car.current_line.name)
        operation.copy_line_cars_before(target_car.current_line)
        Actions.move_car_from_line_to_train_continuously(target_car.current_line.current_top_car, train, operation)
        operation.copy_train_cars(train)
        operation.copy_line_cars_after(target_car.current_line)
        self.operation_manager.add(operation)
        Actions.increase_last_target_line_put_priority(self.train, self.task_manager)

    def _move_block_cars_to_cache(self, car: Car, train: Train, operation_manager: OperationManager) -> bool:
        operation_cache: Operation | None = None
        cache_line: TrackLine | None = None
        current_line = car.current_line
        is_need_skip = False
        while not car.is_current_top and current_line.current_top_car is not None:
            current_top = current_line.current_top_car
            cars = current_top.continuous_cars
            if operation_cache is None:
                operation_cache = Operation(action=ActionType.GET, line_name=current_top.current_line_name)
                operation_cache.copy_line_cars_before(current_top.current_line)
                reserve_cars = list(cars)
                reserve_cars.reverse()
                cache_line = self.track_line_manager.get_cache_line(current_line, reserve_cars, self.car_manager, target_car=car)
            for get_car in cars:
                Actions.move_car_from_line_to_train(get_car, train, False)
                operation_cache.move_cars.append(get_car)
            train_top = self.train.current_top_car
            if train_top is not None and train_top.is_target_line_wanted_continuous and train_top.target_line.is_can_arrived and train_top.target_line.is_cleared:
                Actions.increase_last_target_line_put_priority(self.train, self.task_manager)
                is_need_skip = True
                break
        if operation_cache is not None and cache_line is not None:
            operation_manager.add(operation_cache)
            operation_cache.copy_train_cars(train)
            operation_cache.copy_line_cars_after(self.track_line_manager.track_lines[operation_cache.line_name])
            operation_release = Operation(action=ActionType.PUT, line_name=cache_line.name)
            operation_release.copy_line_cars_before(cache_line)
            for item in reversed(operation_cache.move_cars):
                Actions.move_car_from_train_to_line(item, self.train, cache_line, False)
                operation_release.move_cars.append(item)
            operation_manager.add(operation_release)
            operation_release.copy_train_cars(self.train)
            operation_release.copy_line_cars_after(cache_line)
            self.task_manager.create_clear_line_task(cache_line, self.track_line_manager, self.train)
        return is_need_skip

    Run = run
    OnLineTargetCleared = on_line_target_cleared
    OnLineCurrentCleared = on_line_current_cleared
    OnTaskCompleted = on_task_completed
    _SortTrackLineCars = _sort_track_line_cars
    _CreatePutTask = _create_put_task
    _MoveAllCarInJZXToTrain = _move_all_car_in_jzx_to_train
    _InitTask = _init_task
    _GetBestTarget = _get_best_target
    _IsTrainWantedCar = _is_train_wanted_car
    _MoveCar = _move_car
    _CacheCarsWhenOverCountLimitInGet = _cache_cars_when_over_count_limit_in_get
    _MoveBlockCarsToCache = _move_block_cars_to_cache


class IAlgorithm:
    def run(self) -> list[Operation]:
        raise NotImplementedError

    Run = run


class ICacheStrategy:
    def select_best_cache_line(
        self,
        current_source_line: TrackLine,
        blocking_cars_batch: list[Car],
        all_lines: Iterable[TrackLine],
        last_used_cache_line: TrackLine | None,
    ) -> TrackLine | None:
        raise NotImplementedError

    SelectBestCacheLine = select_best_cache_line


class CacheStrategyV1(ICacheStrategy):
    cost_switch_line = 600.0
    cost_congestion_per_meter = 10.0
    cost_use_empty_line = 1500.0
    cost_future_dig_base = 2000.0
    cost_use_jzx = 5000.0
    cost_functional_line = 3000.0
    functional_lines = {"喷漆库", "调梁库"}

    def __init__(self, distance_calculator: Callable[[str, str], int]) -> None:
        self.distance_calculator = distance_calculator

    def select_best_cache_line(
        self,
        current_source_line: TrackLine,
        blocking_cars_batch: list[Car],
        all_lines: Iterable[TrackLine],
        last_used_cache_line: TrackLine | None,
    ) -> TrackLine | None:
        if not blocking_cars_batch:
            return None
        total_length = sum(car.length for car in blocking_cars_batch)
        batch_priorities = [self.get_car_priority(car) for car in blocking_cars_batch]
        candidates = [
            line
            for line in all_lines
            if line.is_cache and line.is_can_arrived and line.rem_capacity >= total_length and line.name != current_source_line.name
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda line: self.calculate_total_cost(line, current_source_line, last_used_cache_line, batch_priorities),
        )

    def calculate_future_risk(self, candidate: TrackLine, batch_priorities: list[int]) -> float:
        if not candidate.current_list:
            return 0.0
        batch_min_priority = min(batch_priorities)
        max_priority_in_line = max(self.get_car_priority(car) for car in candidate.current_list)
        risk_score = 0.0
        if max_priority_in_line > batch_min_priority:
            diff = max_priority_in_line - batch_min_priority
            risk_score += self.cost_future_dig_base + diff * 100.0
            if max_priority_in_line > 90:
                risk_score += 50000.0
        else:
            risk_score -= 500.0
        if candidate.current_top_car is not None:
            top_priority = self.get_car_priority(candidate.current_top_car)
            if top_priority > batch_min_priority:
                risk_score += 200.0
        return risk_score

    def calculate_total_cost(
        self,
        candidate: TrackLine,
        source: TrackLine,
        last_used: TrackLine | None,
        batch_priorities: list[int],
    ) -> float:
        cost = float(self.distance_calculator(source.name, candidate.name))
        if last_used is not None and candidate.name == last_used.name:
            cost -= 100.0
        else:
            cost += self.cost_switch_line

        is_functional = candidate.name in self.functional_lines or candidate.track_line_name.value in self.functional_lines
        if is_functional:
            cost += self.cost_functional_line

        cost += self.calculate_future_risk(candidate, batch_priorities)

        if not candidate.current_list:
            cost += self.cost_use_empty_line
        if candidate.rem_capacity < 50:
            cost += (50.0 - float(candidate.rem_capacity)) * self.cost_congestion_per_meter
        if candidate.track_line_name == TrackLineName.机走:
            cost += self.cost_use_jzx
        return cost

    def get_car_priority(self, car: Car) -> int:
        if car.target_line is None:
            return 0
        return car.target_line.priority

    SelectBestCacheLine = select_best_cache_line
    CalculateFutureRisk = calculate_future_risk
    CalculateTotalCost = calculate_total_cost
    GetCarPriority = get_car_priority


class CacheStrategyV2(ICacheStrategy):
    cost_switch_line = 1000.0
    cost_burying_light = 50.0
    cost_burying_heavy = 200.0
    cost_use_empty_line_base = 1200.0
    reward_target_per_car = 500.0
    reward_sequential = 200.0
    threshold_congestion = 30.0
    cost_congestion_per_meter = 20.0
    cost_use_jzx = 5000.0
    cost_capacity_waste_coeff = 0.05
    cost_functional_line = 3000.0
    functional_lines = {"喷漆库", "调梁库"}

    def __init__(self, distance_calculator: Callable[[str, str], int]) -> None:
        self.distance_calculator = distance_calculator

    def select_best_cache_line(
        self,
        current_source_line: TrackLine,
        blocking_cars_batch: list[Car],
        all_lines: Iterable[TrackLine],
        last_used_cache_line: TrackLine | None,
    ) -> TrackLine | None:
        if not blocking_cars_batch:
            return None
        total_length = sum(car.length for car in blocking_cars_batch)
        real_source_line_name = blocking_cars_batch[0].current_line_name
        batch_priorities = [self.get_car_priority(car) for car in blocking_cars_batch]
        candidates = [
            line
            for line in all_lines
            if line.is_cache
            and line.is_can_arrived
            and line.rem_capacity >= total_length
            and line.name != current_source_line.name
            and line.name != real_source_line_name
        ]
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda line: self.calculate_total_cost(
                line, real_source_line_name, last_used_cache_line, batch_priorities, blocking_cars_batch
            ),
        )

    def calculate_flexible_risk_and_reward(
        self,
        candidate: TrackLine,
        batch_priorities: list[int],
        blocking_cars_batch: list[Car],
    ) -> float:
        score = 0.0
        for car in blocking_cars_batch:
            if car.target_line_name == candidate.name or car.target_line_name == candidate.track_line_name.value:
                score -= self.reward_target_per_car
        if not candidate.current_list:
            return score
        batch_min_priority = min(batch_priorities)
        max_priority_in_line = max(self.get_car_priority(car) for car in candidate.current_list)
        if max_priority_in_line > batch_min_priority:
            diff = max_priority_in_line - batch_min_priority
            if diff <= 5:
                score += diff * self.cost_burying_light
            else:
                score += 5 * self.cost_burying_light + (diff - 5) * self.cost_burying_heavy
            if max_priority_in_line > 90:
                score += 50000.0
        else:
            score -= self.reward_sequential
        return score

    def calculate_total_cost(
        self,
        candidate: TrackLine,
        real_source_name: str,
        last_used: TrackLine | None,
        batch_priorities: list[int],
        blocking_cars_batch: list[Car],
    ) -> float:
        cost = float(self.distance_calculator(real_source_name, candidate.name))
        is_digging_from_last_used = last_used is not None and last_used.name == real_source_name
        if not is_digging_from_last_used and last_used is not None and candidate.name == last_used.name:
            cost -= 100.0
        else:
            cost += self.cost_switch_line

        is_functional = candidate.name in self.functional_lines or candidate.track_line_name.value in self.functional_lines
        if is_functional:
            is_target_for_batch = any(
                car.target_line_name == candidate.name or car.target_line_name == candidate.track_line_name.value
                for car in blocking_cars_batch
            )
            if not is_target_for_batch:
                cost += self.cost_functional_line

        cost += self.calculate_flexible_risk_and_reward(candidate, batch_priorities, blocking_cars_batch)

        if not candidate.current_list:
            cost += self.cost_use_empty_line_base
            cost += float(candidate.ori_capacity) * self.cost_capacity_waste_coeff
        if float(candidate.rem_capacity) < self.threshold_congestion:
            cost += (self.threshold_congestion - float(candidate.rem_capacity)) * self.cost_congestion_per_meter
        if candidate.track_line_name == TrackLineName.机走:
            cost += self.cost_use_jzx
        return cost

    def get_car_priority(self, car: Car) -> int:
        if car.target_line is None:
            return 0
        return car.target_line.priority

    SelectBestCacheLine = select_best_cache_line
    CalculateFlexibleRiskAndReward = calculate_flexible_risk_and_reward
    CalculateTotalCost = calculate_total_cost
    GetCarPriority = get_car_priority
