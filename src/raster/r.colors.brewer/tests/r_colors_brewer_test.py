"""Tests for the r.colors.brewer addon."""

import pytest

from grass.exceptions import CalledModuleError

# Published ColorBrewer values, used to check the generated rules.
BLUES5 = ["239:243:255", "189:215:231", "107:174:214", "49:130:189", "8:81:156"]
BLUES3 = ["222:235:247", "158:202:225", "49:130:189"]
SET1_3 = ["228:26:28", "55:126:184", "77:175:74"]


def parse_rules(text):
    """Parse 'position color' rule lines into a list of (position, color)."""
    rules = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            position, color = line.split()
            rules.append((position, color))
    return rules


def test_sequential_continuous_percent(tools):
    text = tools.r_colors_brewer(sequential="Blues", classes=5, flags="n").text
    rules = parse_rules(text)
    assert [position for position, _ in rules] == ["0%", "25%", "50%", "75%", "100%"]
    assert [color for _, color in rules] == BLUES5


def test_reverse(tools):
    text = tools.r_colors_brewer(sequential="Blues", classes=5, flags="nr").text
    assert [color for _, color in parse_rules(text)] == BLUES5[::-1]


def test_discrete_bands_are_doubled(tools):
    text = tools.r_colors_brewer(sequential="Blues", classes=5, flags="nd").text
    rules = parse_rules(text)
    assert [position for position, _ in rules] == [
        "0%",
        "20%",
        "20%",
        "40%",
        "40%",
        "60%",
        "60%",
        "80%",
        "80%",
        "100%",
    ]
    colors = [color for _, color in rules]
    # Each class spans two identical boundary entries (a flat band).
    assert colors[0] == colors[1] == BLUES5[0]
    assert colors[8] == colors[9] == BLUES5[4]


def test_classes_out_of_range_fails(tools):
    with pytest.raises(CalledModuleError):
        tools.r_colors_brewer(sequential="Blues", classes=11, flags="n")


def test_two_schemes_are_exclusive(tools):
    with pytest.raises(CalledModuleError):
        tools.r_colors_brewer(
            sequential="Blues", diverging="RdBu", classes=5, flags="n"
        )


def test_breakpoints_wrong_count_fails(tools):
    with pytest.raises(CalledModuleError):
        tools.r_colors_brewer(
            sequential="Blues", classes=5, breakpoints="0,1,2", flags="n"
        )


def test_breakpoints_mixed_units_fail(tools):
    with pytest.raises(CalledModuleError):
        tools.r_colors_brewer(
            sequential="Blues",
            classes=5,
            breakpoints="0%,20%,40%,60%,80%,100",
            flags="n",
        )


def test_breakpoints_not_increasing_fails(tools):
    with pytest.raises(CalledModuleError):
        tools.r_colors_brewer(
            sequential="Blues", classes=5, breakpoints="0,20,10,30,40,50", flags="n"
        )


def test_breakpoints_discrete(tools):
    text = tools.r_colors_brewer(
        sequential="Blues", classes=3, flags="nd", breakpoints="0,10,20,30"
    ).text
    # Absolute breakpoints are extended to -inf/inf so out-of-range cells keep
    # the end colors.
    assert parse_rules(text) == [
        ("-inf", BLUES3[0]),
        ("0", BLUES3[0]),
        ("10", BLUES3[0]),
        ("10", BLUES3[1]),
        ("20", BLUES3[1]),
        ("20", BLUES3[2]),
        ("30", BLUES3[2]),
        ("inf", BLUES3[2]),
    ]


def test_breakpoints_continuous_midpoints(tools):
    text = tools.r_colors_brewer(
        sequential="Blues", classes=3, flags="n", breakpoints="0,10,20,30"
    ).text
    assert parse_rules(text) == [
        ("-inf", BLUES3[0]),
        ("0", BLUES3[0]),
        ("5", BLUES3[0]),
        ("15", BLUES3[1]),
        ("25", BLUES3[2]),
        ("30", BLUES3[2]),
        ("inf", BLUES3[2]),
    ]


def test_range_gives_absolute_positions(tools):
    text = tools.r_colors_brewer(
        sequential="Blues", classes=5, range="0,100", flags="n"
    ).text
    rules = parse_rules(text)
    assert [position for position, _ in rules] == [
        "-inf",
        "0",
        "25",
        "50",
        "75",
        "100",
        "inf",
    ]
    assert [color for _, color in rules] == [BLUES5[0], *BLUES5, BLUES5[4]]


def test_percent_breakpoints_spanning_are_not_clamped(tools):
    text = tools.r_colors_brewer(
        sequential="Blues", classes=4, flags="n", breakpoints="0%,25%,50%,75%,100%"
    ).text
    positions = [position for position, _ in parse_rules(text)]
    assert "-inf" not in positions
    assert "inf" not in positions


def test_percent_breakpoints_not_spanning_are_clamped(tools):
    text = tools.r_colors_brewer(
        sequential="Blues", classes=4, flags="n", breakpoints="10%,30%,50%,70%,90%"
    ).text
    rules = parse_rules(text)
    assert rules[0] == ("-inf", "239:243:255")  # Blues 4-class first color
    assert rules[-1] == ("inf", "33:113:181")  # Blues 4-class last color


def test_null_color_appended(tools):
    text = tools.r_colors_brewer(
        sequential="Blues", classes=5, null_color="white", flags="n"
    ).text
    assert text.strip().splitlines()[-1] == "nv white"


def test_qualitative_maps_to_categories(tools):
    text = tools.r_colors_brewer(qualitative="Set1", classes=3, flags="n").text
    assert parse_rules(text) == [("1", SET1_3[0]), ("2", SET1_3[1]), ("3", SET1_3[2])]


def test_qualitative_ignores_breakpoints(tools):
    # breakpoints do not apply to qualitative schemes; they are ignored.
    text = tools.r_colors_brewer(
        qualitative="Set1", classes=3, breakpoints="0,1,2,3", flags="n"
    ).text
    assert parse_rules(text) == [("1", SET1_3[0]), ("2", SET1_3[1]), ("3", SET1_3[2])]


def test_apply_to_map(tools):
    tools.r_colors_brewer(map="rast", sequential="Blues", classes=5)
    out = tools.r_colors_out(map="rast").text
    # Endpoints of the continuous ramp reach the extreme class colors.
    assert "239:243:255" in out
    assert "8:81:156" in out


def test_apply_with_range_clamps_out_of_range(tools):
    # rast spans 2..10; a narrower range must not leave the ends uncolored.
    tools.r_colors_brewer(map="rast", sequential="Blues", classes=5, range="4,8")
    rules = parse_rules(tools.r_colors_out(map="rast").text)
    positions = [position for position, _ in rules]
    assert "-inf" in positions
    assert "inf" in positions
    below = dict(rules)["-inf"]
    above = dict(rules)["inf"]
    assert below == "239:243:255"  # first Blues color for values below 4
    assert above == "8:81:156"  # last Blues color for values above 8
