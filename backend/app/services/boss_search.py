from __future__ import annotations

from urllib.parse import urlencode

_BOSS_CITY_CODES = {
    "北京": "101010100",
    "上海": "101020100",
    "天津": "101030100",
    "重庆": "101040100",
    "广州": "101280100",
    "深圳": "101280600",
    "杭州": "101210100",
    "南京": "101190100",
    "苏州": "101190400",
    "成都": "101270100",
    "武汉": "101200100",
    "西安": "101110100",
    "济南": "101120100",
    "青岛": "101120200",
    "郑州": "101180100",
    "长沙": "101250100",
    "合肥": "101220100",
    "厦门": "101230201",
    "福州": "101230101",
    "宁波": "101210401",
}


def build_boss_search_url(keyword: str, city: str | None, work_type: str | None) -> str:
    query = {"query": _normalize_keyword(keyword)}
    city_code = _city_code(city)
    if city_code:
        query["city"] = city_code
    return f"https://www.zhipin.com/web/geek/jobs?{urlencode(query)}"


def _normalize_keyword(keyword: str) -> str:
    return " ".join(keyword.split()).strip()


def _city_code(city: str | None) -> str | None:
    if not city:
        return None
    cleaned = city.strip()
    return _BOSS_CITY_CODES.get(cleaned)
