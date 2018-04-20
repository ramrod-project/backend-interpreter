FROM centos/python-36-centos7

# Build arguments, stage=PROD or DEV
ARG stage=DEV

WORKDIR /opt/app-root/src

COPY . .

RUN pip install -r requirements.txt

ENV STAGE $stage

CMD ["python3", "server.py"]