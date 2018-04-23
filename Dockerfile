FROM centos/python-36-centos7

WORKDIR /tmp
COPY ./plugin_controller/requirements.txt .
RUN pip install -r requirements.txt

WORKDIR /opt/app-root/src/plugin_interpreter
COPY ./plugin_interpreter .

WORKDIR /opt/app-root/src/plugin_controller
COPY ./plugin_controller .

USER root

CMD ["python3", "server.py"]