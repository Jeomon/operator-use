#!/bin/bash
# Google Workspace CLI Installation Script
# Installs gws (Google Workspace CLI) and verifies installation
# Supports: macOS, Linux, Windows (via Git Bash/WSL)

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Google Workspace CLI Installation ===${NC}\n"

# Check if already installed
if command -v gws &> /dev/null; then
    echo -e "${GREEN}gws is already installed.${NC}"
    gws --version
    echo ""
    read -p "Reinstall? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipping installation."
        exit 0
    fi
fi

# Detect OS and installation method
OS=$(uname -s)
INSTALL_METHOD=""

echo "Detecting system..."
echo -e "${BLUE}OS: $OS${NC}\n"

# Option 1: Homebrew (preferred for macOS/Linux)
if command -v brew &> /dev/null; then
    echo -e "${YELLOW}Homebrew detected. This is the recommended method.${NC}"
    echo "Installing @googleworkspace/cli via brew..."
    if brew install googleworkspace-cli; then
        echo -e "${GREEN}[OK] Installation successful via Homebrew${NC}"
        INSTALL_METHOD="homebrew"
    else
        echo -e "${RED}[FAILED] Homebrew installation failed. Trying npm...${NC}"
    fi
fi

# Option 2: npm fallback
if [ "$INSTALL_METHOD" != "homebrew" ]; then
    echo "Checking for Node.js..."
    if ! command -v node &> /dev/null; then
        echo -e "${RED}[ERROR] Node.js is required but not installed.${NC}"
        echo "Install from https://nodejs.org (18+) or use Homebrew:"
        echo "  brew install node"
        exit 1
    fi

    NODE_VERSION=$(node -v)
    echo -e "${GREEN}[OK] Node.js found: $NODE_VERSION${NC}"

    # Check npm
    if ! command -v npm &> /dev/null; then
        echo -e "${RED}[ERROR] npm is required but not installed.${NC}"
        exit 1
    fi

    NPM_VERSION=$(npm -v)
    echo -e "${GREEN}[OK] npm found: $NPM_VERSION${NC}\n"

    echo "Installing @googleworkspace/cli via npm..."
    if npm install -g @googleworkspace/cli; then
        echo -e "${GREEN}[OK] Installation successful via npm${NC}"
        INSTALL_METHOD="npm"
    else
        echo -e "${RED}[FAILED] npm installation failed.${NC}"
        echo "Try with sudo or use the pre-built binary:"
        echo "  https://github.com/googleworkspace/cli/releases"
        exit 1
    fi
fi

# Verify installation
echo ""
echo "Verifying installation..."
if command -v gws &> /dev/null; then
    GWS_VERSION=$(gws --version 2>/dev/null || echo "unknown version")
    echo -e "${GREEN}[OK] gws is ready${NC}"
    echo "Version: $GWS_VERSION\n"
else
    echo -e "${RED}[ERROR] gws command not found.${NC}"
    exit 1
fi

# Display next steps
echo -e "${GREEN}=== Installation Complete ===${NC}\n"
echo "Next steps:"
echo ""
echo "1. Authenticate with Google Workspace:"
echo -e "   ${YELLOW}gws auth setup${NC}    (one-time: creates Cloud project)"
echo -e "   ${YELLOW}gws auth login${NC}     (login and select scopes)"
echo ""
echo "2. Try a command:"
echo -e "   ${YELLOW}gws drive files list${NC}"
echo ""
echo "3. Get help:"
echo -e "   ${YELLOW}gws help${NC}"
echo ""
echo "Documentation: https://github.com/googleworkspace/cli"
echo "Installation method: $INSTALL_METHOD"
