#!/data/data/com.termux/files/usr/bin/bash
set -e

export PREFIX=/data/data/com.termux/files/usr
export PATH=$PREFIX/bin:$PATH
export HOME=/data/data/com.termux/files/home
export TMPDIR=$PREFIX/tmp
export LANG=en_US.UTF-8

echo "nameserver 8.8.8.8" > $PREFIX/etc/resolv.conf
echo "nameserver 8.8.4.4" >> $PREFIX/etc/resolv.conf

if [ -f "$PREFIX/etc/apt/sources.list" ]; then
  sed -i 's|https://packages.termux.dev/apt/termux-main|https://mirrors.ustc.edu.cn/termux/apt/termux-main|g' "$PREFIX/etc/apt/sources.list"
  sed -i 's|https://packages-cf.termux.dev/apt/termux-main|https://mirrors.ustc.edu.cn/termux/apt/termux-main|g' "$PREFIX/etc/apt/sources.list"
fi

apt update -yq && apt upgrade -yq
apt install -yq tur-repo && apt update -yq
apt install -yq pythonAPP_PY_VER

PY_BIN=$(ls $PREFIX/bin/python3.* 2>/dev/null | grep -v config | head -1)
[ -z "$PY_BIN" ] && { echo "error: python3 not found"; exit 1; }
PY_SFX=$(basename "$PY_BIN" | sed 's/python//')
ln -sf "$PY_BIN" $PREFIX/bin/python
[ -f "$PREFIX/bin/pip${PY_SFX}" ] && ln -sf "$PREFIX/bin/pip${PY_SFX}" $PREFIX/bin/pip
python --version

apt install -yq ninja clang git patchelf ccache termux-elf-cleaner findutils
pip install --upgrade pip
pip install MarkupSafe==2.1.3 ordered-set==4.1.0 zstandard==0.23.0 nuitka==NUITKA_VER

cd /src/apps/APP_NAME/src
python -m nuitka --module APP_NAME --include-package=APP_NAME \
  --nofollow-imports --output-dir=dist --remove-output \
  --assume-yes-for-downloads --no-progressbar

cp ./dist/*.so /src/dist/ 2>/dev/null || true
cd /src/dist/
SO_FILE=$(ls APP_NAME.*.so 2>/dev/null | head -1)
[ -z "$SO_FILE" ] && { echo "error: No .so produced"; exit 1; }
mv "$SO_FILE" APP_NAME.so
termux-elf-cleaner APP_NAME.so || true
patchelf --set-rpath '' APP_NAME.so || true
patchelf --replace-needed libpython${PY_SFX}.so.1.0 libpython${PY_SFX}.so APP_NAME.so || true
