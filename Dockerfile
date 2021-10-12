FROM alpine as ejson
ARG TARGETPLATFORM
RUN wget -O /ejson "https://github.com/Shopify/ejson/releases/download/v1.3.0/${TARGETPLATFORM/\//-}" \
    && chmod +x /ejson


FROM python:3.9
LABEL author="benjamincaldwell"

COPY --from=ejson /ejson /usr/bin/ejson

ENV PYTHONFAULTHANDLER=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=random \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100

# System deps:
RUN pip install poetry

# Copy only requirements to cache them in docker layer
WORKDIR /code
COPY poetry.lock pyproject.toml /code/

# Project initialization:
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

COPY . /code/

# USER app
CMD ["python", "-u", "app.py"]
