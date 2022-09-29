FROM python:3.9

RUN useradd --create-home appuser
WORKDIR /home/appuser/
USER appuser
RUN mkdir -p /home/appuser/handover
RUN chown appuser:appuser /home/appuser/handover
WORKDIR /home/appuser/handover

#copy handover app
COPY --chown=appuser:appuser . /home/appuser/handover

#Install dependenciesls
RUN python -m venv /home/appuser/handover/venv
ENV PATH="/home/appuser/handover/venv/bin:$PATH"
RUN pip install -r requirements.txt
RUN pip install .

EXPOSE 5000
CMD  ["gunicorn", "--config", "/home/appuser/handover/gunicorn_config.py", "-b", "0.0.0.0:5000", "ensembl.production.handover.app.main:app"]

