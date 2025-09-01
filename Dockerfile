FROM debian:bookworm-slim AS base

FROM base AS s6-arch-arm64
ARG S6_ARCH=aarch64

FROM base AS s6-arch-amd64
ARG S6_ARCH=x86_64

FROM s6-arch-${TARGETARCH} AS final

ENV S6_OVERLAY_VERSION="3.2.0.3"

RUN apt-get update && apt-get install -y xz-utils

ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-noarch.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-noarch.tar.xz
ADD https://github.com/just-containers/s6-overlay/releases/download/v${S6_OVERLAY_VERSION}/s6-overlay-${S6_ARCH}.tar.xz /tmp
RUN tar -C / -Jxpf /tmp/s6-overlay-${S6_ARCH}.tar.xz

RUN mkdir -p /etc/s6-overlay/s6-rc.d/setup && \
    echo 'oneshot' > /etc/s6-overlay/s6-rc.d/setup/type && \
    touch /etc/s6-overlay/s6-rc.d/user/contents.d/setup;

RUN for service in cron clamd rspamd postfix python; do \
      mkdir -p /etc/s6-overlay/s6-rc.d/$service && \
      echo 'longrun' > /etc/s6-overlay/s6-rc.d/$service/type && \
      touch /etc/s6-overlay/s6-rc.d/user/contents.d/$service && \
      echo 'setup' > /etc/s6-overlay/s6-rc.d/$service/dependencies; \
    done

RUN echo '/command/with-contenv /opt/x-ray/setup.sh' \
    > /etc/s6-overlay/s6-rc.d/setup/up && chmod +x /etc/s6-overlay/s6-rc.d/setup/up

# cron
RUN echo '#!/command/execlineb -P\nexec cron -f' \
    > /etc/s6-overlay/s6-rc.d/cron/run && chmod +x /etc/s6-overlay/s6-rc.d/cron/run

# clamd
RUN echo '#!/command/execlineb -P\nexec /usr/sbin/clamd --foreground' \
    > /etc/s6-overlay/s6-rc.d/clamd/run && chmod +x /etc/s6-overlay/s6-rc.d/clamd/run

# rspamd
RUN echo '#!/command/execlineb -P\nexec /usr/bin/rspamd --no-fork --user=rspamd --group=rspamd' \
    > /etc/s6-overlay/s6-rc.d/rspamd/run && chmod +x /etc/s6-overlay/s6-rc.d/rspamd/run

# postfix
RUN echo '#!/command/execlineb -P\nexec /usr/sbin/postfix start-fg' \
    > /etc/s6-overlay/s6-rc.d/postfix/run && chmod +x /etc/s6-overlay/s6-rc.d/postfix/run

# x-ray
RUN echo '#!/command/execlineb -P\nwith-contenv /opt/x-ray/venv/bin/python /opt/x-ray/x-ray.py' \
    > /etc/s6-overlay/s6-rc.d/python/run && chmod +x /etc/s6-overlay/s6-rc.d/python/run

RUN rm -rf /etc/cron.*/*

WORKDIR /opt/x-ray

COPY . .

RUN chmod +x setup.sh x-ray.py cli.py
ENV APP_DIR=/opt/x-ray
RUN bash -c "source /opt/x-ray/setup.sh && install_packages && setup_python_env && create_users"

ENTRYPOINT ["/init"]