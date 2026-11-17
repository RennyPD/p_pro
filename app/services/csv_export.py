def spreadsheet_safe_row(values):
    return [
        "'" + value
        if isinstance(value, str)
        and (
            value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))
        )
        else value
        for value in values
    ]
