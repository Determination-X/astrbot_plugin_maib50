from .base50 import Base50Helper


class B50Helper(Base50Helper):
    def _build_b50_rated_entries(self, plugin, entries: list[dict]) -> list[dict]:
        return self._build_rated_entries(plugin, entries, lambda entry: True)

    def select_b50(
        self, plugin, entries: list[dict]
    ) -> tuple[int | None, list[dict], list[dict]]:
        return self._select_entries(plugin, entries, lambda entry: True)

    def render_summary(
        self, plugin, profile: dict | None, entries: list[dict] | None
    ) -> str:
        return self._render_summary(
            plugin,
            profile,
            entries,
            self.select_b50,
            lambda entries: [
                f"Played charts: {sum(not entry['unplayed'] for entry in entries)} / {len(entries)}",
                f"Unplayed charts excluded: {len(entries) - sum(not entry['unplayed'] for entry in entries)}",
            ],
            "B50",
            "New15",
            "Old35",
            "No current-version charts found in New15 selection.",
            "No old-version charts found in Old35 selection.",
            "No rated charts found for this friend (missing constants or low achievements).",
        )

    async def generate_image(
        self, plugin, profile: dict | None, entries: list[dict], uid: str
    ) -> str:
        return await self._generate_image(
            plugin,
            profile,
            entries,
            self.select_b50,
            "Profile data is required to generate B50 image",
        )
