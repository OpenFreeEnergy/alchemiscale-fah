FROM mambaorg/micromamba:1.5.8

LABEL org.opencontainers.image.source=https://github.com/openforcefield/alchemiscale-fah
LABEL org.opencontainers.image.description="deployable service(s) for using Folding@Home via alchemiscale"
LABEL org.opencontainers.image.licenses=MIT

# Don't buffer stdout & stderr streams, so if there is a crash no partial buffer output is lost
# https://docs.python.org/3/using/cmdline.html#cmdoption-u
ENV PYTHONUNBUFFERED=1

COPY --chown=$MAMBA_USER:$MAMBA_USER devtools/conda-envs/alchemiscale-fah-compute.yml /tmp/env.yaml
COPY --chown=$MAMBA_USER:$MAMBA_USER alchemiscale_fah /tmp/alchemiscale_fah
COPY --chown=$MAMBA_USER:$MAMBA_USER LICENSE README.md pyproject.toml /tmp/
RUN micromamba install -y -n base git -f /tmp/env.yaml && \
    micromamba clean --all --yes

# Ensure that conda environment is automatically activated
# https://github.com/mamba-org/micromamba-docker#running-commands-in-dockerfile-within-the-conda-environment
ARG MAMBA_DOCKERFILE_ACTIVATE=1
RUN python -m pip install --no-deps -e .

WORKDIR /home/mambauser

ENTRYPOINT ["/usr/local/bin/_entrypoint.sh", "/opt/conda/bin/alchemiscale-fah"]
