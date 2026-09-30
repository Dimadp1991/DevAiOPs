FROM zot.local/docker:27-dind

# Install Python, pip, git, and bash (bypassing missing internet repositories if using a local mirror, or standard apt)
RUN apk update && apk add --no-cache \
    python3 \
    py3-pip \
    git \
    bash \
    yaml-cpp \
    && rm -rf /var/cache/apk/*

# Install PyYAML via pip for your Python script steps
RUN pip3 install --no-cache-dir pyyaml --break-system-packages || pip3 install --no-cache-dir pyyaml

# Set default shell
SHELL ["/bin/bash", "-c"]