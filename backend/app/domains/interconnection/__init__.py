"""DER interconnection review: screens, circuit data, application packets."""

import enum

DOMAIN = "interconnection"


class DocumentKind(enum.StrEnum):
    APPLICATION_FORM = "application_form"
    ONE_LINE_DIAGRAM = "one_line_diagram"
    SITE_PLAN = "site_plan"
    INVERTER_SPEC_SHEET = "inverter_spec_sheet"
    BATTERY_SPEC_SHEET = "battery_spec_sheet"
    CUSTOMER_AUTHORIZATION = "customer_authorization"
    OTHER = "other"
