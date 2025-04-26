FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
    wget \
    apt-transport-https \
    curl \
    gnupg \
    libzmq3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install .NET SDK
RUN wget https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb \
    && dpkg -i packages-microsoft-prod.deb \
    && rm packages-microsoft-prod.deb \
    && apt-get update \
    && apt-get -y install --no-install-recommends dotnet-sdk-7.0 \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get update \
    && apt-get -y install --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Install Python packages
RUN pip install --no-cache-dir jupyter notebook ipykernel matplotlib numpy pandas

# Add PATH for dotnet tools
ENV PATH="$PATH:/root/.dotnet/tools"

# Install IJavaScript
RUN npm install -g ijavascript tslab \
    && ijsinstall --install=global \
    && tslab install

# Set default shell
SHELL ["/bin/bash", "-c"]