from collections.abc import Callable
from pathlib import Path


class Base50Helper:
    def __init__(self, template_path: Path):
        self.template_path = template_path

    def _build_rated_entries(
        self,
        plugin,
        entries: list[dict],
        include_entry: Callable[[dict], bool],
    ) -> list[dict]:
        rated_entries = [
            rated_entry
            for entry in entries
            if include_entry(entry)
            for rated_entry in [plugin._build_rated_entry(entry)]
            if rated_entry is not None
        ]
        rated_entries.sort(
            key=lambda entry: (entry["rating"], entry["achievement"]), reverse=True
        )
        return rated_entries

    def _select_entries(
        self, plugin, entries: list[dict], include_entry: Callable[[dict], bool]
    ) -> tuple[int | None, list[dict], list[dict]]:
        rated_entries = self._build_rated_entries(plugin, entries, include_entry)
        current_version_floor = plugin._get_current_version_floor(entries)
        new_entries = [
            entry
            for entry in rated_entries
            if plugin._is_current_version_entry(entry, current_version_floor)
        ]
        old_entries = [
            entry
            for entry in rated_entries
            if not plugin._is_current_version_entry(entry, current_version_floor)
        ]
        return current_version_floor, new_entries[:15], old_entries[:35]

    def _render_summary(
        self,
        plugin,
        profile: dict | None,
        entries: list[dict] | None,
        select_entries: Callable[
            [object, list[dict]], tuple[int | None, list[dict], list[dict]]
        ],
        chart_count_lines: Callable[[list[dict]], list[str]],
        total_label: str,
        new_label: str,
        old_label: str,
        no_new_message: str,
        no_old_message: str,
        no_rated_message: str,
    ) -> str:
        if profile is None:
            return "Failed to retrieve friend profile information."
        if entries is None:
            return "Failed to retrieve friend chart information."

        current_version_floor, new_top, old_top = select_entries(plugin, entries)
        total_rating = sum(entry["rating"] for entry in new_top + old_top)
        lines = [
            f"{profile['name']} (Rating: {profile['rating']})",
            *chart_count_lines(entries),
            f"Current-version floor: {current_version_floor if current_version_floor is not None else 'Unknown'}",
            f"{total_label} total rating: {total_rating} (New {len(new_top)}/15 + Old {len(old_top)}/35)",
            f"\n=== {new_label} ===",
        ]
        self._append_entries(lines, new_top, no_new_message)
        lines.append(f"\n\n=== {old_label} ===\n")
        self._append_entries(lines, old_top, no_old_message)

        if not new_top and not old_top:
            lines.append(no_rated_message)
        return "\n".join(lines)

    @staticmethod
    def _append_entries(
        lines: list[str], entries: list[dict], empty_message: str
    ) -> None:
        if not entries:
            lines.append(empty_message)
            return

        for index, entry in enumerate(entries, start=1):
            lines.append(
                f"{index:02d}. [{entry['difficulty']}] {entry['title']} | {entry['type']} {entry['level']} | {entry['achievement_text']} | c{entry['chart_constant']:.1f} x {entry['rank_factor']:.1f} => {entry['rating']}"
            )

    async def _generate_image(
        self,
        plugin,
        profile: dict | None,
        entries: list[dict],
        select_entries: Callable[
            [object, list[dict]], tuple[int | None, list[dict], list[dict]]
        ],
        error_message: str,
        extra_render_data: dict | None = None,
    ) -> str:
        if not profile:
            raise ValueError(error_message)

        current_floor, new_top, old_top = select_entries(plugin, entries)
        render_data = {
            "player_name": profile["name"],
            "player_rating": profile["rating"],
            "best35": old_top,
            "best15": new_top,
            "total_b50": sum(entry["rating"] for entry in new_top + old_top),
            "version_floor": current_floor,
            "background_image": plugin._get_template_background(),
        }
        if extra_render_data:
            render_data.update(extra_render_data)

        template_path = self.template_path / "b50_template.html"
        with open(template_path, encoding="utf-8") as file:
            template_str = file.read()

        return await plugin.html_render(
            template_str, render_data, options={"full_page": True, "type": "png"}
        )
