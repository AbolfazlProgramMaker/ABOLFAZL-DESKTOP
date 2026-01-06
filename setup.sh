#!/bin/bash
set -euo pipefail

# --------------------------------------------------
# Trap to ensure sudo loop is killed on exit
# --------------------------------------------------
trap 'echo "🛑 Exiting... Killing sudo keep-alive loop"; kill $SUDO_LOOP_PID 2>/dev/null || true' EXIT

# --------------------------------------------------
# Ensure sudo access
# --------------------------------------------------
echo "🔐 Checking sudo access..."
if ! sudo -v; then
    echo "❌ You need sudo access to run this script."
    exit 1
fi

# Keep sudo session alive
( while true; do sudo -v; sleep 60; done ) &
SUDO_LOOP_PID=$!

# --------------------------------------------------
# System dependencies
# --------------------------------------------------
echo "📦 Installing system dependencies..."
export DEBIAN_FRONTEND=noninteractive
sudo apt update -y

# Essential packages
packages=(
    git curl wget build-essential python3 python3-pip
    libssl-dev libbz2-dev libreadline-dev libsqlite3-dev
    libffi-dev liblzma-dev python3-gi python3-gi-cairo
    gir1.2-gtk-3.0 gir1.2-webkit2-4.0
)

# Install missing packages only
for pkg in "${packages[@]}"; do
    if ! dpkg -s "$pkg" &>/dev/null; then
        echo "⬇️ Installing $pkg..."
        sudo apt install -y "$pkg"
    else
        echo "✅ $pkg already installed."
    fi
done

# Upgrade pip & PyGObject system-wide
echo "⬆️ Upgrading pip, setuptools, wheel & PyGObject..."
sudo python3 -m pip install --upgrade pip setuptools wheel PyGObject

# --------------------------------------------------
# Clone or update project
# --------------------------------------------------
PROJECT_DIR="$HOME/ABOLFAZL-DESKTOP"
REPO_URL="https://github.com/AbolfazlProgramMaker/ABOLFAZL-DESKTOP.git"

if [ -d "$PROJECT_DIR" ]; then
    echo "🔄 Project exists. Pulling latest changes..."
    cd "$PROJECT_DIR"
    git fetch --all --quiet
    git reset --hard origin/main --quiet
else
    echo "📥 Cloning ABOLFAZL-DESKTOP..."
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# Ensure desktop.py is executable
chmod +x desktop.py

# --------------------------------------------------
# Create .desktop file for login manager
# --------------------------------------------------
DESKTOP_FILE="/usr/share/xsessions/abolfazl.desktop"
ABS_PROJECT_PATH="$(realpath "$PROJECT_DIR/desktop.py")"

if [ ! -f "$DESKTOP_FILE" ]; then
    echo "🖥️ Creating system-wide .desktop file..."
    sudo tee "$DESKTOP_FILE" > /dev/null <<EOL
[Desktop Entry]
Name=ABOLFAZL Desktop
Comment=Custom Python GTK Desktop Environment
Exec=python3 $ABS_PROJECT_PATH
Type=Application
X-GNOME-SingleWindow=true
Icon=$PROJECT_DIR/start.png
EOL
else
    echo "✅ System-wide .desktop file already exists."
fi

# --------------------------------------------------
# Create user Applications Menu launcher
# --------------------------------------------------
echo "📌 Creating user Applications menu launcher..."
mkdir -p "$HOME/.local/share/applications"
USER_DESKTOP="$HOME/.local/share/applications/ABOLFAZL-Desktop.desktop"

cat > "$USER_DESKTOP" <<EOL
[Desktop Entry]
Name=ABOLFAZL Desktop
Comment=Custom Python GTK Desktop Environment
Exec=python3 $ABS_PROJECT_PATH
Type=Application
Terminal=false
Icon=$PROJECT_DIR/start.png
Categories=Utility;
EOL

# Ensure permissions
chmod +x "$USER_DESKTOP"

# --------------------------------------------------
# Finish
# --------------------------------------------------
echo "------------------------------------------------"
echo "🎉 Installation complete!"
echo "Python: $(python3 --version)"
echo "You can log out and select 'ABOLFAZL Desktop' from login screen,"
echo "or run manually: cd $PROJECT_DIR && python3 desktop.py"
echo "------------------------------------------------"
