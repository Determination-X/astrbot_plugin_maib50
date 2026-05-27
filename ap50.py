from pathlib import Path


class AP50Helper:
    def __init__(self, template_path: Path):
        self.template_path = template_path

    def _is_all_perfect(self, entry: dict) -> bool:
        icons = set(entry.get("icons", []))
        return "ap" in icons or "app" in icons

    def _build_ap_rated_entries(self, plugin, entries: list[dict]) -> list[dict]:
        rated_entries = []
        for entry in entries:
            if not self._is_all_perfect(entry):
                continue
            rated_entry = plugin._build_rated_entry(entry)
            if rated_entry is not None:
                rated_entries.append(rated_entry)

        rated_entries.sort(
            key=lambda entry: (entry["rating"], entry["achievement"]), reverse=True
        )
        return rated_entries

    def select_ap50(
        self, plugin, entries: list[dict]
    ) -> tuple[int | None, list[dict], list[dict]]:
        rated_entries = self._build_ap_rated_entries(plugin, entries)
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

    def render_summary(self, plugin, profile: dict | None, entries: list[dict]) -> str:
        if profile is None:
            return "Failed to retrieve friend profile information."

        current_version_floor, new_top, old_top = self.select_ap50(plugin, entries)
        total_rating = sum(entry["rating"] for entry in new_top + old_top)
        ap_entries = [entry for entry in entries if self._is_all_perfect(entry)]

        lines = [
            f"{profile['name']} (Rating: {profile['rating']})",
            f"All Perfect charts found: {len(ap_entries)} / {len(entries)}",
            f"Current-version floor: {current_version_floor if current_version_floor is not None else 'Unknown'}",
            f"AP50 total rating: {total_rating} (New {len(new_top)}/15 + Old {len(old_top)}/35)",
            "\n=== AP New15 ===",
        ]
        if new_top:
            for index, entry in enumerate(new_top, start=1):
                lines.append(
                    f"{index:02d}. [{entry['difficulty']}] {entry['title']} | {entry['type']} {entry['level']} | {entry['achievement_text']} | c{entry['chart_constant']:.1f} x {entry['rank_factor']:.1f} => {entry['rating']}"
                )
        else:
            lines.append("No current-version AP charts found in AP New15 selection.")

        lines.append("\n\n=== AP Old35 ===\n")
        if old_top:
            for index, entry in enumerate(old_top, start=1):
                lines.append(
                    f"{index:02d}. [{entry['difficulty']}] {entry['title']} | {entry['type']} {entry['level']} | {entry['achievement_text']} | c{entry['chart_constant']:.1f} x {entry['rank_factor']:.1f} => {entry['rating']}"
                )
        else:
            lines.append("No old-version AP charts found in AP Old35 selection.")

        if not new_top and not old_top:
            lines.append("No rated AP charts found for this friend.")
        return "\n".join(lines)

    async def generate_image(
        self, plugin, profile: dict | None, entries: list[dict], uid: str
    ) -> str:
        if not profile:
            raise ValueError("Profile data is required to generate AP50 image")

        current_floor, new_top, old_top = self.select_ap50(plugin, entries)
        render_data = {
            "page_title": "maimai CiRCLE AP50",
            "player_name": profile["name"],
            "player_rating": profile["rating"],
            "best35": old_top,
            "best15": new_top,
            "total_b50": sum(entry["rating"] for entry in new_top + old_top),
            "version_floor": current_floor,
            "background_image": plugin._get_template_background(),
            "old_section_label": "AP Old 35",
            "new_section_label": "AP New 15",
        }

        template_path = self.template_path / "b50_template.html"
        with open(template_path, encoding="utf-8") as f:
            template_str = f.read()

        options = {
            "full_page": True,
            "type": "png",
        }
        return await plugin.html_render(template_str, render_data, options=options)
