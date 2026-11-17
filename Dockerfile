# Start from a slim Python image; the motion script is pure Python.
FROM --platform=linux/amd64 python:3.12-slim-bookworm@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

ENV FLYWHEEL=/flywheel/v0

# Create Flywheel directory
WORKDIR ${FLYWHEEL}
RUN mkdir -p ${FLYWHEEL}

RUN pip3 install "fw-gear[sdk]" pydicom numpy && \
    rm -rf /root/.cache/pip

COPY run.py parse_vNav_Motion.py manifest.json ${FLYWHEEL}/
RUN chmod -R 777 ${FLYWHEEL}

ENTRYPOINT ["python3", "/flywheel/v0/run.py"]
