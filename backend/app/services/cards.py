"""Share-preview images (1200x630 PNG) for social networks."""

from __future__ import annotations

import io
from functools import lru_cache
from typing import Optional, Sequence

from PIL import Image, ImageDraw, ImageFont

from app.config import QUANT_LABEL

W, H = 1200, 630
BG, CARD, TEXT, MUTED = (11, 11, 15), (24, 24, 30), (244, 244, 245), (161, 161, 170)
CYAN, GREEN, RED, AMBER = (34, 211, 238), (52, 211, 153), (248, 113, 113), (251, 191, 36)
HORIZON_NAMES = {"4h": "4-hour", "24h": "24-hour", "1T": "1-week", "1M": "1-month", "1R": "1-year"}
FOOTER = "aicryptopredictor.netlify.app  ·  Not financial advice"


@lru_cache(maxsize=16)
def _font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.load_default(size=size)


def _model_name(model: str) -> str:
    return {QUANT_LABEL: "Free statistical model", "Custom (OpenAI-compatible)": "a custom AI model"}.get(model, model)


def _canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((60, 54, 96, 90), radius=9, fill=CYAN)
    draw.text((112, 58), "AI Crypto Analytics", font=_font(28), fill=TEXT)
    draw.text((60, H - 64), FOOTER, font=_font(22), fill=MUTED)
    return img, draw


def _png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _line_chart(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], series: Sequence[float],
                start: Optional[float], color: tuple) -> None:
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=18, fill=CARD)
    values = [v for v in ([start] if start else []) + list(series) if isinstance(v, (int, float))]
    if len(values) < 2:
        return
    lo, hi = min(values), max(values)
    span = (hi - lo) or abs(hi) * 0.01 or 1.0
    pad = 28
    pts = [(x0 + pad + (x1 - x0 - 2 * pad) * i / (len(values) - 1),
            y1 - pad - (y1 - y0 - 2 * pad) * (v - lo) / span) for i, v in enumerate(values)]
    if start:
        draw.line([(x0 + pad, pts[0][1]), (x1 - pad, pts[0][1])], fill=(63, 63, 70), width=2)
    draw.line(pts, fill=color, width=6, joint="curve")
    draw.ellipse((pts[0][0] - 8, pts[0][1] - 8, pts[0][0] + 8, pts[0][1] + 8), fill=TEXT)
    draw.ellipse((pts[-1][0] - 9, pts[-1][1] - 9, pts[-1][0] + 9, pts[-1][1] + 9), fill=color)


def forecast_card(coin: str, horizon: str, model: str, prices: Sequence[float], start_price: Optional[float],
                  evaluation: Optional[dict]) -> bytes:
    img, draw = _canvas()
    draw.text((60, 122), coin[:10], font=_font(76), fill=TEXT)
    draw.text((60, 214), f"{HORIZON_NAMES.get(horizon, horizon)} forecast by {_model_name(model)}"[:38], font=_font(28), fill=MUTED)
    rising = bool(prices) and start_price is not None and prices[-1] >= start_price
    _line_chart(draw, (620, 130, 1140, 500), prices, start_price, GREEN if rising else RED)
    if evaluation:
        ok = bool(evaluation.get("direction_correct"))
        draw.text((60, 300), "Checked against the real price", font=_font(28), fill=MUTED)
        draw.text((60, 345), "Direction: correct" if ok else "Direction: wrong", font=_font(52), fill=GREEN if ok else RED)
        if evaluation.get("accuracy_pct") is not None:
            draw.text((60, 420), f"Accuracy {evaluation['accuracy_pct']}%", font=_font(36), fill=TEXT)
    else:
        draw.text((60, 300), "Predicted direction", font=_font(28), fill=MUTED)
        draw.text((60, 345), "Up" if rising else "Down", font=_font(64), fill=GREEN if rising else RED)
        draw.text((60, 430), "Result pending: checked when", font=_font(28), fill=AMBER)
        draw.text((60, 466), "the horizon ends", font=_font(28), fill=AMBER)
    return _png(img)


