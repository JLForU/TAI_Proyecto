"""PBT del parser Nmap XML (NFR-U4-MNT-03, P12, BR-U4-20).

Propiedades:
- (a) XML bien formado ⇒ hosts/puertos/estados/servicios extraídos;
- (b) normalización idempotente (parse y merge repetidos);
- (c) basura / atributos hostiles ⇒ ``ScannerError`` controlado (nunca
  excepción cruda del parser);
- (d) el merge por host conserva el método preponderante.
"""

from __future__ import annotations

from xml.sax.saxutils import quoteattr

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from sentinel.discovery.domain import HostFinding, merge_findings
from sentinel.discovery.scanner import ScannerError, parse_nmap_xml
from sentinel.foundation.models import PortInfo

_SAFE = st.characters(blacklist_categories=("Cc", "Cs"))

_IPS = st.sampled_from(["10.0.0.1", "192.168.1.10", "172.16.0.9", "192.168.1.11"])
_MACS = st.sampled_from(["aa:bb:cc:dd:ee:0a", "11:22:33:44:55:66", None])
_PORTS = st.integers(min_value=1, max_value=65535)
_SERVICES = st.sampled_from(["ssh", "http", "https", "mysql", None])
_VERSIONS = st.sampled_from(["9.0", "1.1.1", None])
_STATES = st.sampled_from(["up", "down"])
_PORT_STATES = st.sampled_from(["open", "closed", "filtered"])
_PROTOCOLS = st.sampled_from(["tcp", "udp"])
_SAFE_TEXT = st.text(alphabet=_SAFE, max_size=24)
_SETTINGS = settings(
    max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)


@st.composite
def nmap_docs(draw: st.DrawFn) -> tuple[str, dict[str, dict]]:  # type: ignore[type-arg]
    """Documento nmap bien formado + expectativas por IP."""
    count = draw(st.integers(min_value=1, max_value=4))
    ips = draw(st.lists(_IPS, min_size=count, max_size=count, unique=True))
    expectations: dict[str, dict] = {}
    hosts_xml: list[str] = []
    for ip in ips:
        status = draw(_STATES)
        mac = draw(_MACS)
        hostname = draw(st.one_of(st.none(), _SAFE_TEXT))
        ports = draw(
            st.lists(
                st.tuples(_PORTS, _PORT_STATES, _PROTOCOLS, _SERVICES, _VERSIONS),
                max_size=3,
                unique=True,
            )
        )
        expectations[ip] = {"status": status, "ports": ports, "mac": mac, "hostname": hostname}
        mac_xml = f"<address addr={quoteattr(mac)} addrtype='mac'/>" if mac is not None else ""
        host_xml = (
            f"<host><status state={quoteattr(status)}/>"
            f"<address addr={quoteattr(ip)} addrtype='ipv4'/>{mac_xml}"
        )
        if hostname is not None:
            host_xml += f"<hostnames><hostname name={quoteattr(hostname)}/></hostnames>"
        host_xml += "<ports>"
        for port, pstate, proto, service, version in ports:
            host_xml += (
                f"<port protocol={quoteattr(proto)} portid={quoteattr(str(port))}>"
                f"<state state={quoteattr(pstate)}/>"
            )
            if service is not None or version is not None:
                attrs = []
                if service is not None:
                    attrs.append(f"name={quoteattr(service)}")
                if version is not None:
                    attrs.append(f"version={quoteattr(version)}")
                host_xml += f"<service {' '.join(attrs)}/>"
            host_xml += "</port>"
        host_xml += "</ports></host>"
        hosts_xml.append(host_xml)
    xml = f'<?xml version="1.0"?>\n<nmaprun>{"".join(hosts_xml)}</nmaprun>'
    return xml, expectations


# --- (a) XML bien formado ⇒ hosts/puertos/servicios -------------------------


@given(nmap_docs())
@_SETTINGS
def test_property_valid_xml_extracts_hosts_and_ports(doc: tuple[str, dict]) -> None:
    xml, expectations = doc
    findings = parse_nmap_xml(xml)
    parsed = {f.ip: f for f in findings}
    expected_up = {ip for ip, spec in expectations.items() if spec["status"] == "up"}
    assert set(parsed) == expected_up
    for ip, spec in expectations.items():
        if spec["status"] != "up":
            continue
        finding = parsed[ip]
        assert finding.method == "nmap"
        open_ports = [
            (port, service, version)
            for port, pstate, _proto, service, version in spec["ports"]
            if pstate == "open" and 1 <= port <= 65535
        ]
        got = [(p.port, p.service, p.version) for p in finding.ports]
        assert got == open_ports
        if spec["mac"] is None:
            assert finding.mac is None
        else:
            assert finding.mac == spec["mac"]
        if spec["hostname"] is None:
            assert finding.hostname is None
        else:
            assert finding.hostname == spec["hostname"]


