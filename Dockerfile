FROM python:3-alpine

RUN mkdir /opt/lorad
WORKDIR /opt/lorad

COPY . .
RUN apk add ffmpeg && pip install poetry
RUN poetry build
RUN pip install dist/*.whl

ENTRYPOINT [ "./lorad_main.py" ]