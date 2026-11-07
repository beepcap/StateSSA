#!/usr/bin/env bash
# ==============================================================================
# StateSSA Architecture Guide - Chapter 4
# Automated QEMU Isolation Sandbox Builder & Runner
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="/tmp/statessa_qemu_sandbox"
BUILD_DIR="${SCRIPT_DIR}/build"
ROOTFS_DIR="${WORK_DIR}/rootfs"
INITRD_PATH="${WORK_DIR}/initramfs.cpio.gz"
COMPILER_BIN="${SCRIPT_DIR}/../../../bin/ssac"

echo "======================================================================"
echo " StateSSA Secure Web Server: QEMU Isolation Sandbox"
echo "======================================================================"

# 1. ビルド検証
if [[ ! -f "${SCRIPT_DIR}/bin_web_server_static" ]]; then
    echo "[1/4] Building static StateSSA Web Server binary..."
    mkdir -p "${BUILD_DIR}"
    "${COMPILER_BIN}" "${SCRIPT_DIR}/main.ssa" -o "${BUILD_DIR}/web_server.ll"
    clang -O2 -static "${BUILD_DIR}/web_server.ll" -o "${SCRIPT_DIR}/bin_web_server_static"
fi
echo "[1/4] Web Server binary ready: ${SCRIPT_DIR}/bin_web_server_static"

# 2. カーネル探索
KERNEL_PATH=""
CANDIDATES=(
    "/boot/vmlinuz-$(uname -r)"
    /boot/vmlinuz-*
)
for k in "${CANDIDATES[@]}"; do
    if [[ -f "${k}" && -r "${k}" ]]; then
        KERNEL_PATH="${k}"
        break
    fi
done

if [[ -z "${KERNEL_PATH}" ]]; then
    echo "ERROR: No readable Linux kernel image found in /boot." >&2
    exit 1
fi
echo "[2/4] Using kernel image: ${KERNEL_PATH}"

# 3. 最小オンメモリ rootfs の構築
echo "[3/4] Assembling minimal rootfs (Zero-Allocation Sandbox)..."
rm -rf "${WORK_DIR}"
mkdir -p "${ROOTFS_DIR}"/{bin,sbin,dev,proc,sys,etc,tmp,var/secret,var/www/html/public,modules}

# BusyBox
BUSYBOX_BIN="$(which busybox 2>/dev/null || true)"
if [[ -z "${BUSYBOX_BIN}" ]]; then
    echo "ERROR: busybox not found on host. Please install busybox (e.g. apt install busybox-static)." >&2
    exit 1
fi
cp "${BUSYBOX_BIN}" "${ROOTFS_DIR}/bin/busybox"
chmod +x "${ROOTFS_DIR}/bin/busybox"
for applet in sh ls cat ifconfig route insmod rm ps mount umount basename; do
    ln -sf busybox "${ROOTFS_DIR}/bin/${applet}"
done

# サーバーバイナリ
cp "${SCRIPT_DIR}/bin_web_server_static" "${ROOTFS_DIR}/bin_web_server_static"
chmod +x "${ROOTFS_DIR}/bin_web_server_static"

# 静的コンテンツ
if [[ -d "${SCRIPT_DIR}/public" ]]; then
    cp -r "${SCRIPT_DIR}/public"/* "${ROOTFS_DIR}/var/www/html/public/"
fi

# 秘匿ファイル (CTF 検証ターゲット)
echo "FLAG{StateSSA_FSM_Zero_Leak_Direct_Kernel_Defense_2026}" > "${ROOTFS_DIR}/var/secret/himitu.txt"
chmod 400 "${ROOTFS_DIR}/var/secret/himitu.txt"

# ネットワークドライバモジュール (e1000, virtio_net 等)
KVER="$(uname -r)"
MOD_BASE="/lib/modules/${KVER}/kernel/drivers/net"
for mod in \
    "${MOD_BASE}/ethernet/intel/e1000/e1000.ko"* \
    "${MOD_BASE}/virtio_net.ko"* \
    "${MOD_BASE}/net_failover.ko"* \
    "${MOD_BASE}/failover.ko"*; do
    if [[ -f "${mod}" ]]; then
        cp "${mod}" "${ROOTFS_DIR}/modules/" 2>/dev/null || true
    fi
done

# /init スクリプト生成
cat << 'EOF' > "${ROOTFS_DIR}/init"
#!/bin/sh
mount -t proc none /proc
mount -t sysfs none /sys
mount -t devtmpfs none /dev

# ネットワークドライバ組込み
for m in /modules/*.ko /modules/*.ko.xz /modules/*.ko.zst; do
    if [ -f "$m" ]; then
        insmod "$m" 2>/dev/null || true
    fi
done

ifconfig lo 127.0.0.1 up
ifconfig eth0 10.0.2.15 netmask 255.255.255.0 up 2>/dev/null || true
route add default gw 10.0.2.2 2>/dev/null || true

echo "=== StateSSA Secure Web Server Sandbox Ready ==="
echo "Listening on 0.0.0.0:18080 (Forwarded to Host 127.0.0.1:18080)"
cd /var/www/html
exec /bin_web_server_static
EOF
chmod +x "${ROOTFS_DIR}/init"

# 4. initramfs.cpio.gz パック
(cd "${ROOTFS_DIR}" && find . -print0 | cpio --null -ov -H newc 2>/dev/null | gzip -1 > "${INITRD_PATH}")
echo "[4/4] initramfs assembled ($(du -h "${INITRD_PATH}" | cut -f1))"

echo "======================================================================"
echo " Booting QEMU sandbox. Press Ctrl-C or Ctrl-A X to terminate."
echo " Test via: curl -i http://127.0.0.1:18080/ または python3 verify_traversal.py"
echo "======================================================================"

exec qemu-system-x86_64 \
    -m 256M \
    -kernel "${KERNEL_PATH}" \
    -initrd "${INITRD_PATH}" \
    -append "console=ttyS0 quiet panic=-1" \
    -nographic \
    -serial mon:stdio \
    -device e1000,netdev=net0 \
    -netdev user,id=net0,hostfwd=tcp:127.0.0.1:18080-:18080