# --- (b) normalización idempotente ------------------------------------------


@given(nmap_docs())
@_SETTINGS
def test_property_parse_is_idempotent(doc: tuple[str, dict]) -> None:
    xml, _expectations = doc
    first = parse_nmap_xml(xml)
    second = parse_nmap_xml(xml)
    assert first == second
    merged_once = merge_findings(first)
    merged_twice = merge_findings(merged_once)
    assert merged_once == merged_twice


# --- (c) basura ⇒ ScannerError controlado -----------------------------------


@given(st.text(max_size=200))
@_SETTINGS
def test_property_garbage_never_raises_raw_exception(text: str) -> None:
    try:
        result = parse_nmap_xml(text)
    except ScannerError:
        return
    except Exception as exc:  # noqa: BLE001 - la propiedad es "nunca cruda"
        raise AssertionError(f"raw exception leaked: {type(exc).__name__}: {exc}") from exc
    assert isinstance(result, list)


@given(
    st.text(max_size=40),
    st.text(max_size=40),
    st.text(max_size=400),
    st.integers(min_value=0, max_value=10),
)
@_SETTINGS
def test_property_hostile_attributes_are_controlled(
    bad_portid: str, bad_protocol: str, long_service: str, weird_num: int
) -> None:
    """IP/MAC/puerto/protocolos hostiles ⇒ descarte/recorte, nunca crash."""
    xml = (
        '<?xml version="1.0"?>\n<nmaprun><host><status state="up"/>'
        f"<address addr={quoteattr(f'10.0.0.{weird_num % 255 + 1}')} addrtype='ipv4'/>"
        f"<address addr={quoteattr(bad_portid)} addrtype='mac'/>"
        f"<hostnames><hostname name={quoteattr(bad_portid * 3)}/></hostnames>"
        "<ports>"
        f"<port protocol={quoteattr(bad_protocol)} portid={quoteattr(bad_portid)}>"
        f"<state state='open'/><service name={quoteattr(long_service)}/></port>"
        f"<port protocol='tcp' portid='99999'><state state='open'/></port>"
        "</ports></host></nmaprun>"
    )
    try:
        findings = parse_nmap_xml(xml)
    except ScannerError:
        return
    except Exception as exc:  # noqa: BLE001
        raise AssertionError(f"raw exception leaked: {type(exc).__name__}: {exc}") from exc
    for finding in findings:
        assert finding.mac is None or len(finding.mac) == 17
        assert finding.hostname is None or len(finding.hostname) <= 255
        for port in finding.ports:
            assert 1 <= port.port <= 65535
            assert port.protocol in {"tcp", "udp", "icmp", "arp", "other"}
            assert port.service is None or len(port.service) <= 255


# --- (d) merge por host ⇒ método preponderante -------------------------------

_PRECEDENCE = {"arp": 0, "icmp": 1, "tcp": 2, "nmap": 3}


@given(
    st.lists(
        st.tuples(
            st.sampled_from(["arp", "icmp", "tcp", "nmap"]),
            st.lists(st.integers(min_value=1, max_value=65535), max_size=3, unique=True),
        ),
        min_size=1,
        max_size=4,
    )
)
@_SETTINGS
def test_property_merge_preponderance(cases: list[tuple[str, list[int]]]) -> None:
    findings = [
        HostFinding(
            ip="10.0.0.7",
            method=method,  # type: ignore[arg-type]
            ports=[PortInfo(port=p, state="open", confidence="probable") for p in ports],
        )
        for method, ports in cases
    ]
    merged = merge_findings(findings)
    assert len(merged) == 1
    best = max((method for method, _ports in cases), key=_PRECEDENCE.__getitem__)
    assert merged[0].method == best
    expected_ports = sorted({p for _m, ports in cases for p in ports})
    assert sorted(p.port for p in merged[0].ports) == expected_ports
