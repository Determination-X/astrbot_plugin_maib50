"""Parse /mai alias arguments without treating song apostrophes as shell quotes."""


def parse_alias_command(arguments: str) -> tuple[str, str, str]:
    """Return action, alias/keyword/ID, and song title.

    Only a double-quoted alias is special; the song title stays literal.
    """
    parts = arguments.strip().split(maxsplit=1)
    if not parts:
        return "", "", ""

    action = parts[0].casefold()
    remainder = parts[1].strip() if len(parts) > 1 else ""
    if not remainder:
        return action, "", ""

    if remainder.startswith('"'):
        closing = remainder.find('"', 1)
        if closing < 0 or (
            closing + 1 < len(remainder) and not remainder[closing + 1].isspace()
        ):
            raise ValueError("别名双引号未正确闭合；多词别名请用成对双引号括起来。")
        alias = remainder[1:closing]
        title = remainder[closing + 1 :].strip()
    else:
        values = remainder.split(maxsplit=1)
        alias = values[0]
        title = values[1].strip() if len(values) > 1 else ""

    if action == "list" and title:
        alias = f"{alias} {title}"
        title = ""
    elif len(title) >= 2 and title[0] == title[-1] and title[0] in ("'", '"'):
        title = title[1:-1]

    return action, alias, title
