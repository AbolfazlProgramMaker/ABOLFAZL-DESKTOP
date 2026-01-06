#!/bin/bash
set -euo pipefail

# --------------------------------------------------
# Ensure sudo access
# --------------------------------------------------
echo "Checking sudo access..."
if ! sudo -v; then
    echo "You need sudo access to run this script."
    exit 1
fi

# Keep sudo session alive
( while true; do sudo -v; sleep 60; done ) &
SUDO_LOOP_PID=$!

# --------------------------------------------------
# System dependencies
# --------------------------------------------------
echo "Installing system dependencies..."
export DEBIAN_FRONTEND=noninteractive
sudo apt update -y
sudo apt install -y \
    git curl wget build-essential \
    libssl-dev zlib1g-dev libbz2-dev \
    libreadline-dev libsqlite3-dev llvm libncursesw5-dev xz-utils tk-dev \
    libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev \
    gobject-introspection libgirepository1.0-dev \
    libglib2.0-dev libcairo2-dev pkg-config cmake \
    libwnck-3-dev python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.0

# --------------------------------------------------
# Install pyenv (if missing)
# --------------------------------------------------
if [ ! -d "$HOME/.pyenv" ]; then
    echo "Installing pyenv..."
    curl https://pyenv.run | bash

    # Add pyenv to bashrc
    {
        echo 'export PYENV_ROOT="$HOME/.pyenv"'
        echo 'export PATH="$PYENV_ROOT/bin:$PATH"'
        echo 'eval "$(pyenv init --path)"'
        echo 'eval "$(pyenv init -)"'
    } >> ~/.bashrc
fi

# Load pyenv for current session
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"

# --------------------------------------------------
# Install Python 3.12 if missing
# --------------------------------------------------
PYTHON_VERSION="3.12.2"
if ! pyenv versions --bare | grep -q "^$PYTHON_VERSION\$"; then
    echo "Installing Python $PYTHON_VERSION (may take a while)..."
    pyenv install "$PYTHON_VERSION"
fi
pyenv global "$PYTHON_VERSION"

# Upgrade pip & libraries
python -m pip install --upgrade pip setuptools wheel
python -m pip install --user PyGObject

# --------------------------------------------------
# Clone or update project
# --------------------------------------------------
PROJECT_DIR="ABOLFAZL-DESKTOP"
REPO_URL="https://github.com/AbolfazlGameMaker/Golden-Moon-Desktop.git"

if [ -d "$PROJECT_DIR" ]; then
    echo "Directory $PROJECT_DIR exists. Pulling latest changes..."
    cd "$PROJECT_DIR"
    git fetch --all
    git reset --hard origin/main
    cd ..
else
    echo "Cloning ABOLFAZL-DESKTOP..."
    git clone "$REPO_URL" "$PROJECT_DIR"
fi

# --------------------------------------------------
# Create .desktop file
# --------------------------------------------------
DESKTOP_FILE="/usr/share/xsessions/abolfazl.desktop"
ABS_PROJECT_PATH="$(realpath "$PROJECT_DIR/main.py")"

if [ ! -f "$DESKTOP_FILE" ]; then
    echo "Creating .desktop file for login manager..."
    sudo tee "$DESKTOP_FILE" > /dev/null <<EOL
[Desktop Entry]
Name=ABOLFAZL-DESKTOP
Comment=Custom Python GTK Desktop Shell
Exec=python3 $ABS_PROJECT_PATH
Type=Application
X-GNOME-SingleWindow=true
EOL
fi

# --------------------------------------------------
# Finish
# --------------------------------------------------
echo "------------------------------------------------"
echo "Installation complete!"
echo "Python: $(python --version)"
echo "To run manually: cd $PROJECT_DIR && python3 main.py"
echo "Select 'ABOLFAZL-DESKTOP' from login screen after logout."
echo "------------------------------------------------"

# Kill sudo keep-alive loop
kill $SUDO_LOOP_PID

echo "Done."
