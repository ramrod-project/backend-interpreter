FROM centos/python-36-centos7

# Build arguments, stage=PROD or DEV
ARG stage=DEV
ARG plugin

WORKDIR /tmp
COPY ./requirements.txt .

RUN pip install -r requirements.txt

WORKDIR /opt/app-root/src
COPY . .

ENV STAGE $stage
ENV PLUGIN $plugin

ENTRYPOINT python3 server.py "${PLUGIN}"