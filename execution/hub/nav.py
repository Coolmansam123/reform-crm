"""
Top nav + mobile drawer rendering for the Reform Operations Hub.
`_topnav(active, user)` returns the full `<nav>` block including the hamburger drawer.
"""

from .access import _is_admin, _get_allowed_hubs


# ─── Top Nav ───────────────────────────────────────────────────────────────────
def _topnav(active: str, user: dict = None) -> str:
    user = user or {}
    GROUP_MAP = {
        'attorney': 'outreach', 'gorilla': 'outreach', 'community': 'outreach',
        'attorney_map': 'outreach', 'gorilla_map': 'outreach', 'community_map': 'outreach',
        'route_planner': 'outreach', 'outreach_list': 'outreach',
        'outreach_contacts': 'outreach',
        'attorney_dir': 'outreach', 'gorilla_dir': 'outreach', 'community_dir': 'outreach',
        'gorilla_log': 'outreach', 'gorilla_events_int': 'outreach', 'gorilla_events_ext': 'outreach',
        'gorilla_businesses': 'outreach', 'gorilla_boxes': 'outreach', 'gorilla_routes': 'outreach',
        'leads_by_event': 'outreach', 'leads': 'leads', 'lead': 'leads',
        'patients': 'pi_cases', 'patients_active': 'pi_cases', 'patients_billed': 'pi_cases',
        'patients_awaiting': 'pi_cases', 'patients_closed': 'pi_cases', 'firms': 'pi_cases',
        'billing_collections': 'billing', 'billing_settlements': 'billing',
        'contacts': 'communications', 'communications_email': 'communications',
        'people': 'communications',
        'social': 'social', 'social_history': 'social', 'social_inbox': 'social',
        'calendar': 'calendar',
        'tickets':   'tickets',
        'tasks':     'tasks',
        'inbox':     'inbox',
        'sequences': 'sequences',
        'reports':   'reports',
    }
    top_group = GROUP_MAP.get(active, '')

    def nav_btn(gid, label, href=None, has_drop=False):
        cls = ' active' if gid == top_group or active == gid else ''
        caret = ' \u25be' if has_drop else ''
        if href:
            return f'<a href="{href}" class="tnav-btn{cls}">{label}{caret}</a>'
        return f'<button class="tnav-btn{cls}">{label}{caret}</button>'

    def drop_link(k, label, href):
        cls = ' active' if k == active else ''
        return f'<a href="{href}" class="{cls}">{label}</a>'

    def grp_link(k, label, href):
        cls = ' active' if k == active else ''
        return f'<a href="{href}" class="tnav-grp-lbl{cls}">{label}</a>'

    hubs = _get_allowed_hubs(user)
    admin = _is_admin(user)

    # ── Outreach dropdown: hubs (bold) visible to all, sub-items admin-only ──
    outreach_parts = []
    # Hub links (bold) — visible to anyone with access
    hub_links = ''
    if 'community' in hubs:
        hub_links += grp_link('community', 'Community', '/community')
    if 'attorney' in hubs:
        hub_links += grp_link('attorney', 'PI Attorney', '/attorney')
    if 'guerilla' in hubs:
        hub_links += grp_link('gorilla', 'Guerilla Mktg', '/guerilla')
        if admin:
            hub_links += drop_link('gorilla_events_int', 'Internal Events', '/guerilla/events/internal')
            hub_links += drop_link('leads_by_event', 'Leads by Event', '/leads/by-event')
    if admin:
        hub_links += drop_link('outreach_list', 'Outreach Directory', '/outreach/list')
    if hub_links:
        outreach_parts.append(hub_links)

    # Routes section — below separator
    route_links = ''
    if 'guerilla' in hubs or admin:
        route_links += grp_link('gorilla_routes', 'Routes', '/guerilla/routes')
    if admin:
        route_links += drop_link('route_planner', 'Route Planner', '/outreach/planner')
    if route_links:
        outreach_parts.append(route_links)

    outreach_drop = ('<div class="tnav-sep"></div>').join(outreach_parts)

    pi_drop = (
        drop_link('patients',          'All Patients',     '/patients')
        + drop_link('patients_active',   'Active Treatment', '/patients/active')
        + drop_link('patients_billed',   'Billed',           '/patients/billed')
        + drop_link('patients_awaiting', 'Awaiting',         '/patients/awaiting')
        + drop_link('patients_closed',   'Closed',           '/patients/closed')
        + '<div class="tnav-sep"></div>'
        + drop_link('firms', 'Law Firm ROI', '/firms')
    )

    billing_drop = (
        drop_link('billing_collections', 'Collections', '/billing/collections')
        + drop_link('billing_settlements', 'Settlements', '/billing/settlements')
    )

    comms_drop = (
        drop_link('communications_email', 'Email',     '/communications/email')
        + drop_link('contacts',           'Companies', '/contacts')
        + drop_link('people',             'People',    '/people')
    )

    social_drop = (
        drop_link('social_inbox',   'Inbox',    '/social/inbox')
        + drop_link('social',       'Monitor',  '/social')
        + drop_link('social_history','History', '/social/history')
    )

    def menu(gid, label, drop_html):
        cls = ' active' if gid == top_group else ''
        return (
            f'<div class="tnav-menu">'
            f'<button class="tnav-btn{cls}">{label} \u25be</button>'
            f'<div class="tnav-drop">{drop_html}</div>'
            f'</div>'
        )

    user_name = user.get('name', '')

    # Drawer links for hamburger menu (filtered by role + allowed hubs)
    drawer_links = f'<a href="/" class="{"active" if active == "hub" else ""}">Dashboard</a>'
    # Hub links (bold)
    if 'community' in hubs:
        community_cls = ' active' if active == 'community' else ''
        drawer_links += f'<a href="/community" class="tnav-grp-lbl{community_cls}">Community</a>'
    if 'attorney' in hubs:
        attorney_cls = ' active' if active == 'attorney' else ''
        drawer_links += f'<a href="/attorney" class="tnav-grp-lbl{attorney_cls}">PI Attorney</a>'
    if 'guerilla' in hubs:
        guerilla_cls = ' active' if active == 'gorilla' else ''
        drawer_links += f'<a href="/guerilla" class="tnav-grp-lbl{guerilla_cls}">Guerilla Mktg</a>'
        if admin:
            drawer_links += '<a href="/guerilla/events/internal">Internal Events</a>'
            drawer_links += '<a href="/leads/by-event">Leads by Event</a>'
    if admin:
        drawer_links += '<a href="/outreach/list">Outreach Directory</a>'
    # Routes section
    drawer_links += '<div class="tnav-sep"></div>'
    if 'guerilla' in hubs or admin:
        routes_cls = ' active' if active == 'gorilla_routes' else ''
        drawer_links += f'<a href="/guerilla/routes" class="tnav-grp-lbl{routes_cls}">Routes</a>'
    if admin:
        drawer_links += '<a href="/outreach/planner">Route Planner</a>'
    if admin and 'pi_cases' in hubs:
        drawer_links += (
            '<div class="tnav-sep"></div>'
            '<div class="tnav-grp-lbl">PI Cases</div>'
            '<a href="/patients">All Patients</a>'
            '<a href="/firms">Law Firm ROI</a>'
        )
    if admin and 'billing' in hubs:
        drawer_links += (
            '<div class="tnav-sep"></div>'
            '<a href="/billing/collections">Collections</a>'
            '<a href="/billing/settlements">Settlements</a>'
        )
    if admin and 'communications' in hubs:
        drawer_links += '<a href="/communications/email">Email</a><a href="/contacts">Companies</a><a href="/people">People</a>'
    if admin and 'social' in hubs:
        drawer_links += '<a href="/social/inbox">Social Inbox</a><a href="/social">Social Monitor</a>'
    if 'calendar' in hubs:
        drawer_links += '<a href="/calendar">Calendar</a>'
    if 'inbox' in hubs:
        inbox_cls = ' active' if active == 'inbox' else ''
        drawer_links += f'<a href="/inbox" class="tnav-grp-lbl{inbox_cls}">Inbox</a>'
    if 'leads' in hubs:
        leads_cls = ' active' if active in ('leads', 'lead') else ''
        drawer_links += f'<a href="/leads" class="tnav-grp-lbl{leads_cls}">Leads</a>'
    if 'tasks' in hubs:
        tasks_cls = ' active' if active == 'tasks' else ''
        drawer_links += f'<a href="/tasks" class="tnav-grp-lbl{tasks_cls}">Tasks</a>'
    if 'sequences' in hubs:
        seq_cls = ' active' if active == 'sequences' else ''
        drawer_links += f'<a href="/sequences" class="tnav-grp-lbl{seq_cls}">Automations</a>'
    if 'tickets' in hubs:
        tickets_cls = ' active' if active == 'tickets' else ''
        drawer_links += f'<a href="/tickets" class="tnav-grp-lbl{tickets_cls}">Tickets</a>'
    if admin:
        drawer_links += '<a href="/reports">Reports</a>'
    drawer_links += (
        '<div class="tnav-sep"></div>'
        f'<a href="/settings" class="{"active" if active == "settings" else ""}">\u2699\ufe0f Settings</a>'
        '<a href="/logout" style="color:var(--text3)">Sign Out</a>'
    )

    drawer_html = (
        '<div class="tnav-drawer-backdrop" id="drawer-backdrop" onclick="closeDrawer()"></div>'
        '<div class="tnav-drawer" id="drawer-nav">'
        '<div class="tnav-drawer-hdr">'
        '<span class="tnav-logo">\u2726 Reform</span>'
        '<button class="tnav-drawer-close" onclick="closeDrawer()">\u2715</button>'
        '</div>'
        + drawer_links
        + '</div>'
    )

    has_outreach = any(h in hubs for h in ('attorney', 'guerilla', 'community'))

    nav_items = nav_btn('hub', 'Dashboard', href='/')
    if has_outreach:
        nav_items += menu('outreach', 'Outreach', outreach_drop)
    if admin and 'pi_cases' in hubs:
        nav_items += menu('pi_cases', 'PI Cases', pi_drop)
    if admin and 'billing' in hubs:
        nav_items += menu('billing', 'Billing', billing_drop)
    if admin and 'communications' in hubs:
        nav_items += menu('communications', 'Comms', comms_drop)
    if admin and 'social' in hubs:
        nav_items += menu('social', 'Social', social_drop)
    if 'calendar' in hubs:
        nav_items += nav_btn('calendar', 'Calendar', href='/calendar')
    if 'inbox' in hubs:
        nav_items += nav_btn('inbox', 'Inbox', href='/inbox')
    if 'leads' in hubs:
        nav_items += nav_btn('leads', 'Leads', href='/leads')
    if 'tasks' in hubs:
        nav_items += nav_btn('tasks', 'Tasks', href='/tasks')
    if 'sequences' in hubs:
        nav_items += nav_btn('sequences', 'Automations', href='/sequences')
    if 'tickets' in hubs:
        nav_items += nav_btn('tickets', 'Tickets', href='/tickets')

    settings_active = ' active' if active == 'settings' else ''
    return (
        '<nav class="tnav">'
        '<a href="/" class="tnav-logo">\u2726 Reform <span>Operations Hub</span></a>'
        '<div class="tnav-items">'
        + nav_items
        + '</div>'
        '<div class="tnav-right">'
        '<button class="tnav-theme-btn" id="theme-btn" onclick="toggleTheme()"><span id="theme-icon">\U0001f319</span></button>'
        + (f'<span class="tnav-user">{user_name}</span>' if user_name else '')
        + f'<a href="/settings" class="tnav-settings{settings_active}" title="Settings" aria-label="Settings">\u2699\ufe0f</a>'
        + '<a href="/logout" class="tnav-signout">Sign Out</a>'
        '</div>'
        '<button class="tnav-hamburger" onclick="openDrawer()">\u2630</button>'
        '</nav>'
        + drawer_html
    )
