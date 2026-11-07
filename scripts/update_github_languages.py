#!/usr/bin/env python3
import html
import json
import math
import os
import urllib.error
import urllib.request
from pathlib import Path


USERNAME = os.environ.get("GITHUB_REPOSITORY_OWNER", "trajkovskim")
API_BASE = "https://api.github.com"
OUTPUT = Path(__file__).resolve().parents[1] / "assets" / "github-languages.svg"
CHART_WIDTH = 640
DONUT_RADIUS = 78
DONUT_STROKE = 34
LEGEND_ROW_HEIGHT = 22
DOWN_CHART_WIDTH = 900
DOWN_DONUT_RADIUS = 150
DOWN_DONUT_STROKE = 40
DOWN_LEGEND_TOP = 390
DOWN_LEGEND_ROW_HEIGHT = 21
MAX_CHART_HEIGHT = 1000
LEGEND_POSITION = "down"
LEGEND_POSITIONS = {"right", "down"}


def github_json(url, token):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "github-language-chart",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def repositories(token):
    result = []
    page = 1
    while True:
        url = (
            f"{API_BASE}/users/{USERNAME}/repos"
            f"?type=owner&per_page=100&page={page}"
        )
        batch = github_json(url, token)
        if not batch:
            break
        result.extend(
            repo
            for repo in batch
            if not repo["private"] and not repo["fork"] and not repo["archived"]
        )
        page += 1
    return result


def language_totals(repos, token):
    totals = {}
    for repo in repos:
        languages = github_json(repo["languages_url"], token)
        for language, size in languages.items():
            totals[language] = totals.get(language, 0) + size
    return totals


def svg_text(value):
    return html.escape(str(value), quote=True)


def language_color(index):
    hue = (index * 137.508) % 360
    return f"hsl({hue:.0f} 68% 66%)"


def create_svg(totals):
    if LEGEND_POSITION not in LEGEND_POSITIONS:
        raise ValueError(f"LEGEND_POSITION must be one of {sorted(LEGEND_POSITIONS)}.")

    total_bytes = sum(totals.values())
    if total_bytes <= 0:
        raise RuntimeError("GitHub returned no language data for the selected repositories.")

    sorted_languages = sorted(totals.items(), key=lambda item: (-item[1], item[0]))
    display_percentages = [
        round(size / total_bytes * 100, 2)
        for _, size in sorted_languages
    ]
    display_percentages[-1] = round(100 - sum(display_percentages[:-1]), 2)
    if LEGEND_POSITION == "down":
        max_legend_rows = (
            MAX_CHART_HEIGHT - DOWN_LEGEND_TOP - 10
        ) // DOWN_LEGEND_ROW_HEIGHT
        if len(sorted_languages) > max_legend_rows:
            visible_language_count = max_legend_rows - 1
            other_size = sum(size for _, size in sorted_languages[visible_language_count:])
            sorted_languages = [
                *sorted_languages[:visible_language_count],
                ("Other", other_size),
            ]
            display_percentages = [
                round(size / total_bytes * 100, 2)
                for _, size in sorted_languages
            ]
            display_percentages[-1] = round(100 - sum(display_percentages[:-1]), 2)
    rows_per_column = math.ceil(len(sorted_languages) / 2)
    if LEGEND_POSITION == "right":
        chart_width = CHART_WIDTH
        chart_height = max(220, rows_per_column * LEGEND_ROW_HEIGHT + 24)
        center_x = 140
        center_y = chart_height / 2
        donut_radius = DONUT_RADIUS
        donut_stroke = DONUT_STROKE
    else:
        chart_width = DOWN_CHART_WIDTH
        chart_height = (
            DOWN_LEGEND_TOP
            + len(sorted_languages) * DOWN_LEGEND_ROW_HEIGHT
            + 10
        )
        center_x = chart_width / 2
        donut_radius = DOWN_DONUT_RADIUS
        donut_stroke = DOWN_DONUT_STROKE
        center_y = donut_radius + donut_stroke / 2 + 12
    circumference = 2 * math.pi * donut_radius
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{chart_width}" height="{chart_height}" viewBox="0 0 {chart_width} {chart_height}" fill="none" role="img" aria-labelledby="title description">',
        '  <title id="title">GitHub language distribution</title>',
        f'  <desc id="description">{"; ".join(f"{svg_text(name)} {percent:.2f}%" for (name, _), percent in zip(sorted_languages, display_percentages))}</desc>',
    ]

    offset = 0.0
    for index, (name, size) in enumerate(sorted_languages):
        arc_length = circumference * size / total_bytes
        color = language_color(index)
        lines.extend(
            [
                f'  <circle cx="{center_x}" cy="{center_y:.1f}" r="{donut_radius}" stroke="{color}" stroke-width="{donut_stroke}" stroke-dasharray="{arc_length:.3f} {circumference - arc_length:.3f}" stroke-dashoffset="{-offset:.3f}" transform="rotate(-90 {center_x} {center_y:.1f})"/>',
            ]
        )
        offset += arc_length

    for index, (name, _) in enumerate(sorted_languages):
        column = index // rows_per_column
        row = index % rows_per_column
        if LEGEND_POSITION == "right":
            x = 278 + column * 194
            y = (chart_height - rows_per_column * LEGEND_ROW_HEIGHT) / 2 + row * LEGEND_ROW_HEIGHT + 10
            percent_offset = 164
        else:
            x = 130
            y = DOWN_LEGEND_TOP + index * DOWN_LEGEND_ROW_HEIGHT
            percent_offset = 640
        color = language_color(index)
        percent = display_percentages[index]
        font_size = 18 if LEGEND_POSITION == "down" else 13
        percent_font_size = 16 if LEGEND_POSITION == "down" else 12
        lines.extend(
            [
                f'  <circle cx="{x}" cy="{y - 6}" r="{7 if LEGEND_POSITION == "down" else 5}" fill="{color}"/>',
                f'  <text x="{x + 12}" y="{y}" fill="#e6edf3" font-family="ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif" font-size="{font_size}">{svg_text(name)}</text>',
                f'  <text x="{x + percent_offset}" y="{y}" text-anchor="end" fill="#9ba8c7" font-family="ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif" font-size="{percent_font_size}">{percent:.2f}%</text>',
            ]
        )

    lines.extend(["</svg>", ""])
    return "\n".join(lines)


def main():
    token = os.environ.get("GITHUB_TOKEN")
    repos = repositories(token)
    if not repos:
        raise RuntimeError(f"No public, non-fork repositories found for {USERNAME}.")
    totals = language_totals(repos, token)
    OUTPUT.write_text(create_svg(totals), encoding="utf-8")
    print(f"Updated {OUTPUT} from {len(repos)} repositories.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as error:
        raise SystemExit(f"GitHub API request failed: HTTP {error.code} {error.reason}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"Could not reach the GitHub API: {error.reason}") from error
