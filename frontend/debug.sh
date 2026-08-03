#!/bin/bash

echo "=== Operator 360 Debug Information ==="
echo "Date: $(date)"
echo "Container ID: $(hostname)"
echo

echo "=== Nginx Version ==="
nginx -v
echo

echo "=== Nginx Configuration Test ==="
nginx -t
echo

echo "=== Directory Structure ==="
echo "Web root contents:"
ls -la /usr/share/nginx/html/
echo

echo "=== Nginx Config Files ==="
echo "Main nginx.conf:"
ls -la /etc/nginx/nginx.conf
echo
echo "Site configs:"
ls -la /etc/nginx/conf.d/
echo

echo "=== File Permissions ==="
echo "Web root permissions:"
ls -la /usr/share/nginx/
echo
echo "Config permissions:"
ls -la /etc/nginx/
echo

echo "=== Process Information ==="
ps aux
echo

echo "=== Network Information ==="
netstat -tulpn 2>/dev/null || ss -tulpn
echo

echo "=== Disk Space ==="
df -h
echo

echo "=== Log Files ==="
echo "Error log:"
test -f /var/log/nginx/error.log && tail -n 20 /var/log/nginx/error.log || echo "No error log found"
echo
echo "Access log:"
test -f /var/log/nginx/access.log && tail -n 20 /var/log/nginx/access.log || echo "No access log found"

echo "=== End Debug Information ==="