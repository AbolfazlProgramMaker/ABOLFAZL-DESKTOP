#!/bin/bash

# Exit on error globally
set -e

echo "Updating package lists... This part will be skipped if it doesn't work for 100s"

# Disable exit-on-error for this block
set +e
if ! timeout 100s sudo apt update; then
    echo "apt update took too long, skipping..."
fi
set -e  # re-enable exit-on-error

echo "Installing Git and dependencies..."
sudo apt install -y git software-properties-common build-essential \
  gobject-introspection libgirepository-2.0-dev libglib2.0-dev \
  libcairo2-dev pkg-config cmake wget curl

# Install Python 3.12
echo "Adding deadsnakes PPA for Python 3.12..."
sudo add-apt-repository -y ppa:deadsnakes/ppa
echo "Updating package lists for repo change... This part will be skipped if it doesn't work for 100s"

# Disable exit-on-error for this block
set +e
if ! timeout 100s sudo apt update; then
    echo "failed to load update deadsnake repo. skipping...."
fi
set -e  # re-enable exit-on-error
sudo apt install -y python3.12 python3.12-venv python3.12-dev python3-pip

# Make python3.12 the default python3 (optional)
echo "Updating alternatives for python3..."
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.12 2
sudo update-alternatives --config python3

# Upgrade pip
echo "Updating pip to latest version..."
python3 -m pip install --upgrade pip

# Install PyGObject
echo "Installing PyGObject..."
python3 -m pip install PyGObject

echo "Done! Git, Python 3.12, and PyGObject are installed."