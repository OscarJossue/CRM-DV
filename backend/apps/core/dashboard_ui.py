from urllib.parse import urlencode


def query_string_with(request, **overrides):
    """Return the current query string with pagination removed and overrides applied."""
    params = request.GET.copy()
    params.pop("page", None)

    for key, value in overrides.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value

    return urlencode(params, doseq=True)


def build_dashboard_items(request, definitions, counts, active_value="", parameter="status"):
    """Build consistent dashboard cards while preserving the remaining filters."""
    items = []
    for definition in definitions:
        value = definition["value"]
        items.append(
            {
                **definition,
                "count": int(counts.get(value, 0) or 0),
                "is_active": active_value == value,
                "query_string": query_string_with(request, **{parameter: value}),
            }
        )
    return items
