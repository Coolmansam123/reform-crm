"""Field-rep mobile page renderers. Previously lived in hub/mobile.py."""

from .admin import _mobile_admin_page
from .home import _mobile_home_page, _mobile_routes_dashboard_page
from .outreach import _mobile_outreach_due_page, _mobile_outreach_map_page
from .company import _mobile_company_detail_page, _mobile_directory_page
from .events import _mobile_events_page
from .lead import _mobile_lead_capture_page, _mobile_log_page
from .route import _mobile_route_page
from .recent import _mobile_recent_page
from .map import _mobile_map_page

__all__ = [
    "_mobile_admin_page",
    "_mobile_home_page",
    "_mobile_routes_dashboard_page",
    "_mobile_outreach_due_page",
    "_mobile_outreach_map_page",
    "_mobile_company_detail_page",
    "_mobile_directory_page",
    "_mobile_events_page",
    "_mobile_lead_capture_page",
    "_mobile_log_page",
    "_mobile_route_page",
    "_mobile_recent_page",
    "_mobile_map_page",
]
