from __future__ import annotations


def format_company_display(
    company_name: str | None,
    matched_companies: list[str] | None = None,
) -> str:
    candidates: list[str] = []

    if matched_companies:
        for item in matched_companies:
            normalized = str(item).strip()
            if normalized and normalized not in candidates:
                candidates.append(normalized)

    if company_name:
        normalized_name = str(company_name).strip()
        if normalized_name:
            for piece in normalized_name.replace("，", ",").split(","):
                normalized = piece.strip()
                if normalized and normalized not in candidates:
                    candidates.append(normalized)

    if not candidates:
        return "Unknown"

    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) == 2:
        return " / ".join(candidates)

    return f"{candidates[0]} / {candidates[1]} (+{len(candidates) - 2})"
