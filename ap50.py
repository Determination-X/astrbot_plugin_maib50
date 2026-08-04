from .base50 import Base50Helper


class AP50Helper(Base50Helper):
    def _is_all_perfect(self, entry: dict) -> bool:
        icons = set(entry.get("icons", []))
        return "ap" in icons or "app" in icons

    def _build_ap_rated_entries(self, plugin, entries: list[dict]) -> list[dict]:
        return self._build_rated_entries(plugin, entries, self._is_all_perfect)

    def select_ap50(
        self, plugin, entries: list[dict]
    ) -> tuple[int | None, list[dict], list[dict]]:
        return self._select_entries(plugin, entries, self._is_all_perfect)

    def render_summary(
        self, plugin, profile: dict | None, entries: list[dict] | None
    ) -> str:
        return self._render_summary(
            plugin,
            profile,
            entries,
            self.select_ap50,
            lambda entries: [
                f"All Perfect charts found: {sum(self._is_all_perfect(entry) for entry in entries)} / {len(entries)}"
            ],
            "AP50",
            "AP New15",
            "AP Old35",
            "No current-version AP charts found in AP New15 selection.",
            "No old-version AP charts found in AP Old35 selection.",
            "No rated AP charts found for this friend.",
        )

    async def generate_image(
        self, plugin, profile: dict | None, entries: list[dict], uid: str
    ) -> str:
        return await self._generate_image(
            plugin,
            profile,
            entries,
            self.select_ap50,
            "Profile data is required to generate AP50 image",
            {
                "page_title": "maimai CiRCLE AP50",
                "old_section_label": "AP Old 35",
                "new_section_label": "AP New 15",
            },
        )
