FROM mcr.microsoft.com/devcontainers/base:ubuntu

# Install Python
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install python3 python3-pip python3-dev

# Install .NET SDK
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install wget apt-transport-https \
    && wget https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get -y install dotnet-sdk-7.0

# Install Node.js
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install curl \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get -y install nodejs

# Install additional Python packages
RUN pip3 install jupyter notebook ipykernel matplotlib numpy pandas

# Add PATH for dotnet tools
ENV PATH="$PATH:/root/.dotnet/tools"

# --- IJavaScript Installation ---
# Install dependencies for IJavaScript
RUN apt-get update && apt-get install -y libzmq3-dev --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Install IJavaScript (Note: May have issues on ARM64)
# Ensure Node.js/npm is installed before this step
RUN npm install -g ijavascript \
    && ijsinstall --install=global
# --- End IJavaScript Installation ---