from pathlib import Path


class B50Helper:
    def __init__(self, template_path: Path):
        self.template_path = template_path

    def _build_b50_rated_entries(self, plugin, entries: list[dict]) -> list[dict]:
        rated_entries = [
            rated_entry
            for entry in entries
            for rated_entry in [plugin._build_rated_entry(entry)]
            if rated_entry is not None
        ]
        rated_entries.sort(
            key=lambda entry: (entry["rating"], entry["achievement"]), reverse=True
        )
        return rated_entries

    def select_b50(
        self, plugin, entries: list[dict]
    ) -> tuple[int | None, list[dict], list[dict]]:
        rated_entries = self._build_b50_rated_entries(plugin, entries)
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

    def render_summary(self, plugin, profile: dict | None, entries: list[dict] | None) -> str:
        if profile is None:
            return "Failed to retrieve friend profile information."
        if entries is None:
            return "Failed to retrieve friend chart information."

        current_version_floor, new_top, old_top = self.select_b50(plugin, entries)
        total_rating = sum(entry["rating"] for entry in new_top + old_top)
        played_entries = [entry for entry in entries if not entry["unplayed"]]
        unplayed_count = len(entries) - len(played_entries)

        lines = [
            f"{profile['name']} (Rating: {profile['rating']})",
            f"Played charts: {len(played_entries)} / {len(entries)}",
            f"Unplayed charts excluded: {unplayed_count}",
            f"Current-version floor: {current_version_floor if current_version_floor is not None else 'Unknown'}",
            f"B50 total rating: {total_rating} (New {len(new_top)}/15 + Old {len(old_top)}/35)",
            "\n=== New15 ===",
        ]
        if new_top:
            for index, entry in enumerate(new_top, start=1):
                lines.append(
                    f"{index:02d}. [{entry['difficulty']}] {entry['title']} | {entry['type']} {entry['level']} | {entry['achievement_text']} | c{entry['chart_constant']:.1f} x {entry['rank_factor']:.1f} => {entry['rating']}"
                )
        else:
            lines.append("No current-version charts found in New15 selection.")

        lines.append("\n\n=== Old35 ===\n")
        if old_top:
            for index, entry in enumerate(old_top, start=1):
                lines.append(
                    f"{index:02d}. [{entry['difficulty']}] {entry['title']} | {entry['type']} {entry['level']} | {entry['achievement_text']} | c{entry['chart_constant']:.1f} x {entry['rank_factor']:.1f} => {entry['rating']}"
                )
        else:
            lines.append("No old-version charts found in Old35 selection.")

        if not new_top and not old_top:
            lines.append(
                "No rated charts found for this friend (missing constants or low achievements)."
            )
        return "\n".join(lines)

    async def generate_image(
        self, plugin, profile: dict | None, entries: list[dict], uid: str
    ) -> str:
        if not profile:
            raise ValueError("Profile data is required to generate B50 image")

        current_floor, new_top, old_top = self.select_b50(plugin, entries)
        render_data = {
            "player_name": profile["name"],
            "player_rating": profile["rating"],
            "best35": old_top,
            "best15": new_top,
            "total_b50": sum(entry["rating"] for entry in new_top + old_top),
            "version_floor": current_floor,
            "background_image": plugin._get_template_background(),
        }

        template_path = self.template_path / "b50_template.html"
        with open(template_path, encoding="utf-8") as f:
            template_str = f.read()

        options = {
            "full_page": True,
            "type": "png",
        }
        return await plugin.html_render(template_str, render_data, options=options)
