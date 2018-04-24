FROM alpine:3.7
  
RUN apk add --no-cach python3 && \
    python3 -m ensurepip && \
    rm -r /usr/lib/python*/ensurepip && \
    pip3 install --upgrade pip setuptools && \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi && \
    if [[ ! -e /usr/bin/python ]]; then ln -sf /usr/bin/python3 /usr/bin/python; fi && \
    rm -r /root/.cache

WORKDIR /tmp
COPY ./plugin_controller/requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /opt/app-root/src/plugin_interpreter
COPY ./plugin_interpreter .

WORKDIR /opt/app-root/src/plugin_controller
COPY ./plugin_controller .

USER root

CMD ["python3", "server.py"]
