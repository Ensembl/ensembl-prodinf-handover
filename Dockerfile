FROM python:3.10-alpine

RUN useradd --create-home appuser
USER appuser
RUN mkdir -p /home/appuser/handover
WORKDIR /home/appuser/handover
RUN chown appuser:appuser /home/appuser/handover

#copy handover app
COPY --chown=appuser:appuser . /home/appuser/handover

#Install dependencies
RUN python -m venv /home/appuser/handover/venv
ENV PATH="/home/appuser/handover/venv/bin:$PATH"
RUN pip install --upgrade pip
RUN pip install wheel
RUN pip install .

EXPOSE 5000
CMD  ["gunicorn", "--config", "/home/appuser/handover/gunicorn_config.py", "ensembl.production.handover.app.main:app"]
