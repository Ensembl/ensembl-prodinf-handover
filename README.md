# README
EnsEMBL - Production Handover Service Application
========

The handover app provides a simple endpoint to submit a new database to be checked and copied to the staging server for further automated processing. 

Implementation
==============

The `handover app <./src/ensembl/handover/app/main.py>`_ is a simple Flask app which defines endpoints for handover. After starting the app, full API documentation is available from ``/apidocs``.

The submission of a handover job triggers the submission of a `celery <https://github.com/Ensembl/ensembl-prodinf-handover/blob/master/docs/celery.rst>`_ task (`handover_database <https://github.com/Ensembl/ensembl-prodinf-handover/blob/master/src/ensembl/production/handover/celery_app/tasks.py>`_) which coordinates the necessary processes for checking and importing a database.

Installation
============

First clone this repo
```
  git clone https://github.com/Ensembl/ensembl-prodinf-handover
  cd ensembl-prodinf-handover
```
To install Python requirements using pip:


``` 
  pip install -r requirements.txt
  pip install . 
  handover_api (for devlopment perpous)    
```

Configuration
=============

Configuration is minimal and restricted to the contents of `config.py <./src/ensembl/handover/config.py>`_ which is restricted solely to basic Flask properties.

Running
=======

To start the main application as a standalone Flask application:

```
  export FLASK_APP=ensembl.production.handover.app.main.py
  flask run --port 5003 --host 0.0.0.0
```
or to start the main application as a standalone using gunicorn with 4 threads:

```
  gunicorn -w 4 -b 0.0.0.0:5003 ensembl.production.handover.app.main:app
```
Note that for production, a different deployment option should be used as the standalone flask app can only serve one request at a time.

There are multiple options, described at:
```
* http://flask.pocoo.org/docs/0.12/deploying/wsgi-standalone/
* http://flask.pocoo.org/docs/0.12/deploying/uwsgi/
```
To use a standalone gunicorn server with 4 worker threads:

```
  gunicorn -w 4 -b 0.0.0.0:5001 handover_app:app
```
Running Celery
==============
The Celery task manager is currently used for coordinating handover jobs. The default backend in ``config.py`` is RabbitMQ. This can be installed as per <https://www.rabbitmq.com/>.

To start a celery worker to handle handover:

```
    celery -A ensembl.production.handover.celery_app.tasks worker -l info -Q handover -n handover@%%h
```

Build Docker Image 
==================
```
sudo docker build -t handover . 
```
RUN Docker Container
====================
```
sudo docker run -p 5000:5000 -it  handover:latest
```




