"""Minimal SOAP client for the Microsoft Advertising (Bing Ads) v13 API.

The Bing Ads API is SOAP, so this builds the envelope (auth header + body) and
POSTs it, then parses the response **defensively** with namespace-stripped
xml.etree (the API's namespaces are verbose and version-specific). Graceful
{ok: False, reason} when not connected or on any error — never raises.

Scoped to Campaign Management v13. Performance metrics are NOT here — those need
the async Reporting service (submit→poll→download), deliberately out of scope.
"""

from __future__ import annotations

import logging
from xml.sax.saxutils import escape

from .oauth import access_token, is_connected
from .settings import raw_config

logger = logging.getLogger('morpheus.microsoft_commerce')

CAMPAIGN_MGMT_URL = (
    'https://campaign.api.bingads.microsoft.com/Api/Advertiser/CampaignManagement/v13/'
    'CampaignManagementService.svc'
)
_NS = 'https://bingads.microsoft.com/CampaignManagement/v13'


def ads_creds() -> dict:
    cfg = raw_config()
    return {
        'developer_token': (cfg.get('developer_token') or '').strip(),
        'customer_id': (cfg.get('customer_id') or '').strip(),
        'account_id': (cfg.get('account_id') or '').strip(),
    }


def ads_connected() -> bool:
    c = ads_creds()
    return bool(is_connected() and c['developer_token'] and c['account_id'])


def _strip_ns(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def call(action: str, body_inner_xml: str) -> dict:
    """POST a Campaign Management SOAP action. body_inner_xml is the inner XML of
    the <{action}Request> element. Returns {ok, root} (namespace-stripped
    ElementTree) or {ok: False, reason}."""
    if not ads_connected():
        return {'ok': False, 'reason': 'not_connected'}
    token = access_token()
    if not token:
        return {'ok': False, 'reason': 'no_access_token'}
    c = ads_creds()

    envelope = (
        '<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">'
        f'<s:Header xmlns="{_NS}">'
        f'<Action mustUnderstand="1">{action}</Action>'
        f'<AuthenticationToken>{escape(token)}</AuthenticationToken>'
        f'<CustomerAccountId>{escape(c["account_id"])}</CustomerAccountId>'
        f'<CustomerId>{escape(c["customer_id"])}</CustomerId>'
        f'<DeveloperToken>{escape(c["developer_token"])}</DeveloperToken>'
        '</s:Header><s:Body>'
        f'<{action}Request xmlns="{_NS}" '
        'xmlns:i="http://www.w3.org/2001/XMLSchema-instance">'
        f'{body_inner_xml}'
        f'</{action}Request>'
        '</s:Body></s:Envelope>'
    )
    headers = {'Content-Type': 'application/soap+xml; charset=utf-8'}
    try:
        import requests  # noqa: PLC0415

        resp = requests.post(
            CAMPAIGN_MGMT_URL, data=envelope.encode('utf-8'), headers=headers, timeout=30
        )
        resp.raise_for_status()
        from xml.etree import ElementTree as ET  # noqa: PLC0415

        # The body is a SOAP response from a fixed, authenticated Microsoft HTTPS
        # endpoint (campaign.api.bingads.microsoft.com) — not untrusted user
        # input — so the XML-attack premise of S314 doesn't apply here.
        root = ET.fromstring(resp.content)  # noqa: S314
        # Surface a SOAP Fault as the error reason.
        for el in root.iter():
            if _strip_ns(el.tag) in ('faultstring', 'Text') and (el.text or '').strip():
                return {'ok': False, 'reason': el.text.strip()[:300]}
        return {'ok': True, 'root': root}
    except Exception as e:  # noqa: BLE001 — never raise into a view
        logger.warning('microsoft_commerce: SOAP %s failed: %s', action, e)
        return {'ok': False, 'reason': str(e)[:300]}


def findall_local(root, name: str):
    """All elements whose namespace-stripped tag == name."""
    return [el for el in root.iter() if _strip_ns(el.tag) == name]


def text_of(parent, name: str) -> str:
    for el in parent.iter():
        if _strip_ns(el.tag) == name:
            return (el.text or '').strip()
    return ''
