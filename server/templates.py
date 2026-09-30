"""Deterministic advisory templates.

These are the always-available fallback for every language the console offers.
They live in their own module rather than inside the FastAPI app so that the
Gemini adapter can use them without importing the web framework, which keeps the
adapter unit-testable with no server running.

Templates must never state a number that is not in the exposure payload, and must
always name IMD/OSDMA as the warning authority.
"""
from __future__ import annotations

WARNING_AUTHORITY = "IMD/OSDMA"

_HI = (
    "चक्रवात परिदृश्य समीक्षा — केन्द्रापाड़ा ज़िला, ओडिशा। "
    "परिदृश्य स्टर्म सर्ज {surge:.1f} मीटर: लगभग {area:.0f} वर्ग किमी भूमि जलमग्न होने का "
    "स्क्रीनिंग अनुमान। {medical} स्वास्थ्य केंद्र, {shelter} आश्रय-क्षमता प्रॉक्सी और "
    "{power} विद्युत परिसंपत्तियाँ सर्ज क्षेत्र में। "
    "यह केवल मानव समीक्षा हेतु प्रारूप है, आधिकारिक चेतावनी नहीं। "
    "आधिकारिक चेतावनी के लिए {authority} देखें।"
)

_OR = (
    "ବାତ୍ୟା ପରିଦୃଶ୍ୟ ସମୀକ୍ଷା — କେନ୍ଦ୍ରାପଡ଼ା ଜିଲ୍ଲା, ଓଡ଼ିଶା। "
    "ପରିଦୃଶ୍ୟ ସର୍ଜ {surge:.1f} ମିଟର: ପ୍ରାୟ {area:.0f} ବର୍ଗ କିମି ଭୂମି ଜଳମଗ୍ନ ହେବାର "
    "ସ୍କ୍ରିନିଂ ଅନୁମାନ। {medical} ସ୍ୱାସ୍ଥ୍ୟ କେନ୍ଦ୍ର, {shelter} ଆଶ୍ରୟ-କ୍ଷମତା ପ୍ରକ୍ସି ଏବଂ "
    "{power} ବିଦ୍ୟୁତ ଆସେଟ ସର୍ଜ କ୍ଷେତ୍ରରେ। "
    "ଏହା କେବଳ ମାନବ ସମୀକ୍ଷା ପାଇଁ ଡ୍ରାଫ୍ଟ, ଅଧିକୃତ ସତର୍କତା ନୁହେଁ। "
    "ଅଧିକୃତ ସତର୍କତା ପାଇଁ {authority} ଦେଖନ୍ତୁ।"
)

_EN = (
    "CYCLONE SCENARIO REVIEW — Kendrapara district, Odisha. Screening scenario surge "
    "{surge:.1f} m: about {area:.0f} sq km of land screened as inundated, including "
    "{medical} health facility(ies), {shelter} shelter-capacity proxy(ies) and {power} "
    "power asset(s). {road:.0f} km of road and {grid:.0f} km of transmission line "
    "intersect the scenario. This is a screening-level draft for human review, not an "
    "official forecast or evacuation instruction. Official warnings are issued by {authority}."
)


def template_advisory(surge: float, lang: str, exposure: dict) -> str:
    """Build the deterministic advisory for one language.

    Unknown languages fall back to English rather than returning an empty string,
    so a reviewer always sees something actionable.
    """
    fields = {
        "surge": float(surge),
        "area": float(exposure.get("areaKm2", 0) or 0),
        "medical": int(exposure.get("medical", 0) or 0),
        "shelter": int(exposure.get("shelter", 0) or 0),
        "power": int(exposure.get("power", 0) or 0),
        "road": float(exposure.get("roadKm", 0) or 0),
        "grid": float(exposure.get("gridKm", 0) or 0),
        "authority": WARNING_AUTHORITY,
    }
    template = {"hi": _HI, "or": _OR}.get(lang, _EN)
    return template.format(**fields)
