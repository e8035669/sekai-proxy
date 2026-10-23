#!/bin/sh
set -e

MITM_PORT=8085

# Redirect HTTP/HTTPS from tailnet clients (exit-node traffic) into mitmproxy transparent mode.
for port in 80 443; do
  iptables -t nat -C PREROUTING -i tailscale0 -p tcp --dport "$port" -j REDIRECT --to-ports "$MITM_PORT" 2>/dev/null ||
    iptables -t nat -A PREROUTING -i tailscale0 -p tcp --dport "$port" -j REDIRECT --to-ports "$MITM_PORT"
done

# Drop QUIC/HTTP3 so clients fall back to TCP, which can be intercepted.
iptables -C FORWARD -i tailscale0 -p udp --dport 443 -j REJECT 2>/dev/null ||
  iptables -I FORWARD -i tailscale0 -p udp --dport 443 -j REJECT

# The container has no IPv6 egress; reject so clients fall back to IPv4 immediately.
ip6tables -C FORWARD -i tailscale0 -j REJECT 2>/dev/null ||
  ip6tables -I FORWARD -i tailscale0 -j REJECT 2>/dev/null || true

exec /usr/local/bin/containerboot
