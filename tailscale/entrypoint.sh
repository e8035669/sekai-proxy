#!/bin/sh
set -e

MITM_PORT=8085

# The image defaults to iptables-legacy; hosts running nftables (e.g. Raspberry Pi OS) lack the legacy nat table.
IPT=iptables
IP6T=ip6tables
if ! iptables -t nat -S >/dev/null 2>&1 && command -v iptables-nft >/dev/null; then
  IPT=iptables-nft
  IP6T=ip6tables-nft
fi
echo "entrypoint: using $IPT"

# Redirect HTTP/HTTPS from tailnet clients (exit-node traffic) into mitmproxy transparent mode.
for port in 80 443; do
  $IPT -t nat -C PREROUTING -i tailscale0 -p tcp --dport "$port" -j REDIRECT --to-ports "$MITM_PORT" 2>/dev/null ||
    $IPT -t nat -A PREROUTING -i tailscale0 -p tcp --dport "$port" -j REDIRECT --to-ports "$MITM_PORT"
done

# Drop QUIC/HTTP3 so clients fall back to TCP, which can be intercepted.
$IPT -C FORWARD -i tailscale0 -p udp --dport 443 -j REJECT 2>/dev/null ||
  $IPT -I FORWARD -i tailscale0 -p udp --dport 443 -j REJECT

# The container has no IPv6 egress; reject so clients fall back to IPv4 immediately.
$IP6T -C FORWARD -i tailscale0 -j REJECT 2>/dev/null ||
  $IP6T -I FORWARD -i tailscale0 -j REJECT 2>/dev/null || true

exec /usr/local/bin/containerboot
