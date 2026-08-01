def new_lines(
    old_text: str,
    new_text: str
) -> list[str]:

    old_set = set(old_text.splitlines())

    seen = set()

    result = []

    for line in new_text.splitlines():

        if line in old_set:
            continue

        if line in seen:
            continue

        seen.add(line)
        result.append(line)

    return result
