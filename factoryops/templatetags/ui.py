"""Small presentation helpers shared by every template."""
import hashlib

from django import template
from django.utils.safestring import mark_safe

from ..icons import ICONS

register = template.Library()


@register.simple_tag
def icon(name, size=16, cls=""):
    body = ICONS.get(name, "")
    return mark_safe(
        f'<svg class="ic {cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" '
        f'aria-hidden="true">{body}</svg>'
    )


@register.simple_tag
def spark(values, color="#16D3A8"):
    """Tiny sparkline from a comma-separated list or a Python list."""
    if isinstance(values, str):
        pts = [float(v) for v in values.split(",") if v.strip()]
    else:
        pts = [float(v) for v in values]
    if len(pts) < 2:
        return ""
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1
    step = 100 / (len(pts) - 1)
    coords = " ".join(f"{i * step:.1f},{26 - ((v - lo) / span) * 21:.1f}" for i, v in enumerate(pts))
    area = f"0,26 {coords} 100,26"
    gid = "s" + hashlib.md5((coords + color).encode()).hexdigest()[:6]
    return mark_safe(
        f'<svg class="spark" viewBox="0 0 100 26" preserveAspectRatio="none" aria-hidden="true">'
        f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity=".28"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>'
        f'<polygon points="{area}" fill="url(#{gid})"/>'
        f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="1.7" '
        f'stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )


@register.simple_tag
def qr(seed, size=64, grid=21):
    """Deterministic QR-style matrix — decorative, scan-target look only."""
    h = hashlib.sha256(seed.encode()).digest()
    bits = []
    for i in range(grid * grid):
        bits.append((h[i % len(h)] >> (i % 8)) & 1)
    px = size / grid
    cells = []
    for y in range(grid):
        for x in range(grid):
            if bits[y * grid + x]:
                cells.append(f'<rect x="{x * px:.2f}" y="{y * px:.2f}" width="{px:.2f}" height="{px:.2f}"/>')
    finder = []
    for ox, oy in ((0, 0), (grid - 7, 0), (0, grid - 7)):
        finder.append(
            f'<rect x="{ox * px:.2f}" y="{oy * px:.2f}" width="{7 * px:.2f}" height="{7 * px:.2f}" fill="none" stroke="#0B1220" stroke-width="{px:.2f}"/>'
            f'<rect x="{(ox + 2) * px:.2f}" y="{(oy + 2) * px:.2f}" width="{3 * px:.2f}" height="{3 * px:.2f}" fill="#0B1220"/>'
        )
    return mark_safe(
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" role="img" aria-label="Sample QR code">'
        f'<rect width="{size}" height="{size}" fill="#fff"/>'
        f'<g fill="#0B1220">{"".join(cells)}</g>{"".join(finder)}</svg>'
    )


@register.simple_tag
def barcode(seed, width=240, height=44):
    h = hashlib.sha256(seed.encode()).digest()
    bars, x = [], 2
    i = 0
    while x < width - 4 and i < 60:
        w = 1 + (h[i % len(h)] % 3)
        if i % 2 == 0:
            bars.append(f'<rect x="{x}" y="0" width="{w}" height="{height - 9}" fill="#0B1220"/>')
        x += w + 1 + (h[(i + 3) % len(h)] % 2)
        i += 1
    return mark_safe(
        f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Barcode">'
        f'<rect width="{width}" height="{height}" fill="#fff"/>{"".join(bars)}</svg>'
    )


@register.filter
def get(d, key):
    if isinstance(d, dict):
        return d.get(key, "")
    return ""


@register.filter
def initials(name):
    return "".join(p[0] for p in str(name).replace(".", "").split() if p)[:2].upper()
