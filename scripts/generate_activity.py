import json
import os
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path


USERNAME = "lnunesdev"
OUTPUT = Path("assets/activity.svg")

GRAPHQL_URL = "https://api.github.com/graphql"


QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            date
            contributionCount
            contributionLevel
            color
          }
        }
        months {
          name
          year
          firstDay
          totalWeeks
        }
      }
    }
  }
}
"""


def github_request(token, variables):
    payload = json.dumps({
        "query": QUERY,
        "variables": variables
    }).encode("utf-8")

    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "lnunesdev-activity-generator"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API returned HTTP {error.code}: {body}"
        ) from error


def escape_xml(value):
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def get_date_range():
    today = datetime.utcnow().date()

    end = today + timedelta(days=1)
    start = end - timedelta(days=365)

    return (
        start.isoformat() + "T00:00:00Z",
        end.isoformat() + "T00:00:00Z"
    )


def get_calendar(token):
    start, end = get_date_range()

    result = github_request(
        token,
        {
            "login": USERNAME,
            "from": start,
            "to": end
        }
    )

    if "errors" in result:
        raise RuntimeError(
            "GitHub GraphQL error:\n" +
            json.dumps(result["errors"], indent=2)
        )

    user = result.get("data", {}).get("user")

    if not user:
        raise RuntimeError(
            f"GitHub user '{USERNAME}' was not found."
        )

    return user["contributionsCollection"]["contributionCalendar"]


def build_days(calendar):
    days = []

    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append(day)

    return days


def month_positions(calendar, x_start, cell_size, gap):
    positions = []

    current_week = 0

    for month in calendar["months"]:
        first_day = month["firstDay"]

        matching_week = None

        for index, week in enumerate(calendar["weeks"]):
            if week["firstDay"] <= first_day:
                matching_week = index
            else:
                break

        if matching_week is None:
            matching_week = current_week

        x = x_start + matching_week * (cell_size + gap)

        positions.append({
            "name": month["name"],
            "year": month["year"],
            "x": x
        })

        current_week = matching_week

    return positions


def generate_svg(calendar):
    days = build_days(calendar)

    total = calendar["totalContributions"]

    width = 1000
    height = 300

    bg = "#0d1117"
    primary = "#f0f6fc"
    secondary = "#8b949e"
    border = "#30363d"

    x_start = 40
    y_start = 105

    cell_size = 12
    gap = 4

    week_width = cell_size + gap

    svg = []

    svg.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
    )

    svg.append("""
    <style>
        .title {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                         Helvetica, Arial, sans-serif;
            font-size: 21px;
            font-weight: 600;
            fill: #f0f6fc;
        }

        .subtitle {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                         Helvetica, Arial, sans-serif;
            font-size: 13px;
            fill: #8b949e;
        }

        .month {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                         Helvetica, Arial, sans-serif;
            font-size: 11px;
            fill: #8b949e;
        }

        .weekday {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI",
                         Helvetica, Arial, sans-serif;
            font-size: 10px;
            fill: #8b949e;
        }

        .day {
            stroke: #0d1117;
            stroke-width: 1;
        }

        .day:hover {
            stroke: #f0f6fc;
        }

        @keyframes appear {
            from {
                opacity: 0;
                transform: scale(0.65);
            }

            to {
                opacity: 1;
                transform: scale(1);
            }
        }

        .animated {
            transform-box: fill-box;
            transform-origin: center;
            animation: appear 0.45s ease-out forwards;
        }
    </style>
    """)

    svg.append(
        f'<rect width="{width}" height="{height}" '
        f'rx="16" fill="{bg}" stroke="{border}" />'
    )

    svg.append(
        f'<text x="40" y="40" class="title">'
        f'GitHub Activity'
        f'</text>'
    )

    svg.append(
        f'<text x="40" y="65" class="subtitle">'
        f'{escape_xml(USERNAME)} • {total:,} contributions in the last year'
        f'</text>'
    )

    # Dias da semana
    weekdays = [
        ("Mon", 1),
        ("Wed", 3),
        ("Fri", 5),
    ]

    for label, weekday in weekdays:
        y = y_start + (weekday - 1) * week_width + 10

        svg.append(
            f'<text x="8" y="{y}" class="weekday">'
            f'{label}'
            f'</text>'
        )

    # Meses
    months = month_positions(
        calendar,
        x_start,
        cell_size,
        gap
    )

    for month in months:
        svg.append(
            f'<text x="{month["x"]}" y="91" class="month">'
            f'{escape_xml(month["name"])}'
            f'</text>'
        )

    # Contribuições
    for index, week in enumerate(calendar["weeks"]):
        for day in week["contributionDays"]:

            weekday = day["weekday"]

            x = x_start + index * week_width
            y = y_start + (weekday - 1) * week_width

            color = day["color"]
            count = day["contributionCount"]

            delay = (index * 0.018) + (weekday * 0.008)

            tooltip = (
                f'{count} contribution'
                f'{"s" if count != 1 else ""} on {day["date"]}'
            )

            svg.append(
                f'<g transform="translate({x},{y})">'
            )

            svg.append(
                f'<title>{escape_xml(tooltip)}</title>'
            )

            svg.append(
                f'<rect '
                f'class="day animated" '
                f'x="0" y="0" '
                f'width="{cell_size}" '
                f'height="{cell_size}" '
                f'rx="3" '
                f'fill="{escape_xml(color)}" '
                f'style="animation-delay:{delay:.3f}s" '
                f'/>'
            )

            svg.append('</g>')

    # Legenda
    legend_y = 235

    svg.append(
        f'<text x="40" y="{legend_y}" class="subtitle">'
        f'Less'
        f'</text>'
    )

    legend_colors = [
        "#161b22",
        "#0e4429",
        "#006d32",
        "#26a641",
        "#39d353",
    ]

    for index, color in enumerate(legend_colors):

        x = 75 + index * 22

        svg.append(
            f'<rect '
            f'x="{x}" '
            f'y="{legend_y - 11}" '
            f'width="13" '
            f'height="13" '
            f'rx="3" '
            f'fill="{color}" '
            f'/>'
        )

    svg.append(
        f'<text x="190" y="{legend_y}" class="subtitle">'
        f'More'
        f'</text>'
    )

    svg.append(
        f'<text x="{width - 190}" y="{legend_y}" class="subtitle">'
        f'Updated automatically'
        f'</text>'
    )

    svg.append("</svg>")

    return "\n".join(svg)


def main():
    token = os.environ.get("GITHUB_TOKEN")

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN environment variable is missing."
        )

    print(f"Fetching GitHub contribution data for {USERNAME}...")

    calendar = get_calendar(token)

    svg = generate_svg(calendar)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    OUTPUT.write_text(
        svg,
        encoding="utf-8"
    )

    print(
        f"Activity SVG generated successfully: {OUTPUT}"
    )

    print(
        f"Total contributions: "
        f"{calendar['totalContributions']}"
    )


if __name__ == "__main__":
    main()