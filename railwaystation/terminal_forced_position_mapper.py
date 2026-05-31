from __future__ import annotations

from .core import Car


class TerminalForcedPositionMapper:
    @staticmethod
    def is_active_force_text(text: str | None) -> bool:
        if not text or not text.strip():
            return False
        text = text.strip()
        if text in {"0", "否", "无"} or text.lower() == "false":
            return False
        return any(ch.isdigit() for ch in text)

    @staticmethod
    def apply_to_car(car: Car, selected_raw_target_name: str) -> None:
        car.allowed_target_line_positions.clear()
        if not TerminalForcedPositionMapper.is_active_force_text(car.force_target_position_text):
            car.is_force_target_position = False
            car.fixed_target_line_position = -1
            return
        positions = TerminalForcedPositionMapper.parse_allowed_positions(
            car.force_target_position_text,
            selected_raw_target_name,
        )
        car.allowed_target_line_positions = positions
        car.is_force_target_position = bool(positions)
        car.fixed_target_line_position = positions[0] if len(positions) == 1 else -1

    @staticmethod
    def can_map_force_text(force_text: str, selected_raw_target_name: str) -> bool:
        try:
            return len(TerminalForcedPositionMapper.parse_allowed_positions(force_text, selected_raw_target_name)) > 0
        except Exception:
            return False

    @staticmethod
    def parse_allowed_positions(force_text: str, selected_raw_target_name: str) -> list[int]:
        from .terminal import Terminal

        result: list[int] = []
        if not TerminalForcedPositionMapper.is_active_force_text(force_text):
            return result
        segment = Terminal.resolve_target_segment(selected_raw_target_name)
        tokens = TerminalForcedPositionMapper.split_force_position_tokens(force_text, segment[1], segment[2])
        for token in tokens:
            absolute_position = TerminalForcedPositionMapper.try_parse_absolute_position_token(token)
            if absolute_position is None:
                continue
            if segment[1] <= absolute_position <= segment[2]:
                result.append(absolute_position)
        return sorted(set(result))

    @staticmethod
    def has_position_constraint(car: Car) -> bool:
        return car.is_force_target_position and (bool(car.allowed_target_line_positions) or car.fixed_target_line_position > 0)

    @staticmethod
    def get_allowed_positions_in_range(car: Car, min_position: int, max_position: int) -> list[int]:
        positions: list[int] = []
        if car.allowed_target_line_positions:
            positions.extend(car.allowed_target_line_positions)
        elif car.is_force_target_position and car.fixed_target_line_position > 0:
            positions.append(car.fixed_target_line_position)
        return sorted({pos for pos in positions if min_position <= pos <= max_position})

    @staticmethod
    def is_position_allowed(car: Car, position: int, min_position: int, max_position: int) -> bool:
        if not TerminalForcedPositionMapper.has_position_constraint(car):
            return True
        return position in TerminalForcedPositionMapper.get_allowed_positions_in_range(car, min_position, max_position)

    @staticmethod
    def split_force_position_tokens(force_text: str, min_position: int, max_position: int) -> list[str]:
        raw_tokens = [
            token.strip()
            for token in force_text.replace("，", ",").replace("；", ",").replace(";", ",").replace("/", ",").replace("、", ",").split(",")
            if token.strip()
        ]
        result: list[str] = []
        for raw_token in raw_tokens:
            digits = "".join(ch for ch in raw_token if ch.isdigit())
            if not digits:
                continue
            try:
                direct_value = int(digits)
            except ValueError:
                direct_value = -1
            if min_position <= direct_value <= max_position:
                result.append(digits)
                continue
            compact_tokens = TerminalForcedPositionMapper.split_compact_digits_by_range(digits, min_position, max_position)
            if compact_tokens:
                result.extend(compact_tokens)
                continue
            result.append(digits)
        return result

    @staticmethod
    def split_compact_digits_by_range(digits: str, min_position: int, max_position: int) -> list[str]:
        best: list[str] = []
        current: list[str] = []

        def dfs(index: int) -> None:
            nonlocal best
            if index == len(digits):
                if len(current) > len(best):
                    best = list(current)
                return
            for length in (1, 2):
                if index + length > len(digits):
                    continue
                part = digits[index : index + length]
                try:
                    value = int(part)
                except ValueError:
                    continue
                if value < min_position or value > max_position:
                    continue
                current.append(part)
                dfs(index + length)
                current.pop()

        dfs(0)
        if len(best) <= 1:
            return []
        return best

    @staticmethod
    def try_parse_absolute_position_token(token: str) -> int | None:
        digits = "".join(ch for ch in token if ch.isdigit())
        if not digits:
            return None
        try:
            return int(digits)
        except ValueError:
            return None
