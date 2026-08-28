"""
"Clinical Symptoms" page -> output/clinical-symptoms.html.

Builds from Processed_Sensitive_Data clinical_symptoms artifacts when present;
falls back to the shared chrome stub ("Coming soon") otherwise.
"""

from __future__ import annotations

from common.chrome import STUB_VIEWS, _render_nav, render_page
from clinical.render_clinical import build_clinical_html, load_clinical_bundle

VIEW_ID = "clinical-symptoms"


def _chrome_payload(payload: dict) -> dict:
    i18n = payload.get("i18n") or {}
    return {
        "i18n": i18n,
        "partners": payload.get("partners") or [],
        "methods_html": payload.get("methods_html") or "",
        "terms_html": payload.get("terms_html") or "",
        "terms_updated": payload.get("terms_updated") or "",
    }


def build_page(payload: dict) -> str:
    try:
        data, fits, clin_dir = load_clinical_bundle()
        print(f"  clinical-symptoms: using {clin_dir}")
        return build_clinical_html(
            nav_links=_render_nav(VIEW_ID, "assets/"),
            assets_prefix="assets/",
            data=data,
            fits=fits,
            chrome_payload=_chrome_payload(payload),
        )
    except FileNotFoundError as exc:
        print(f"  WARNING: clinical artifacts missing ({exc}); stub page")
        from common import chrome as chrome_mod
        prev = set(chrome_mod.STUB_VIEWS)
        chrome_mod.STUB_VIEWS = prev | {VIEW_ID}
        try:
            return render_page(VIEW_ID, payload)
        finally:
            chrome_mod.STUB_VIEWS = prev
