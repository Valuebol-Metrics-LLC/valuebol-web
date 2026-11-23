"""Offline tests: run the whole scraper against sample pages shaped like upsl.com.

    python scraper/test_scraper.py
"""
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import upsl_scraper as S  # noqa: E402

TEAMS = """
<html><body><header><a href="https://www.instagram.com/upslsoccer/">UPSL</a></header>
<div class="teams__card--container" data-team-id="430068" data-team-name="Chicago Nation FC" data-team-conference="Midwest Central">
  <a href="https://premier.upsl.com/teams/chicago-nation-fc-430068"><img data-src="/wp-content/uploads/cnfc.png" src="data:image/gif;base64,R0lGOD"></a></div>
<div class="teams__card--container" data-team-id="33621" data-team-name="Lynchburg FC" data-team-conference="DMV South">
  <a href="https://division1upsl.com/teams/lynchburg-fc-33621/"><img srcset="/l-150.png 150w, /l-600.png 600w"></a></div>
""" + "".join(
    f'<div class="teams__card--container" data-team-id="{i}" data-team-name="Club {i}" data-team-conference="Test">'
    f'<a href="https://premier.upsl.com/teams/club-{i}"><img src="/default-crest.png"></a></div>' for i in range(6)
) + "</body></html>"

CNFC = """
<html><body><header><a href="https://www.instagram.com/upslsoccer/">UPSL</a></header>
<div class="single-team__header"><div class="single-team__logo"><img src="https://cdn.upsl.com/cnfc-big.png"></div>
 <span class="single-team__location">Chicago, IL</span>
 <a href="https://chicagonationfc.com">Site</a><a href="https://www.instagram.com/chicagonationfc/?hl=en">IG</a>
 <a href="https://x.com/chicagonationfc">X</a></div>
<select id="single__select-season"><option>2024 Spring</option><option selected="selected">2026 Fall</option></select>
<table id="single-team-schedule"><thead><tr><th>Home</th><th>Away</th><th>Date</th><th>Time</th><th>H</th><th>A</th><th>Venue</th><th></th></tr></thead><tbody>
<tr><td><a>Isthmus City FC</a></td><td><a>Chicago Nation FC</a></td><td>03/30/2026</td><td>5:00 pm PT</td><td>0</td><td>7</td><td>Breese Stevens Field</td><td>upsl__show__results</td></tr>
<tr><td><a>Chicago Nation FC</a></td><td><a>Street Dreams</a></td><td>04/21/2026</td><td>5:30 pm PT</td><td>0</td><td>0</td><td>College of DuPage</td><td>upsl__show__schedule</td></tr>
</tbody></table>
<span class="single-team__roster-player-name">Samuel
Marchi</span><span class="single-team__roster-player-title">DEFENDER</span><span class="single-team__roster-player-appearances">Appearances: 12</span>
<footer><a href="https://www.facebook.com/upslsoccer">fb</a></footer></body></html>
"""

LYNCH = """<html><body><div class="single-team__info"><img src="/lfc.png"><h1>Lynchburg FC</h1><p>DMV South</p><p>Lynchburg,
VA</p></div><select id="single__select-season"><option selected>Select a Season</option><option>2024 Spring</option></select>
<table id="single-team-schedule"><tbody><tr><td><a>Lynchburg FC</a></td><td><a>DC United U19</a></td><td>04/20/2024</td><td>4</td><td>1</td><td>City Stadium</td></tr></tbody></table></body></html>"""

PLAIN = "<html><body><div class='single-team__header'><img src='/default-crest.png'></div></body></html>"


def png(color, size=(300, 200)):
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGBA", size, color).save(b, "PNG")
    return b.getvalue()


class FakeFetcher:
    refresh = False

    def html(self, url):
        if url == S.TEAMS_URL:
            return TEAMS
        if "chicago-nation" in url:
            return CNFC
        if "lynchburg" in url:
            assert "division1.upsl.com" in url, url  # missing dot fixed
            return LYNCH
        return PLAIN

    def binary(self, url):
        if "default-crest" in url:
            return png((200, 200, 200, 255))
        if "l-600" in url:
            return b"not an image"
        return png((20, 120, 60, 255))

    def close(self):
        pass


def main():
    tmp = Path(tempfile.mkdtemp())
    S.ROOT, S.LOGO_DIR, S.DATA_DIR = tmp, tmp / "public" / "logos", tmp / "src" / "data" / "upsl"

    class A:
        limit = None; only = None; refresh = False

    f = FakeFetcher()
    S.cmd_teams(f, A)
    S.cmd_rosters(f, A)
    S.cmd_results(f, A)

    teams = {t["name"]: t for t in json.loads((S.DATA_DIR / "teams.json").read_text())}
    cn = teams["Chicago Nation FC"]
    assert cn["instagram"] == "chicagonationfc", cn
    assert cn["website"] == "https://chicagonationfc.com", cn
    assert cn["twitter"].endswith("/chicagonationfc"), cn
    assert cn["city"] == "Chicago, IL", cn
    assert cn["logo"] == "logos/chicago-nation-fc.png" and cn["logo_source"].endswith("cnfc-big.png"), cn
    assert "facebook" not in cn, "league footer link leaked"
    lf = teams["Lynchburg FC"]
    assert lf["city"] == "Lynchburg, VA", lf
    assert "2024 Spring" in (S.DATA_DIR / "results.csv").read_text()
    assert lf["division"] == "division1" and lf["logo_source"].endswith("/lfc.png"), lf
    assert not any(teams[f"Club {i}"].get("logo") for i in range(6)), "placeholder crest kept"
    assert len(list(S.LOGO_DIR.glob("*.png"))) == 2

    from PIL import Image
    assert Image.open(S.LOGO_DIR / "chicago-nation-fc.png").size == (256, 256)

    rosters = json.loads((S.DATA_DIR / "rosters.json").read_text())
    assert rosters["chicago-nation-fc"]["players"][0] == {"player": "Samuel Marchi", "position": "DEFENDER", "appearances": 12}

    csv_text = (S.DATA_DIR / "results.csv").read_text()
    assert "03/30/2026,5:00 pm PT,Isthmus City FC,Chicago Nation FC,0,7,Breese Stevens Field,True" in csv_text, csv_text
    assert "Street Dreams,,,College of DuPage,False" in csv_text, csv_text  # scheduled: no fake 0-0
    assert "04/20/2024,,Lynchburg FC,DC United U19,4,1,City Stadium,True" in csv_text, csv_text  # old 6-column layout
    shutil.rmtree(tmp)
    print("all scraper tests passed")


if __name__ == "__main__":
    main()
