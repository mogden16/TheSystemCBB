from ncaam_picks_bot.parser import build_matchup_key, parse_message_lines


def test_parse_message_lines() -> None:
    content = [
        "BREAKING:",
        "",
        "Alabama +7.5 at Florida",
        "Maryland +13.5 over Purdue",
        "Bad line here",
    ]
    picks, rejected = parse_message_lines(content)

    assert len(picks) == 2
    assert picks[0].team == "Alabama"
    assert picks[0].spread == 7.5
    assert picks[0].relation == "at"
    assert picks[0].opponent == "Florida"
    assert len(rejected) == 1
    assert rejected[0].line_no == 5


def test_build_matchup_key_normalization() -> None:
    key = build_matchup_key("North Carolina!", "Duke  ", "over")
    assert key == "north carolinadukeover"