def track_record_card(totals: dict, providers: list[dict]) -> bytes:
    img, draw = _canvas()
    draw.text((60, 128), "Which AI predicts crypto best?", font=_font(56), fill=TEXT)
    draw.text((60, 200), "Public track record, every forecast checked against reality", font=_font(28), fill=MUTED)
    pct = lambda v: "—" if v is None else f"{v}%"  # noqa: E731
    stats = [(str(totals.get("evaluated", 0)), "forecasts checked"), (pct(totals.get("direction_hit_pct")), "direction hit"),
             (pct(totals.get("beats_baseline_pct")), "beat a naive guess")]
    for i, (value, label) in enumerate(stats):
        x = 60 + i * 360
        draw.rounded_rectangle((x, 262, x + 340, 392), radius=18, fill=CARD)
        draw.text((x + 26, 280), value, font=_font(52), fill=CYAN)
        draw.text((x + 26, 346), label, font=_font(24), fill=MUTED)
    for i, p in enumerate([p for p in providers if not p.get("low_sample")][:3] or providers[:3]):
        y = 420 + i * 44
        draw.text((60, y), _model_name(p["provider"])[:28], font=_font(26), fill=TEXT)
        bar = int(5 * p["direction_hit_pct"])
        draw.rounded_rectangle((520, y + 6, 520 + max(bar, 6), y + 30), radius=8, fill=CYAN if i == 0 else (82, 82, 91))
        draw.text((540 + max(bar, 6), y), f"{p['direction_hit_pct']}%", font=_font(24), fill=MUTED)
    return _png(img)


FORMATS = {"square": (1080, 1080), "story": (1080, 1920)}


def forecast_card_tall(fmt: str, coin: str, horizon: str, model: str, prices: Sequence[float],
                       start_price: Optional[float], evaluation: Optional[dict]) -> bytes:
    """Instagram / TikTok formats: 1:1 post or 9:16 story with the forecast chart in the middle."""
    w, h = FORMATS[fmt]
    story = fmt == "story"
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img)
    top = 140 if story else 70
    draw.rounded_rectangle((70, top, 116, top + 46), radius=11, fill=CYAN)
    draw.text((134, top + 4), "AI Crypto Analytics", font=_font(36), fill=TEXT)
    y = top + (150 if story else 110)
    draw.text((70, y), coin[:10], font=_font(120 if story else 96), fill=TEXT)
    y += 150 if story else 118
    draw.text((70, y), f"{HORIZON_NAMES.get(horizon, horizon)} forecast"[:30], font=_font(40), fill=MUTED)
    draw.text((70, y + 52), f"by {_model_name(model)}"[:34], font=_font(40), fill=MUTED)
    rising = bool(prices) and start_price is not None and prices[-1] >= start_price
    chart_top = y + (150 if story else 120)
    chart_bottom = chart_top + (720 if story else 320)
    _line_chart(draw, (70, chart_top, w - 70, chart_bottom), prices, start_price, GREEN if rising else RED)
    y = chart_bottom + (70 if story else 40)
    if evaluation:
        ok = bool(evaluation.get("direction_correct"))
        draw.text((70, y), "Direction: correct" if ok else "Direction: wrong", font=_font(64 if story else 54),
                  fill=GREEN if ok else RED)
        if evaluation.get("accuracy_pct") is not None:
            draw.text((70, y + 84), f"Accuracy {evaluation['accuracy_pct']}%", font=_font(44), fill=TEXT)
    else:
        change = (prices[-1] - start_price) / start_price * 100 if prices and start_price else None
        label = ("Up" if rising else "Down") + (f"  {change:+.1f}%" if change is not None else "")
        draw.text((70, y), label, font=_font(72 if story else 60), fill=GREEN if rising else RED)
        draw.text((70, y + 90), "Checked automatically when the horizon ends", font=_font(34), fill=AMBER)
    if story:
        draw.text((70, h - 300), "Think you know better? Beat the AI.", font=_font(44), fill=TEXT)
    draw.text((70, h - (170 if story else 90)), "aicryptopredictor.netlify.app", font=_font(38), fill=CYAN)
    draw.text((70, h - (120 if story else 50)), "Not financial advice", font=_font(28), fill=MUTED)
    return _png(img)
