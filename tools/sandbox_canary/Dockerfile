# The GitHub Actions workflow builds a self-authored, static Go canary locally.
# No upstream image, package manager, network access, or Skill content is used.
FROM scratch
COPY --chmod=0555 canary /canary
USER 65532:65532
ENTRYPOINT ["/canary"]
ARG CANARY_SOURCE_SHA
LABEL org.gasl.inert-canary="v1" \
      org.gasl.canary-source-sha256="${CANARY_SOURCE_SHA}"
