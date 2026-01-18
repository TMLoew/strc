from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field as PydField

from core.models.fields import Field


class CouponScheduleItem(BaseModel):
    date: Field[str] = Field()
    amount: Field[float] = Field()
    currency: Field[str] = Field()


class Underlying(BaseModel):
    name: Field[str] = Field()
    isin: Field[str] = Field()
    bloomberg_ticker: Field[str] = Field()
    exchange: Field[str] = Field()
    reference_currency: Field[str] = Field()
    initial_level: Field[float] = Field()
    strike_level: Field[float] = Field()
    strike_pct_of_initial: Field[float] = Field()
    barrier_level: Field[float] = Field()
    barrier_pct_of_initial: Field[float] = Field()


class NormalizedProduct(BaseModel):
    id: Optional[str] = None

    source_file_name: Field[str] = Field()
    source_file_hash_sha256: Field[str] = Field()
    document_language: Field[str] = Field()
    document_timestamp: Field[str] = Field()
    document_type: Field[str] = Field()
    parse_version: Field[str] = Field()
    parse_confidence: Field[float] = Field()

    issuer_name: Field[str] = Field()
    issuer_rating: Field[str] = Field()
    issuer_regulator: Field[str] = Field()
    calculation_agent: Field[str] = Field()
    paying_agent: Field[str] = Field()
    lead_manager: Field[str] = Field()
    governing_law: Field[str] = Field()
    jurisdiction: Field[str] = Field()
    risk_disclosure_flags: Field[dict[str, bool]] = Field()

    product_name: Field[str] = Field()
    product_type: Field[str] = Field()
    sspa_category: Field[str] = Field()
    valor_number: Field[str] = Field()
    isin: Field[str] = Field()
    ticker_six: Field[str] = Field()
    listing_venue: Field[str] = Field()

    currency: Field[str] = Field()
    quanto: Field[bool] = Field()
    fx_risk_flag: Field[bool] = Field()
    issue_price_pct: Field[float] = Field()
    denomination: Field[float] = Field()
    min_investment: Field[float] = Field()
    trade_unit: Field[float] = Field()
    ter_pct: Field[float] = Field()
    iev_pct: Field[float] = Field()
    distribution_fee_pct: Field[float] = Field()
    market_expectation: Field[str] = Field()
    yield_to_maturity_pct_pa: Field[float] = Field()
    worst_to_yield_pct_pa: Field[float] = Field()

    coupon_rate_pct_pa: Field[float] = Field()
    coupon_frequency: Field[str] = Field()
    coupon_is_guaranteed: Field[bool] = Field()
    coupon_schedule: list[CouponScheduleItem] = PydField(default_factory=list)
    tax_coupon_split: Field[dict[str, float]] = Field()
    interest_component_pct_pa: Field[float] = Field()
    premium_component_pct_pa: Field[float] = Field()

    subscription_start: Field[str] = Field()
    subscription_end: Field[str] = Field()
    initial_fixing_date: Field[str] = Field()
    settlement_date: Field[str] = Field()
    final_fixing_date: Field[str] = Field()
    maturity_date: Field[str] = Field()
    redemption_date: Field[str] = Field()
    last_trading_day: Field[str] = Field()

    underlyings: list[Underlying] = PydField(default_factory=list)

    barrier_type: Field[str] = Field()
    barrier_observation_start: Field[str] = Field()
    barrier_observation_end: Field[str] = Field()
    barrier_trigger_condition: Field[str] = Field()
    worst_of: Field[bool] = Field()
    worst_of_definition: Field[str] = Field()

    cap_level_pct: Field[float] = Field()
    participation_rate_pct: Field[float] = Field()

    is_callable: Field[bool] = Field()
    call_style: Field[str] = Field()
    call_first_possible_after: Field[str] = Field()
    call_observation_dates: list[Field[str]] = PydField(default_factory=list)
    call_settlement_dates: list[Field[str]] = PydField(default_factory=list)
    call_redemption_amount_rule: Field[str] = Field()

    settlement_type: Field[str] = Field()
    redemption_rules: Field[dict[str, str]] = Field()
    physical_delivery: Field[dict[str, str]] = Field()
    payoff_summary_text: Field[str] = Field()

    secondary_market_intent: Field[str] = Field()
    pricing_convention: Field[str] = Field()
    custodian_depository: Field[str] = Field()
    clearing_settlement: Field[str] = Field()

    swiss_tax_classification: Field[str] = Field()
    withholding_tax_interest_component: Field[bool] = Field()
    stamp_duty_secondary_market: Field[bool] = Field()
    selling_restrictions: list[Field[str]] = PydField(default_factory=list)
    tax_notes_snippet: Field[str] = Field()

    capital_protection: Field[bool] = Field()
    max_loss_description: Field[str] = Field()
    issuer_credit_risk: Field[bool] = Field()
    liquidity_risk_flag: Field[bool] = Field()
    risk_summary: Field[str] = Field()

    audit_trail: list[dict[str, str]] = PydField(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)
