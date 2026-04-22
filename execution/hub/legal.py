"""
Public Terms of Service and Privacy Policy pages.

Required so third-party developer portals (TikTok, Meta, etc.) can link to
a functioning ToS + Privacy URL during app registration. Content is scoped
narrowly to what Reform's social integrations actually do — post videos to
our own accounts and read engagement metrics on our own posts.

Both pages are public (no auth) and share the same minimal prose styling.
"""

EFFECTIVE_DATE = "April 22, 2026"
CONTACT_EMAIL = "techops@reformchiropractic.com"


_SHARED_STYLE = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#fafafa;color:#1e293b;line-height:1.7;padding:40px 20px}
.doc{max-width:760px;margin:0 auto;background:#fff;padding:48px 56px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.04)}
.doc-brand{font-size:12px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:#ea580c;margin-bottom:8px}
.doc h1{font-size:28px;font-weight:700;color:#0f172a;margin-bottom:6px;line-height:1.2}
.doc-date{font-size:13px;color:#64748b;margin-bottom:32px}
.doc h2{font-size:18px;font-weight:700;color:#0f172a;margin-top:28px;margin-bottom:10px}
.doc p{font-size:15px;color:#334155;margin-bottom:14px}
.doc ul{padding-left:22px;margin-bottom:14px}
.doc li{font-size:15px;color:#334155;margin-bottom:6px}
.doc a{color:#ea580c;text-decoration:none}
.doc a:hover{text-decoration:underline}
.doc-footer{margin-top:40px;padding-top:20px;border-top:1px solid #e2e8f0;font-size:13px;color:#94a3b8;text-align:center}
@media (max-width:560px){.doc{padding:32px 24px}.doc h1{font-size:24px}}
"""


def _shell(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html><html lang="en">
<head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Reform Chiropractic</title>
<style>{_SHARED_STYLE}</style></head>
<body>
<div class="doc">
{body_html}
<div class="doc-footer">Reform Chiropractic &middot; reformchiropractic.com &middot; <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a></div>
</div>
</body></html>"""


def _terms_page() -> str:
    body = f"""
<div class="doc-brand">Reform Chiropractic</div>
<h1>Terms of Service</h1>
<div class="doc-date">Effective {EFFECTIVE_DATE}</div>

<p>These Terms of Service govern the use of Reform Chiropractic's internal
social media management application (the "App"), operated by Reform
Chiropractic ("Reform", "we", "our"). By using the App, authorized users
agree to these terms.</p>

<h2>1. Purpose of the App</h2>
<p>The App is an internal operations tool used exclusively by Reform
Chiropractic staff to manage Reform's own social media presence across
platforms including TikTok, Instagram, and Facebook. The App is not a
consumer-facing product and is not made available to the general public.</p>

<h2>2. Authorized Use</h2>
<p>Use of the App is restricted to current Reform Chiropractic staff who have
been granted access by Reform. Unauthorized access, sharing of credentials,
or use of the App outside the scope of official Reform work is prohibited.</p>

<h2>3. Acceptable Use</h2>
<ul>
  <li>The App may be used only to manage social media accounts owned and
      operated by Reform Chiropractic.</li>
  <li>The App must not be used to harass, impersonate, or collect data about
      any third-party social media user.</li>
  <li>All use must comply with the terms of service of the underlying
      platforms (TikTok, Meta, etc.).</li>
</ul>

<h2>4. No Warranties</h2>
<p>The App is provided "as is" and "as available". Reform makes no warranties,
express or implied, regarding uptime, accuracy of reported metrics, or fitness
for any particular purpose.</p>

<h2>5. Limitation of Liability</h2>
<p>To the fullest extent permitted by law, Reform is not liable for any
indirect, incidental, or consequential damages arising from use of the App.</p>

<h2>6. Changes to These Terms</h2>
<p>Reform may update these Terms at any time. Continued use of the App after
changes are posted constitutes acceptance of the updated Terms. The effective
date at the top of this page indicates when the Terms were last revised.</p>

<h2>7. Contact</h2>
<p>Questions about these Terms can be directed to
<a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
"""
    return _shell("Terms of Service", body)


def _privacy_page() -> str:
    body = f"""
<div class="doc-brand">Reform Chiropractic</div>
<h1>Privacy Policy</h1>
<div class="doc-date">Effective {EFFECTIVE_DATE}</div>

<p>This Privacy Policy describes how Reform Chiropractic ("Reform", "we",
"our") handles data collected through its internal social media management
application (the "App"). The App is used exclusively by Reform staff to
manage Reform's own social media presence.</p>

<h2>1. Information We Collect</h2>
<p>The App connects to social media platforms (TikTok, Instagram, Facebook)
using OAuth credentials belonging to Reform Chiropractic's own accounts.
From those platforms, the App reads the following data limited to Reform's
own account activity:</p>
<ul>
  <li><strong>Account profile data</strong> for the connected Reform account:
      display name, avatar, follower counts, and account statistics.</li>
  <li><strong>Video metadata</strong> for videos posted by Reform's own
      accounts: title, description, cover image URL, creation time, and
      share URL.</li>
  <li><strong>Engagement metrics</strong> on videos posted by Reform's own
      accounts: view count, like count, comment count, and share count.</li>
</ul>

<h2>2. Information We Do Not Collect</h2>
<ul>
  <li>The App does not collect data from any social media user other than
      Reform Chiropractic's own authenticated accounts.</li>
  <li>The App does not read, store, or process private messages or direct
      messages.</li>
  <li>The App does not collect personal data from viewers, followers, or
      commenters on Reform's posts.</li>
</ul>

<h2>3. How We Use the Information</h2>
<p>Collected data is used solely for internal operations: surfacing
engagement trends in a private staff dashboard to inform content planning
and posting schedules. The data is not used for advertising, profiling, or
any purpose beyond internal operations.</p>

<h2>4. Storage and Security</h2>
<p>Data is stored in Reform's private database. Access is restricted to
authorized Reform Chiropractic staff. OAuth access tokens and refresh
tokens are stored in encrypted secret stores and are never exposed in the
App's user interface.</p>

<h2>5. Sharing with Third Parties</h2>
<p>Reform does not sell, trade, or share data collected through the App with
third parties. Data remains within Reform's internal systems.</p>

<h2>6. Data Retention</h2>
<p>Engagement metrics and video metadata are retained indefinitely as
internal operational records. OAuth credentials are retained for as long as
the App's connection to the corresponding social media account remains
active and are revoked immediately if access is no longer required.</p>

<h2>7. Platform Compliance</h2>
<p>The App uses the TikTok API, Meta Graph API, and similar platform APIs
solely in the manner described above. The App's use of data obtained from
these APIs complies with each platform's Developer Terms of Service.</p>

<h2>8. Your Rights</h2>
<p>If you believe the App may be processing data about you and would like to
request information or deletion, please contact us at
<a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>. We will respond
within a reasonable timeframe.</p>

<h2>9. Changes to This Policy</h2>
<p>Reform may update this Privacy Policy at any time. The effective date at
the top of this page indicates when the Policy was last revised.</p>

<h2>10. Contact</h2>
<p>Questions about this Privacy Policy can be directed to
<a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>.</p>
"""
    return _shell("Privacy Policy", body)
