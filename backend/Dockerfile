FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl gettext gosu \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 crm \
    && useradd --uid 10001 --gid crm --create-home --shell /usr/sbin/nologin crm

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY --chown=crm:crm . /app
COPY docker-entrypoint.sh /usr/local/bin/crm-entrypoint
RUN chmod 0755 /app/entrypoint.prod.sh /usr/local/bin/crm-entrypoint \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R crm:crm /app/media /app/staticfiles

ENTRYPOINT ["/usr/local/bin/crm-entrypoint"]

EXPOSE 8000
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
