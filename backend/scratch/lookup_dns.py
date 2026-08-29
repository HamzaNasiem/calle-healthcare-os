import socket

hosts = [
    "aabbhuzlzjkosqmvhysm.supabase.co",
    "db.aabbhuzlzjkosqmvhysm.supabase.co"
]

for host in hosts:
    print(f"\nResolving {host}:")
    try:
        # Resolve both IPv4 (AF_INET) and IPv6 (AF_INET6)
        results = socket.getaddrinfo(host, None)
        ips = set()
        for res in results:
            family = res[0]
            family_str = "IPv4" if family == socket.AF_INET else "IPv6" if family == socket.AF_INET6 else str(family)
            ip = res[4][0]
            ips.add((family_str, ip))
        for family_str, ip in sorted(ips):
            print(f"  {family_str}: {ip}")
    except Exception as e:
        print(f"  Error: {e}")
