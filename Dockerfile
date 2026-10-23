FROM python:3.12-slim-bookworm

# fluidsynth (LGPL-2.1, used only as a subprocess) and ffmpeg (mp3 encode / decode / ebur128 cross-check)
RUN apt-get update \
 && apt-get install -y --no-install-recommends fluidsynth ffmpeg curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# FluidR3_GM SoundFont (MIT, Frank Wen), pinned Debian package + SHA-256 checks of the .deb and the .sf2
ARG SF_DEB_URL=http://deb.debian.org/debian/pool/main/f/fluid-soundfont/fluid-soundfont-gm_3.1-5.3_all.deb
ARG SF_DEB_SHA256=6f531493ac4e4d9772fd96b2488ea1790af81c196135fbdd25997da0781fc60e
ARG SF2_SHA256=74594e8f4250680adf590507a306655a299935343583256f3b722c48a1bc1cb0
RUN curl -fsSL "$SF_DEB_URL" -o /tmp/sf.deb \
 && echo "$SF_DEB_SHA256  /tmp/sf.deb" | sha256sum -c - \
 && dpkg-deb -x /tmp/sf.deb /tmp/sf \
 && mkdir -p /opt/soundfonts \
 && mv /tmp/sf/usr/share/sounds/sf2/FluidR3_GM.sf2 /opt/soundfonts/FluidR3_GM.sf2 \
 && echo "$SF2_SHA256  /opt/soundfonts/FluidR3_GM.sf2" | sha256sum -c - \
 && rm -rf /tmp/sf /tmp/sf.deb

RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[test]"
COPY . .
RUN mkdir -p /app/out && chown -R app /app/out
USER app

ENV PYTHONUNBUFFERED=1 SOUNDFONT_PATH=/opt/soundfonts/FluidR3_GM.sf2
EXPOSE 8000
CMD ["uvicorn", "musicengine.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
