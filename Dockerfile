FROM ghcr.io/prefix-dev/pixi:0.49.0 AS build

WORKDIR /app
COPY pixi.toml pixi.toml
COPY pixi.lock pixi.lock
RUN apt-get update && apt-get install -y build-essential
RUN pixi install --locked -e default

FROM gcr.io/distroless/base-debian12 AS production
WORKDIR /app
COPY --from=build /app/.pixi/envs/default /app/.pixi/envs/default
COPY ./addon.py /app/addon.py
COPY ./webapp.py /app/webapp.py
COPY ./utils.py /app/utils.py
COPY ./manager.py /app/manager.py
COPY ./supervisord.conf /app/supervisord.conf
COPY ./asset /app/asset
EXPOSE 8000
ENV PATH=/app/.pixi/envs/default/bin:$PATH
ENV CONDA_PREFIX=/app/.pixi/envs/default
CMD [ "python", "webapp.py"]
