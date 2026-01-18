from core.models import NormalizedProduct, make_field
from core.utils.merge import merge_products


def test_merge_precedence_overrides() -> None:
    primary = NormalizedProduct()
    primary.coupon_rate_pct_pa = make_field(1.0, 0.4, "leonteq_html")

    secondary = NormalizedProduct()
    secondary.coupon_rate_pct_pa = make_field(2.0, 0.7, "pdf")

    merged = merge_products(primary, secondary, prefer_secondary_fields={"coupon_rate_pct_pa"})
    assert merged.coupon_rate_pct_pa.value == 2.0
    assert merged.audit_trail
